"""
Interactive mode for Github-Repository-Manager
"""

import os
import asyncio
from typing import Optional, List, Dict, Any

import colorama
from colorama import Fore, Style

from core.github_api import GitHubAPI
from core.file_manager import FileManager
from core.logger import Logger
from cli.commands import Commands

class InteractiveMode:
    """Interactive command-line interface"""
    
    def __init__(self, github_api: GitHubAPI, file_manager: FileManager, logger: Logger):
        self.github_api = github_api
        self.file_manager = file_manager
        self.logger = logger
        self.running = True
    
    async def start(self) -> int:
        """Start interactive mode"""
        print(f"\n{Fore.CYAN}=== Github-Repository-Manager - Interactive Mode ==={Style.RESET_ALL}")
        print(f"Connected as: {Fore.GREEN}{self.github_api.username}{Style.RESET_ALL}")
        print(f"Type 'help' for available commands or 'quit' to exit\n")
        
        while self.running:
            try:
                command = input(f"{Fore.CYAN}github-automation> {Style.RESET_ALL}").strip()
                
                if not command:
                    continue
                
                await self._process_command(command)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Use 'quit' to exit{Style.RESET_ALL}")
            except EOFError:
                print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
                break
        
        return 0
    
    async def _process_command(self, command: str):
        """Process interactive command"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == 'help':
            self._show_help()
        elif cmd == 'quit' or cmd == 'exit':
            self.running = False
            print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
        elif cmd == 'status':
            await self._show_status()
        elif cmd == 'stats':
            await self._show_stats(parts[1:] if len(parts) > 1 else [])
        elif cmd == 'follow':
            await self._interactive_follow(parts[1:])
        elif cmd == 'unfollow':
            await self._interactive_unfollow(parts[1:])
        elif cmd == 'followback':
            await self._interactive_follow_back(parts[1:])
        elif cmd == 'check':
            await self._interactive_check(parts[1:])
        elif cmd == 'search':
            await self._interactive_search(parts[1:])
        elif cmd == 'backup':
            await self._interactive_backup()
        elif cmd == 'restore':
            await self._interactive_restore(parts[1:])
        elif cmd == 'list':
            await self._interactive_list(parts[1:])
        elif cmd == 'create':
            await self._interactive_create_repo(parts[1:])
        elif cmd == 'clone':
            await self._interactive_clone_repo(parts[1:])
        elif cmd == 'users':
            await self._interactive_search_users(parts[1:])
        elif cmd == 'clear':
            os.system('clear' if os.name == 'posix' else 'cls')
        else:
            print(f"{Fore.RED}Unknown command: {cmd}. Type 'help' for available commands.{Style.RESET_ALL}")
    
    def _show_help(self):
        """Show help information"""
        help_text = f"""
{Fore.CYAN}Available Commands:{Style.RESET_ALL}

{Fore.GREEN}General:{Style.RESET_ALL}
  help                    Show this help message
  quit, exit              Exit interactive mode
  clear                   Clear screen
  status                  Show current API status
  stats [username]        Show follow/follower statistics

{Fore.GREEN}Follow Operations:{Style.RESET_ALL}
  follow <username>       Follow a specific user
  unfollow <username>     Unfollow a specific user
  followback [limit]      Follow back your followers (default limit: 100)
  check <username>        Check if following/followed by user

{Fore.GREEN}Bulk Operations:{Style.RESET_ALL}
  search followers <username>     Show followers of a user
  search following <username>     Show users followed by a user
  
{Fore.GREEN}Repository Management:{Style.RESET_ALL}
  create <name>           Create a new repository
  clone <url>             Clone a repository
  
{Fore.GREEN}User Search:{Style.RESET_ALL}
  users                   Search users by criteria
  
{Fore.GREEN}Data Management:{Style.RESET_ALL}
  backup                  Create backup of current state
  restore [backup_file]   Restore from backup file
  list backups            List available backups
  list files              List data files

