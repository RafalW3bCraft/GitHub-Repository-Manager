import os
import json
import csv
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import shutil
from cryptography.fernet import Fernet

from .logger import Logger

class FileManager:

    def __init__(self):
        self.logger = Logger()
        self.data_dir = Path("data")
        self.logs_dir = Path("logs")
        self.backups_dir = Path("backups")
        self.encrypt_backups = os.getenv('ENCRYPT_BACKUPS', 'false').lower() == 'true'

        for directory in [self.data_dir, self.logs_dir, self.backups_dir]:
            directory.mkdir(exist_ok=True)

    async def load_user_list(self, file_path: str) -> List[str]:
        path = Path(file_path)

        if not path.exists():
            self.logger.error(f"File not found: {file_path}")
            return []

        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                usernames = []
                async for line in f:
                    username = line.strip()
                    if username and not username.startswith('#'):
                        usernames.append(username)

            self.logger.info(f"Loaded {len(usernames)} usernames from {file_path}")
            return usernames

        except Exception as e:
            self.logger.error(f"Error loading user list from {file_path}: {e}")
            return []

    async def save_user_list(self, usernames: List[str], file_path: str,
                      append: bool = False) -> bool:
        path = Path(file_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            async with aiofiles.open(path, mode, encoding='utf-8') as f:
                if append:
                    await f.write('\n')
                for username in usernames:
                    await f.write(f"{username}\n")

            action = "appended to" if append else "saved to"
            self.logger.info(f"Successfully {action} {len(usernames)} usernames to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving user list to {file_path}: {e}")
            return False

    async def load_json_data(self, file_path: str) -> Optional[Dict[str, Any]]:
        path = Path(file_path)

        if not path.exists():
            return None

        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)

            self.logger.debug(f"Loaded JSON data from {file_path}")
            return data

        except Exception as e:
            self.logger.error(f"Error loading JSON data from {file_path}: {e}")
            return None

    async def save_json_data(self, data: Dict[str, Any], file_path: str) -> bool:
        path = Path(file_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(json_content)

            self.logger.debug(f"Saved JSON data to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving JSON data to {file_path}: {e}")
            return False

    async def create_backup(self, follow_data: Dict[str, Any],
                     backup_name: Optional[str] = None) -> str:
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.json"

        backup_path = self.backups_dir / backup_name

        backup_data = {
            'created_at': datetime.now().isoformat(),
            'version': '2.0.0',
            'data': follow_data
        }

        try:
            if self.encrypt_backups:
                key = Fernet.generate_key()
                fernet = Fernet(key)

                json_data = json.dumps(backup_data, indent=2)
                encrypted_data = fernet.encrypt(json_data.encode())

                async with aiofiles.open(backup_path, 'wb') as f:
                    await f.write(encrypted_data)

                key_path = backup_path.with_suffix('.key')
                async with aiofiles.open(key_path, 'wb') as f:
                    await f.write(key)

                self.logger.info(f"Created encrypted backup: {backup_path}")
            else:
                json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
                async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                    await f.write(json_content)

                self.logger.info(f"Created backup: {backup_path}")

            return str(backup_path)

        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return ""

    async def restore_backup(self, backup_path: str) -> Optional[Dict[str, Any]]:
        path = Path(backup_path)

        if not path.exists():
            self.logger.error(f"Backup file not found: {backup_path}")
            return None

        try:
            if self.encrypt_backups and path.suffix == '.json':
                key_path = path.with_suffix('.key')
                if key_path.exists():
                    async with aiofiles.open(key_path, 'rb') as f:
                        key = await f.read()

                    fernet = Fernet(key)

                    async with aiofiles.open(path, 'rb') as f:
                        encrypted_data = await f.read()

                    decrypted_data = fernet.decrypt(encrypted_data)
                    backup_data = json.loads(decrypted_data.decode())
                else:
                    self.logger.error(f"Encryption key not found for {backup_path}")
                    return None
            else:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    backup_data = json.loads(content)

            self.logger.info(f"Restored backup from {backup_path}")
            return backup_data.get('data', backup_data)

        except Exception as e:
            self.logger.error(f"Error restoring backup from {backup_path}: {e}")
            return None

    async def list_backups(self) -> List[Dict[str, str]]:
        backups = []

        try:
            for backup_file in self.backups_dir.glob("backup_*.json"):
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size': f"{stat.st_size / 1024:.1f} KB",
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })

            backups.sort(key=lambda x: x['modified'], reverse=True)

            self.logger.debug(f"Found {len(backups)} backup files")
            return backups

        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []

    async def cleanup_old_backups(self, retention_days: int = 30) -> int:
        if retention_days <= 0:
            return 0

        cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 3600)
        deleted_count = 0

        try:
            for backup_file in self.backups_dir.glob("backup_*.json"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()

                    key_file = backup_file.with_suffix('.key')
                    if key_file.exists():
                        key_file.unlink()

                    deleted_count += 1
                    self.logger.debug(f"Deleted old backup: {backup_file.name}")

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old backup files")

            return deleted_count

        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}")
            return 0

    async def export_to_csv(self, data: List[Dict[str, Any]], file_path: str) -> bool:
        if not data:
            self.logger.warning("No data to export")
            return False

        path = Path(file_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            csv_content = output.getvalue()
            output.close()

            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(csv_content)

            self.logger.info(f"Exported {len(data)} records to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            return False

    async def ensure_data_files_exist(self):
        default_files = {
            'follow_list.txt': [''],
            'unfollow_list.txt': [''],
            'whitelist.txt': ['']
        }

        for filename, content in default_files.items():
            file_path = self.data_dir / filename
            if not file_path.exists():
                try:
                    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                        await f.write('\n'.join(content))
                    self.logger.debug(f"Created default file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error creating default file {file_path}: {e}")
