"""
Interactive mode for GitHub Automation Suite
"""

import os
from typing import Optional, List, Dict, Any

import colorama
from colorama import Fore, Style

from core.github_api import GitHubAPI
from core.file_manager import FileManager
from core.logger import Logger

class InteractiveMode:
    """Interactive command-line interface"""
    
    def __init__(self, github_api: GitHubAPI, file_manager: FileManager, logger: Logger):
        self.github_api = github_api
        self.file_manager = file_manager
        self.logger = logger
        self.running = True
    
    def start(self) -> int:
        """Start interactive mode"""
        print(f"\n{Fore.CYAN}=== GitHub Automation Suite - Interactive Mode ==={Style.RESET_ALL}")
        print(f"Connected as: {Fore.GREEN}{self.github_api.username}{Style.RESET_ALL}")
        print(f"Type 'help' for available commands or 'quit' to exit\n")
        
        while self.running:
            try:
                command = input(f"{Fore.CYAN}github-automation> {Style.RESET_ALL}").strip()
                
                if not command:
                    continue
                
                self._process_command(command)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Use 'quit' to exit{Style.RESET_ALL}")
            except EOFError:
                print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
                break
        
        return 0
    
    def _process_command(self, command: str):
        """Process interactive command"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == 'help':
            self._show_help()
        elif cmd == 'quit' or cmd == 'exit':
            self.running = False
            print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
        elif cmd == 'status':
            self._show_status()
        elif cmd == 'stats':
            self._show_stats()
        elif cmd == 'follow':
            self._interactive_follow(parts[1:])
        elif cmd == 'unfollow':
            self._interactive_unfollow(parts[1:])
        elif cmd == 'check':
            self._interactive_check(parts[1:])
        elif cmd == 'search':
            self._interactive_search(parts[1:])
        elif cmd == 'backup':
            self._interactive_backup()
        elif cmd == 'list':
            self._interactive_list(parts[1:])
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
  check <username>        Check if following/followed by user

{Fore.GREEN}Bulk Operations:{Style.RESET_ALL}
  search followers <username>     Show followers of a user
  search following <username>     Show users followed by a user
  
{Fore.GREEN}Data Management:{Style.RESET_ALL}
  backup                  Create backup of current state
  list backups            List available backups
  list files              List data files

{Fore.YELLOW}Examples:{Style.RESET_ALL}
  follow octocat
  stats torvalds
  search followers octocat
        """
        print(help_text)
    
    def _show_status(self):
        """Show current API and rate limit status"""
        print(f"{Fore.CYAN}=== API Status ==={Style.RESET_ALL}")
        
        # User info
        user_info = self.github_api.get_user_info()
        if user_info:
            print(f"User: {user_info.get('name', 'N/A')} (@{user_info.get('login', 'N/A')})")
            print(f"Public Repos: {user_info.get('public_repos', 0)}")
            print(f"Followers: {user_info.get('followers', 0)}")
            print(f"Following: {user_info.get('following', 0)}")
        
        # Rate limit status
        rate_limit = self.github_api.get_rate_limit_status()
        if rate_limit and 'rate' in rate_limit:
            remaining = rate_limit['rate'].get('remaining', 'N/A')
            limit = rate_limit['rate'].get('limit', 'N/A')
            reset_time = rate_limit['rate'].get('reset', 'N/A')
            print(f"Rate Limit: {remaining}/{limit} remaining")
            if reset_time != 'N/A':
                from datetime import datetime
                reset_dt = datetime.fromtimestamp(reset_time)
                print(f"Resets at: {reset_dt.strftime('%H:%M:%S')}")
    
    def _show_stats(self):
        """Show detailed statistics"""
        username = self.github_api.username
        
        print(f"{Fore.CYAN}Getting detailed statistics...{Style.RESET_ALL}")
        
        followers = self.github_api.get_followers(username)
        following = self.github_api.get_following(username)
        
        followers_set = set(followers)
        following_set = set(following)
        
        mutual = followers_set & following_set
        non_followers = following_set - followers_set
        not_following_back = followers_set - following_set
        
        print(f"\n{Fore.GREEN}=== Follow Statistics ==={Style.RESET_ALL}")
        print(f"Followers: {len(followers)}")
        print(f"Following: {len(following)}")
        print(f"Mutual follows: {len(mutual)}")
        print(f"Following but not followed back: {len(non_followers)}")
        print(f"Followers you don't follow back: {len(not_following_back)}")
        
        if following:
            ratio = len(followers) / len(following)
            print(f"Follower/Following ratio: {ratio:.2f}")
    
    def _interactive_follow(self, args: List[str]):
        """Interactive follow command"""
        if not args:
            username = input(f"{Fore.CYAN}Username to follow: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check if already following
        if self.github_api.is_following(username):
            print(f"{Fore.YELLOW}Already following {username}{Style.RESET_ALL}")
            return
        
        # Get user info first
        user_info = self.github_api.get_user_info(username)
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
            if self.github_api.follow_user(username):
                print(f"{Fore.GREEN}✓ Successfully followed {username}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Failed to follow {username}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Follow cancelled{Style.RESET_ALL}")
    
    def _interactive_unfollow(self, args: List[str]):
        """Interactive unfollow command"""
        if not args:
            username = input(f"{Fore.CYAN}Username to unfollow: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check if currently following
        if not self.github_api.is_following(username):
            print(f"{Fore.YELLOW}Not following {username}{Style.RESET_ALL}")
            return
        
        # Confirm
        confirm = input(f"{Fore.CYAN}Unfollow {username}? (y/N): {Style.RESET_ALL}")
        if confirm.lower() == 'y':
            if self.github_api.unfollow_user(username):
                print(f"{Fore.GREEN}✓ Successfully unfollowed {username}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Failed to unfollow {username}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Unfollow cancelled{Style.RESET_ALL}")
    
    def _interactive_check(self, args: List[str]):
        """Check follow relationship with a user"""
        if not args:
            username = input(f"{Fore.CYAN}Username to check: {Style.RESET_ALL}").strip()
        else:
            username = args[0]
        
        if not username:
            print(f"{Fore.RED}Username required{Style.RESET_ALL}")
            return
        
        # Check both directions
        following = self.github_api.is_following(username)
        follower = self.github_api.is_follower(username)
        
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
    
    def _interactive_search(self, args: List[str]):
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
            users = self.github_api.get_followers(username)
        else:
            users = self.github_api.get_following(username)
        
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
            if self.file_manager.save_user_list(users, filename):
                print(f"{Fore.GREEN}Saved to {filename}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to save file{Style.RESET_ALL}")
    
    def _interactive_backup(self):
        """Interactive backup creation"""
        print(f"{Fore.CYAN}Creating backup of your current follow state...{Style.RESET_ALL}")
        
        followers = self.github_api.get_followers()
        following = self.github_api.get_following()
        user_info = self.github_api.get_user_info()
        
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
        
        backup_path = self.file_manager.create_backup(backup_data)
        if backup_path:
            print(f"{Fore.GREEN}✓ Backup created: {backup_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Failed to create backup{Style.RESET_ALL}")
    
    def _interactive_list(self, args: List[str]):
        """List various items"""
        if not args:
            print(f"{Fore.RED}Usage: list <backups|files>{Style.RESET_ALL}")
            return
        
        list_type = args[0].lower()
        
        if list_type == 'backups':
            backups = self.file_manager.list_backups()
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