{Fore.YELLOW}Examples:{Style.RESET_ALL}
  follow octocat
  followback 50
  stats torvalds
  search followers octocat
  create my-new-repo
  clone https://github.com/user/repo
  users
  restore backup_20250830_063257.json
        """
        print(help_text)
    
    async def _show_status(self):
        """Show current API and rate limit status"""
        print(f"{Fore.CYAN}=== API Status ==={Style.RESET_ALL}")
        
        # User info
        user_info = await self.github_api.get_user_info()
        if user_info:
            print(f"User: {user_info.get('name', 'N/A')} (@{user_info.get('login', 'N/A')})")
            print(f"Public Repos: {user_info.get('public_repos', 0)}")
            print(f"Followers: {user_info.get('followers', 0)}")
            print(f"Following: {user_info.get('following', 0)}")
        
        # Rate limit status
        rate_limit = await self.github_api.get_rate_limit_status()
        if rate_limit and 'rate' in rate_limit:
            remaining = rate_limit['rate'].get('remaining', 'N/A')
            limit = rate_limit['rate'].get('limit', 'N/A')
            reset_time = rate_limit['rate'].get('reset', 'N/A')
            print(f"Rate Limit: {remaining}/{limit} remaining")
            if reset_time != 'N/A':
                from datetime import datetime
                reset_dt = datetime.fromtimestamp(reset_time)
                print(f"Resets at: {reset_dt.strftime('%H:%M:%S')}")
    
    async def _show_stats(self, args: List[str]):
        """Show detailed statistics"""
        # Use provided username or default to authenticated user
        username = args[0] if args else None
        
        # Use the proper Commands class method for consistency
        commands = Commands(self.github_api, self.file_manager, self.logger)
        
        # Always show detailed stats for authenticated user, basic stats for others
        detailed = (username is None or username == self.github_api.username)
        await commands.show_statistics(username, detailed)
    
    async def _interactive_follow(self, args: List[str]):
        """Interactive follow command"""
        if not args:
            username = input(f"{Fore.CYAN}Username to follow: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check if already following
        if await self.github_api.is_following(username):
            print(f"{Fore.YELLOW}Already following {username}{Style.RESET_ALL}")
            return
        
        # Get user info first
        user_info = await self.github_api.get_user_info(username)
        if not user_info:
            print(f"{Fore.RED}User {username} not found{Style.RESET_ALL}")
            return
        
        # Show user info
        print(f"\n{Fore.CYAN}User Information:{Style.RESET_ALL}")
        print(f"Name: {user_info.get('name', 'N/A')}")
        print(f"Bio: {user_info.get('bio', 'N/A')}")
        print(f"Followers: {user_info.get('followers', 0)}")
        print(f"Following: {user_info.get('following', 0)}")
        print(f"Public Repos: {user_info.get('public_repos', 0)}")
        
        # Confirm
        confirm = input(f"\n{Fore.CYAN}Follow {username}? (y/N): {Style.RESET_ALL}")
        if confirm.lower() == 'y':
            if await self.github_api.follow_user(username):
                print(f"{Fore.GREEN}✓ Successfully followed {username}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Failed to follow {username}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Follow cancelled{Style.RESET_ALL}")
    
    async def _interactive_follow_back(self, args: List[str]):
        """Interactive follow back command"""
        # Get limit from args or use default
        limit = 100
        if args:
            try:
                limit = int(args[0])
                if limit <= 0:
                    print(f"{Fore.RED}Limit must be a positive number{Style.RESET_ALL}")
                    return
            except ValueError:
                print(f"{Fore.RED}Invalid limit: {args[0]}. Using default limit of 100{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}Follow back limit: {limit}{Style.RESET_ALL}")
        
        # Use the commands instance to execute follow back
        commands = Commands(self.github_api, self.file_manager, self.logger)
        await commands.follow_back_followers(limit)
    
    async def _interactive_unfollow(self, args: List[str]):
        """Interactive unfollow command"""
        if not args:
            username = input(f"{Fore.CYAN}Username to unfollow: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check if currently following
        if not await self.github_api.is_following(username):
            print(f"{Fore.YELLOW}Not following {username}{Style.RESET_ALL}")
            return
        
        # Confirm
        confirm = input(f"{Fore.CYAN}Unfollow {username}? (y/N): {Style.RESET_ALL}")
        if confirm.lower() == 'y':
            if await self.github_api.unfollow_user(username):
                print(f"{Fore.GREEN}✓ Successfully unfollowed {username}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Failed to unfollow {username}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Unfollow cancelled{Style.RESET_ALL}")
    
    async def _interactive_check(self, args: List[str]):
        """Check follow relationship with a user"""
        if not args:
            username = input(f"{Fore.CYAN}Username to check: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check both directions
        following = await self.github_api.is_following(username)
        follower = await self.github_api.is_follower(username)
        
        print(f"\n{Fore.CYAN}Relationship with {username}:{Style.RESET_ALL}")
        print(f"You follow them: {Fore.GREEN if following else Fore.RED}{'Yes' if following else 'No'}{Style.RESET_ALL}")
        print(f"They follow you: {Fore.GREEN if follower else Fore.RED}{'Yes' if follower else 'No'}{Style.RESET_ALL}")
        
        if following and follower:
            print(f"{Fore.GREEN}✓ Mutual follow{Style.RESET_ALL}")
        elif following and not follower:
            print(f"{Fore.YELLOW}⚠ You follow them, but they don't follow back{Style.RESET_ALL}")
        elif not following and follower:
            print(f"{Fore.BLUE}ℹ They follow you, but you don't follow back{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ No follow relationship{Style.RESET_ALL}")
    
    async def _interactive_search(self, args: List[str]):
        """Search followers/following"""
        if len(args) < 2:
            print(f"{Fore.RED}Usage: search <followers|following> <username>{Style.RESET_ALL}")
            return
        
        search_type = args[0].lower()
        username = args[1]
        
        if search_type not in ['followers', 'following']:
            print(f"{Fore.RED}Search type must be 'followers' or 'following'{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Getting {search_type} for {username}...{Style.RESET_ALL}")
        
        if search_type == 'followers':
            users = await self.github_api.get_followers(username)
        else:
            users = await self.github_api.get_following(username)
        
        if not users:
            print(f"{Fore.YELLOW}No {search_type} found for {username}{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.GREEN}Found {len(users)} {search_type}:{Style.RESET_ALL}")
        
        # Show first 20 users
        for i, user in enumerate(users[:20]):
            print(f"  {i+1:2d}. {user}")
        
        if len(users) > 20:
            print(f"  ... and {len(users) - 20} more")
        
        # Option to save to file
        save = input(f"\n{Fore.CYAN}Save list to file? (y/N): {Style.RESET_ALL}")
        if save.lower() == 'y':
            filename = f"data/{username}_{search_type}.txt"
            if await self.file_manager.save_user_list(users, filename):
                print(f"{Fore.GREEN}Saved to {filename}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to save file{Style.RESET_ALL}")
    
    async def _interactive_backup(self):
        """Interactive backup creation"""
        print(f"{Fore.CYAN}Creating backup of your current follow state...{Style.RESET_ALL}")
        
        followers = await self.github_api.get_followers()
        following = await self.github_api.get_following()
        user_info = await self.github_api.get_user_info()
        
        backup_data = {
            'user': {
                'username': self.github_api.username,
                'profile': user_info
            },
            'followers': followers,
            'following': following,
            'stats': {
                'followers_count': len(followers),
                'following_count': len(following),
                'mutual_count': len(set(followers) & set(following))
            }
        }
        
        backup_path = await self.file_manager.create_backup(backup_data)
        if backup_path:
            print(f"{Fore.GREEN}✓ Backup created: {backup_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Failed to create backup{Style.RESET_ALL}")
    
    async def _interactive_restore(self, args: List[str]):
        """Interactive backup restore"""
        if not args:
            # Show available backups and let user choose
            backups = await self.file_manager.list_backups()
            if not backups:
                print(f"{Fore.YELLOW}No backups found{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.CYAN}Available backups:{Style.RESET_ALL}")
            for i, backup in enumerate(backups, 1):
                print(f"  {i:2d}. {backup['name']} ({backup['size']}, {backup['modified']})")
            
            try:
                choice = input(f"\n{Fore.CYAN}Select backup number (or press Enter to cancel): {Style.RESET_ALL}").strip()
                if not choice:
                    print(f"{Fore.YELLOW}Restore cancelled{Style.RESET_ALL}")
                    return
                
                backup_index = int(choice) - 1
                if 0 <= backup_index < len(backups):
                    backup_file = backups[backup_index]['name']
                else:
                    print(f"{Fore.RED}Invalid backup number{Style.RESET_ALL}")
                    return
            except ValueError:
                print(f"{Fore.RED}Invalid input{Style.RESET_ALL}")
                return
        else:
            backup_file = args[0]
        
        # Use Commands class to perform restore
        from cli.commands import Commands
        commands = Commands(self.github_api, self.file_manager, self.logger)
        backup_path = f"backups/{backup_file}" if not backup_file.startswith('backups/') else backup_file
        
        result = await commands.restore_backup(backup_path)
        
        if result == 0:
            print(f"{Fore.GREEN}✓ Restore completed successfully{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Restore failed or was cancelled{Style.RESET_ALL}")
    
    async def _interactive_list(self, args: List[str]):
        """List various items"""
        if not args:
            print(f"{Fore.RED}Usage: list <backups|files>{Style.RESET_ALL}")
            return
        
        list_type = args[0].lower()
        
        if list_type == 'backups':
            backups = await self.file_manager.list_backups()
            if not backups:
                print(f"{Fore.YELLOW}No backups found{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.CYAN}Available backups:{Style.RESET_ALL}")
            for i, backup in enumerate(backups, 1):
                print(f"  {i:2d}. {backup['name']} ({backup['size']}, {backup['modified']})")
        
        elif list_type == 'files':
            data_dir = self.file_manager.data_dir
            if not data_dir.exists():
                print(f"{Fore.YELLOW}Data directory not found{Style.RESET_ALL}")
                return
            
            files = list(data_dir.glob("*.txt"))
            if not files:
                print(f"{Fore.YELLOW}No data files found{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.CYAN}Data files:{Style.RESET_ALL}")
            for i, file_path in enumerate(files, 1):
                try:
                    lines = len([line for line in file_path.read_text().splitlines() 
                               if line.strip() and not line.startswith('#')])
                    print(f"  {i:2d}. {file_path.name} ({lines} entries)")
                except Exception as e:
                    print(f"  {i:2d}. {file_path.name} (error reading)")
        
        else:
            print(f"{Fore.RED}Unknown list type: {list_type}{Style.RESET_ALL}")
    
    async def _interactive_create_repo(self, args: List[str]):
        """Interactive repository creation"""
        if not args:
            name = input(f"{Fore.CYAN}Repository name: {Style.RESET_ALL}").strip()
        else:
            name = args[0]
        
        if not name:
            print(f"{Fore.RED}Repository name required{Style.RESET_ALL}")
            return
        
        description = input(f"{Fore.CYAN}Description (optional): {Style.RESET_ALL}").strip()
        
        private_input = input(f"{Fore.CYAN}Make private? (Y/n): {Style.RESET_ALL}").strip().lower()
        private = private_input != 'n'
        
        # Import Commands class functionality
        from cli.commands import Commands
        commands = Commands(self.github_api, self.file_manager, self.logger)
        await commands.create_repository(name, description, private)
    
    async def _interactive_clone_repo(self, args: List[str]):
        """Interactive repository cloning"""
        if not args:
            repo_url = input(f"{Fore.CYAN}Repository URL: {Style.RESET_ALL}").strip()
        else:
            repo_url = args[0]
        
        if not repo_url:
            print(f"{Fore.RED}Repository URL required{Style.RESET_ALL}")
            return
        
        local_path = input(f"{Fore.CYAN}Local path (optional): {Style.RESET_ALL}").strip()
        
        # Import Commands class functionality
        from cli.commands import Commands
        commands = Commands(self.github_api, self.file_manager, self.logger)
        await commands.clone_repository(repo_url, local_path)
    
    async def _interactive_search_users(self, args: List[str]):
        """Interactive user search"""
        print(f"{Fore.CYAN}Advanced User Search{Style.RESET_ALL}")
        
        try:
            min_followers_input = input(f"{Fore.CYAN}Minimum followers (default 100): {Style.RESET_ALL}").strip()
            min_followers = int(min_followers_input) if min_followers_input else 100
            
            min_repos_input = input(f"{Fore.CYAN}Minimum repositories (default 5): {Style.RESET_ALL}").strip()
            min_repos = int(min_repos_input) if min_repos_input else 5
            
            language = input(f"{Fore.CYAN}Programming language (optional): {Style.RESET_ALL}").strip()
            location = input(f"{Fore.CYAN}Location (optional): {Style.RESET_ALL}").strip()
            
            limit_input = input(f"{Fore.CYAN}Result limit (default 50): {Style.RESET_ALL}").strip()
            limit = int(limit_input) if limit_input else 50
            
            # Import Commands class functionality
            from cli.commands import Commands
            commands = Commands(self.github_api, self.file_manager, self.logger)
            await commands.search_users_advanced(min_followers, min_repos, language, location, limit)
            
        except ValueError:
            print(f"{Fore.RED}Invalid number input{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error in user search: {e}{Style.RESET_ALL}")
