"""
File management utilities for GitHub Automation Suite
"""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import shutil
from cryptography.fernet import Fernet

from .logger import Logger

class FileManager:
    """Handle file operations for the automation suite"""
    
    def __init__(self):
        self.logger = Logger()
        self.data_dir = Path("data")
        self.logs_dir = Path("logs")
        self.backups_dir = Path("backups")
        self.encrypt_backups = os.getenv('ENCRYPT_BACKUPS', 'false').lower() == 'true'
        
        # Create directories if they don't exist
        for directory in [self.data_dir, self.logs_dir, self.backups_dir]:
            directory.mkdir(exist_ok=True)
    
    def load_user_list(self, file_path: str) -> List[str]:
        """Load list of usernames from file"""
        path = Path(file_path)
        
        if not path.exists():
            self.logger.error(f"File not found: {file_path}")
            return []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                usernames = []
                for line in f:
                    username = line.strip()
                    if username and not username.startswith('#'):
                        usernames.append(username)
            
            self.logger.info(f"Loaded {len(usernames)} usernames from {file_path}")
            return usernames
            
        except Exception as e:
            self.logger.error(f"Error loading user list from {file_path}: {e}")
            return []
    
    def save_user_list(self, usernames: List[str], file_path: str, 
                      append: bool = False) -> bool:
        """Save list of usernames to file"""
        path = Path(file_path)
        
        try:
            # Create directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                if append:
                    f.write('\n')
                for username in usernames:
                    f.write(f"{username}\n")
            
            action = "appended to" if append else "saved to"
            self.logger.info(f"Successfully {action} {len(usernames)} usernames to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving user list to {file_path}: {e}")
            return False
    
    def load_json_data(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load JSON data from file"""
        path = Path(file_path)
        
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.debug(f"Loaded JSON data from {file_path}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error loading JSON data from {file_path}: {e}")
            return None
    
    def save_json_data(self, data: Dict[str, Any], file_path: str) -> bool:
        """Save data as JSON to file"""
        path = Path(file_path)
        
        try:
            # Create directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved JSON data to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving JSON data to {file_path}: {e}")
            return False
    
    def create_backup(self, follow_data: Dict[str, Any], 
                     backup_name: Optional[str] = None) -> str:
        """Create backup of current follow/follower state"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.json"
        
        backup_path = self.backups_dir / backup_name
        
        # Add metadata to backup
        backup_data = {
            'created_at': datetime.now().isoformat(),
            'version': '2.0.0',
            'data': follow_data
        }
        
        try:
            if self.encrypt_backups:
                # Generate encryption key and save encrypted backup
                key = Fernet.generate_key()
                fernet = Fernet(key)
                
                json_data = json.dumps(backup_data, indent=2)
                encrypted_data = fernet.encrypt(json_data.encode())
                
                with open(backup_path, 'wb') as f:
                    f.write(encrypted_data)
                
                # Save key separately
                key_path = backup_path.with_suffix('.key')
                with open(key_path, 'wb') as f:
                    f.write(key)
                
                self.logger.info(f"Created encrypted backup: {backup_path}")
            else:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Created backup: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return ""
    
    def restore_backup(self, backup_path: str) -> Optional[Dict[str, Any]]:
        """Restore from backup file"""
        path = Path(backup_path)
        
        if not path.exists():
            self.logger.error(f"Backup file not found: {backup_path}")
            return None
        
        try:
            if self.encrypt_backups and path.suffix == '.json':
                # Try to find corresponding key file
                key_path = path.with_suffix('.key')
                if key_path.exists():
                    with open(key_path, 'rb') as f:
                        key = f.read()
                    
                    fernet = Fernet(key)
                    
                    with open(path, 'rb') as f:
                        encrypted_data = f.read()
                    
                    decrypted_data = fernet.decrypt(encrypted_data)
                    backup_data = json.loads(decrypted_data.decode())
                else:
                    self.logger.error(f"Encryption key not found for {backup_path}")
                    return None
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            
            self.logger.info(f"Restored backup from {backup_path}")
            return backup_data.get('data', backup_data)
            
        except Exception as e:
            self.logger.error(f"Error restoring backup from {backup_path}: {e}")
            return None
    
    def list_backups(self) -> List[Dict[str, str]]:
        """List available backup files"""
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
            
            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x['modified'], reverse=True)
            
            self.logger.debug(f"Found {len(backups)} backup files")
            return backups
            
        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []
    
    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """Clean up old backup files"""
        if retention_days <= 0:
            return 0
        
        cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 3600)
        deleted_count = 0
        
        try:
            for backup_file in self.backups_dir.glob("backup_*.json"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    
                    # Also delete corresponding key file if it exists
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
    
    def export_to_csv(self, data: List[Dict[str, Any]], file_path: str) -> bool:
        """Export data to CSV format"""
        if not data:
            self.logger.warning("No data to export")
            return False
        
        path = Path(file_path)
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            
            self.logger.info(f"Exported {len(data)} records to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            return False
    
    def ensure_data_files_exist(self):
        """Create default data files if they don't exist"""
        default_files = {
            'follow_list.txt': [
                '# Add usernames to follow, one per line',
                '# Lines starting with # are comments',
                ''
            ],
            'unfollow_list.txt': [
                '# Add usernames to unfollow, one per line',
                '# Lines starting with # are comments',
                ''
            ],
            'whitelist.txt': [
                '# Add usernames to never unfollow, one per line',
                '# These users will be protected during cleanup operations',
                '# Lines starting with # are comments',
                ''
            ]
        }
        
        for filename, content in default_files.items():
            file_path = self.data_dir / filename
            if not file_path.exists():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(content))
                    self.logger.debug(f"Created default file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error creating default file {file_path}: {e}")
