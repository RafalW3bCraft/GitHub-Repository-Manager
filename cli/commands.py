"""
Command implementations for GitHub Automation Suite
"""

import time
import random
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import json

import colorama
from colorama import Fore, Style
from tqdm import tqdm

from core.github_api import GitHubAPI
from core.file_manager import FileManager
from core.logger import Logger
from core.validators import Validators

class Commands:
    """Implementation of all CLI commands"""
    
    def __init__(self, github_api: GitHubAPI, file_manager: FileManager, logger: Logger):
        self.github_api = github_api
        self.file_manager = file_manager
        self.logger = logger
        self.validators = Validators()
        
        # Ensure data files exist
        self.file_manager.ensure_data_files_exist()
    
    # follow_from_list method removed as per revision requirements
    
    # unfollow_from_list method removed as per revision requirements
    
    def auto_follow_followers(self, target_username: str, limit: int, 
                            filter_verified: bool, min_followers: int) -> int:
        """Auto-follow followers of a target user"""
        print(f"{Fore.CYAN}Getting followers of {target_username}...{Style.RESET_ALL}")
        
        # Get target user's followers
        followers = self.github_api.get_followers(target_username)
        if not followers:
            print(f"{Fore.RED}No followers found for {target_username}{Style.RESET_ALL}")
            return 1
        
        print(f"{Fore.GREEN}Found {len(followers)} followers{Style.RESET_ALL}")
        
        # Filter out users we're already following
        current_following = set(self.github_api.get_following())
        candidates = [f for f in followers if f not in current_following]
        
        if not candidates:
            print(f"{Fore.YELLOW}Already following all followers of {target_username}{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.CYAN}Found {len(candidates)} new candidates to follow{Style.RESET_ALL}")
        
        # Apply filters
        if filter_verified or min_followers > 0:
            filtered_candidates = []
            print(f"{Fore.CYAN}Applying filters...{Style.RESET_ALL}")
            
            with tqdm(total=len(candidates), desc="Filtering candidates") as pbar:
                for username in candidates:
                    user_info = self.github_api.get_user_info(username)
                    if user_info:
                        # Check verification (if user has a company or verified badge)
                        is_verified = bool(user_info.get('company') or 
                                         user_info.get('twitter_username'))
                        
                        # Check follower count
                        follower_count = user_info.get('followers', 0)
                        
                        if (not filter_verified or is_verified) and follower_count >= min_followers:
                            filtered_candidates.append(username)
                    
                    pbar.update(1)
            
            candidates = filtered_candidates
            print(f"{Fore.GREEN}After filtering: {len(candidates)} candidates{Style.RESET_ALL}")
        
        # Apply limit
        if len(candidates) > limit:
            candidates = candidates[:limit]
            print(f"{Fore.YELLOW}Limited to {limit} users{Style.RESET_ALL}")
        
        if not candidates:
            print(f"{Fore.YELLOW}No candidates remaining after filtering{Style.RESET_ALL}")
            return 0
        
        # Validate operation limits
        if not self.validators.validate_operation_limits('auto_follow', len(candidates)):
            return 1
        
        # Perform follows
        return self._execute_follow_operation(candidates, f"auto-following followers of {target_username}")
    
    def unfollow_non_followers(self, whitelist_path: Optional[str], min_days: int, 
                             no_confirm: bool = False) -> int:
        """Unfollow users who don't follow back"""
        print(f"{Fore.CYAN}Analyzing follow relationships...{Style.RESET_ALL}")
        
        # Get current following and followers
        following = set(self.github_api.get_following())
        followers = set(self.github_api.get_followers())
        
        # Find non-followers
        non_followers = following - followers
        
        if not non_followers:
            print(f"{Fore.GREEN}All users you follow also follow you back!{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.YELLOW}Found {len(non_followers)} users who don't follow back{Style.RESET_ALL}")
        
        # Load whitelist if provided
        whitelist = set()
        if whitelist_path:
            whitelist_users = self.file_manager.load_user_list(whitelist_path)
            whitelist = set(self.validators.validate_usernames(whitelist_users))
            if whitelist:
                print(f"{Fore.CYAN}Loaded {len(whitelist)} users from whitelist{Style.RESET_ALL}")
        
        # Filter out whitelisted users
        candidates = list(non_followers - whitelist)
        
        if len(candidates) != len(non_followers):
            protected = len(non_followers) - len(candidates)
            print(f"{Fore.GREEN}Protected {protected} users from whitelist{Style.RESET_ALL}")
        
        if not candidates:
            print(f"{Fore.GREEN}No users to unfollow after applying whitelist{Style.RESET_ALL}")
            return 0
        
        # TODO: Implement min_days filtering (would require storing follow dates)
        # For now, we'll just warn about it
        if min_days > 0:
            print(f"{Fore.YELLOW}Note: Minimum days filtering not yet implemented{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}Will unfollow {len(candidates)} users{Style.RESET_ALL}")
        
        # Confirmation
        if not no_confirm:
            print(f"\n{Fore.YELLOW}Users to unfollow:")
            for i, username in enumerate(candidates[:10]):  # Show first 10
                print(f"  {username}")
            if len(candidates) > 10:
                print(f"  ... and {len(candidates) - 10} more")
            
            confirm = input(f"\n{Fore.CYAN}Continue with unfollowing {len(candidates)} users? (y/N): {Style.RESET_ALL}")
            if confirm.lower() != 'y':
                print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return 0
        
        # Perform unfollows
        return self._execute_unfollow_operation(candidates, "cleanup non-followers")
    
    def show_statistics(self, username: Optional[str], detailed: bool = False) -> int:
        """Show follow/follower statistics"""
        target_user = username or self.github_api.username
        
        print(f"{Fore.CYAN}Getting statistics for {target_user}...{Style.RESET_ALL}")
        
        # Get user info
        user_info = self.github_api.get_user_info(target_user)
        if not user_info:
            print(f"{Fore.RED}Could not get user information for {target_user}{Style.RESET_ALL}")
            return 1
        
        # Get follow data
        followers = self.github_api.get_followers(target_user)
        following = self.github_api.get_following(target_user)
        
        # Basic statistics
        print(f"\n{Fore.GREEN}=== Statistics for {target_user} ==={Style.RESET_ALL}")
        print(f"Profile: {user_info.get('html_url', 'N/A')}")
        print(f"Name: {user_info.get('name', 'N/A')}")
        print(f"Bio: {user_info.get('bio', 'N/A')}")
        print(f"Public Repos: {user_info.get('public_repos', 0)}")
        print(f"Created: {user_info.get('created_at', 'N/A')}")
        print()
        
        print(f"{Fore.CYAN}Follow Statistics:{Style.RESET_ALL}")
        print(f"Followers: {len(followers)}")
        print(f"Following: {len(following)}")
        
        if following:
            ratio = len(followers) / len(following)
            print(f"Follower/Following Ratio: {ratio:.2f}")
        
        if detailed and target_user == self.github_api.username:
            # Detailed analysis for authenticated user
            print(f"\n{Fore.CYAN}Detailed Analysis:{Style.RESET_ALL}")
            
            followers_set = set(followers)
            following_set = set(following)
            
            mutual_follows = followers_set & following_set
            non_followers = following_set - followers_set
            not_following_back = followers_set - following_set
            
            print(f"Mutual follows: {len(mutual_follows)}")
            print(f"Following but not followed back: {len(non_followers)}")
            print(f"Followers you don't follow back: {len(not_following_back)}")
            
            if non_followers:
                print(f"\n{Fore.YELLOW}Users you follow who don't follow back (first 10):{Style.RESET_ALL}")
                for username in list(non_followers)[:10]:
                    print(f"  {username}")
                if len(non_followers) > 10:
                    print(f"  ... and {len(non_followers) - 10} more")
        
        # Rate limit status
        rate_limit = self.github_api.get_rate_limit_status()
        if rate_limit and 'rate' in rate_limit:
            remaining = rate_limit['rate'].get('remaining', 'N/A')
            limit = rate_limit['rate'].get('limit', 'N/A')
            print(f"\n{Fore.CYAN}API Rate Limit: {remaining}/{limit} remaining{Style.RESET_ALL}")
        
        return 0
    
    def create_backup(self) -> int:
        """Create backup of current follow/follower state"""
        print(f"{Fore.CYAN}Creating backup of follow/follower state...{Style.RESET_ALL}")
        
        try:
            # Get current state
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
                print(f"{Fore.GREEN}Backup created successfully: {backup_path}{Style.RESET_ALL}")
                return 0
            else:
                print(f"{Fore.RED}Failed to create backup{Style.RESET_ALL}")
                return 1
        
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            print(f"{Fore.RED}Error creating backup: {e}{Style.RESET_ALL}")
            return 1
    
    def restore_backup(self, backup_path: str) -> int:
        """Restore from backup file"""
        print(f"{Fore.CYAN}Restoring from backup: {backup_path}{Style.RESET_ALL}")
        
        backup_data = self.file_manager.restore_backup(backup_path)
        if not backup_data:
            print(f"{Fore.RED}Failed to load backup file{Style.RESET_ALL}")
            return 1
        
        # TODO: Implement restore logic
        # This would involve comparing current state with backup and generating actions
        print(f"{Fore.YELLOW}Restore functionality not yet implemented{Style.RESET_ALL}")
        print(f"Backup contains:")
        print(f"  Followers: {len(backup_data.get('followers', []))}")
        print(f"  Following: {len(backup_data.get('following', []))}")
        
        return 0
    
    def list_backups(self) -> int:
        """List available backup files"""
        backups = self.file_manager.list_backups()
        
        if not backups:
            print(f"{Fore.YELLOW}No backup files found{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.CYAN}Available backups:{Style.RESET_ALL}")
        print(f"{'Name':<30} {'Size':<10} {'Modified':<20}")
        print("-" * 62)
        
        for backup in backups:
            print(f"{backup['name']:<30} {backup['size']:<10} {backup['modified']:<20}")
        
        return 0
    
    def run_legacy_bulk_private(self) -> int:
        """Run legacy git-bulk-private functionality"""
        print(f"{Fore.CYAN}Running legacy bulk private repository operation...{Style.RESET_ALL}")
        
        try:
            repos = self.github_api.get_user_repositories()
            public_repos = [repo for repo in repos if not repo['private']]
            
            if not public_repos:
                print(f"{Fore.GREEN}All repositories are already private{Style.RESET_ALL}")
                return 0
            
            print(f"{Fore.YELLOW}Found {len(public_repos)} public repositories{Style.RESET_ALL}")
            
            # Confirmation
            confirm = input(f"{Fore.CYAN}Make all public repositories private? (y/N): {Style.RESET_ALL}")
            if confirm.lower() != 'y':
                print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return 0
            
            successful = 0
            failed = 0
            
            with tqdm(total=len(public_repos), desc="Making repositories private") as pbar:
                for repo in public_repos:
                    repo_name = repo['name']
                    pbar.set_postfix_str(f"Processing {repo_name}")
                    
                    if self.github_api.update_repository_visibility(repo_name, private=True):
                        successful += 1
                        print(f"{Fore.GREEN}✓ Made {repo_name} private{Style.RESET_ALL}")
                    else:
                        failed += 1
                        print(f"{Fore.RED}✗ Failed to update {repo_name}{Style.RESET_ALL}")
                    
                    pbar.update(1)
                    time.sleep(1)  # Rate limiting
            
            print(f"\n{Fore.CYAN}Repository Privacy Update Summary:{Style.RESET_ALL}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            
            return 0 if failed == 0 else 1
        
        except Exception as e:
            self.logger.error(f"Error in legacy bulk private operation: {e}")
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
            return 1
    
    def repository_manager(self, make_private: bool = False, make_public: bool = False, 
                          filter_type: str = 'all') -> int:
        """Enhanced repository visibility management with interactive selection"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║                    gitMaster-init v1.0.0                     ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║              Repository Visibility Manager                   ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║                   by RafalW3bCraft                          ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Check repository permissions first
        print(f"{Fore.CYAN}Checking repository access permissions...{Style.RESET_ALL}")
        permissions = self.github_api.check_repository_permissions()
        
        if not permissions['can_read_public']:
            print(f"{Fore.RED}Unable to read repositories. Please check your GitHub token.{Style.RESET_ALL}")
            return 1
        
        if not permissions['can_read_private']:
            print(f"{Fore.YELLOW}Warning: Cannot access private repositories. Token may lack 'repo' scope.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Only public repositories will be shown.{Style.RESET_ALL}")
        
        # Get all repositories
        print(f"{Fore.CYAN}Fetching your repositories...{Style.RESET_ALL}")
        repos = self.github_api.get_user_repositories()
        
        if not repos:
            print(f"{Fore.RED}No repositories found.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}This could be because:{Style.RESET_ALL}")
            print(f"  1. You have no repositories")
            print(f"  2. Token lacks proper permissions")
            print(f"  3. Network connectivity issues")
            return 1
        
        # Filter repositories based on current visibility
        if filter_type == 'public':
            filtered_repos = [repo for repo in repos if not repo['private']]
        elif filter_type == 'private':
            filtered_repos = [repo for repo in repos if repo['private']]
        else:
            filtered_repos = repos
        
        if not filtered_repos:
            print(f"{Fore.YELLOW}No {filter_type} repositories found{Style.RESET_ALL}")
            return 0
        
        # Display repository summary
        total_repos = len(repos)
        public_count = len([r for r in repos if not r['private']])
        private_count = len([r for r in repos if r['private']])
        
        print(f"{Fore.GREEN}Repository Summary:{Style.RESET_ALL}")
        print(f"  Total repositories: {total_repos}")
        print(f"  Public: {public_count}")
        print(f"  Private: {private_count}")
        print(f"  Showing: {len(filtered_repos)} {filter_type} repositories")
        print()
        
        # If direct operation requested (make-private or make-public)
        if make_private or make_public:
            # Check write permissions for repository operations
            if not permissions.get('can_write_repos', False):
                print(f"{Fore.RED}Cannot modify repositories. Token lacks 'repo' scope.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please generate a new token with 'repo' scope for repository modifications.{Style.RESET_ALL}")
                return 1
            
            target_visibility = 'private' if make_private else 'public'
            return self._bulk_visibility_operation(filtered_repos, target_visibility)
        
        # Interactive mode - display repositories with selection
        return self._interactive_repository_selection(filtered_repos)
    
    def _interactive_repository_selection(self, repos: List[Dict[str, Any]]) -> int:
        """Interactive repository selection interface"""
        print(f"{Fore.CYAN}Repository List:{Style.RESET_ALL}")
        print(f"{'#':<3} {'Name':<30} {'Visibility':<10} {'Stars':<6} {'Forks':<6} {'Updated':<12}")
        print("-" * 75)
        
        for i, repo in enumerate(repos):
            visibility = "Private" if repo['private'] else "Public"
            visibility_color = Fore.RED if repo['private'] else Fore.GREEN
            stars = repo.get('stargazers_count', 0)
            forks = repo.get('forks_count', 0)
            updated = repo.get('updated_at', '')[:10] if repo.get('updated_at') else 'Unknown'
            
            print(f"{i+1:<3} {repo['name']:<30} {visibility_color}{visibility:<10}{Style.RESET_ALL} "
                  f"{stars:<6} {forks:<6} {updated:<12}")
        
        print()
        print(f"{Fore.YELLOW}Selection Options:{Style.RESET_ALL}")
        print("  Enter repository numbers (e.g., 1,3,5-10)")
        print("  Type 'all' to select all repositories")
        print("  Type 'public' to select all public repositories")
        print("  Type 'private' to select all private repositories")
        print("  Type 'quit' or 'exit' to cancel")
        print()
        
        while True:
            try:
                selection = input(f"{Fore.CYAN}Select repositories: {Style.RESET_ALL}").strip().lower()
                
                if selection in ['quit', 'exit', 'q']:
                    print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                    return 0
                
                if selection == 'all':
                    selected_repos = repos
                elif selection == 'public':
                    selected_repos = [repo for repo in repos if not repo['private']]
                elif selection == 'private':
                    selected_repos = [repo for repo in repos if repo['private']]
                else:
                    # Parse number selection
                    selected_repos = self._parse_repository_selection(selection, repos)
                
                if not selected_repos:
                    print(f"{Fore.RED}No repositories selected or invalid selection{Style.RESET_ALL}")
                    continue
                
                # Ask what to do with selected repositories
                return self._process_selected_repositories(selected_repos)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return 0
            except EOFError:
                print(f"\n{Fore.YELLOW}Operation cancelled (EOF){Style.RESET_ALL}")
                return 0
            except Exception as e:
                print(f"{Fore.RED}Invalid selection: {e}{Style.RESET_ALL}")
                continue
    
    def _parse_repository_selection(self, selection: str, repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse user selection string into repository list"""
        selected_indices = set()
        
        try:
            parts = selection.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range selection (e.g., 5-10)
                    start, end = map(int, part.split('-'))
                    selected_indices.update(range(start-1, end))
                else:
                    # Single number
                    selected_indices.add(int(part) - 1)
            
            # Validate indices and return selected repositories
            valid_repos = []
            for idx in selected_indices:
                if 0 <= idx < len(repos):
                    valid_repos.append(repos[idx])
            
            return valid_repos
            
        except ValueError:
            return []
    
    def _process_selected_repositories(self, selected_repos: List[Dict[str, Any]]) -> int:
        """Process the action for selected repositories"""
        print(f"\n{Fore.GREEN}Selected {len(selected_repos)} repositories:{Style.RESET_ALL}")
        for repo in selected_repos[:5]:  # Show first 5
            visibility = "Private" if repo['private'] else "Public"
            print(f"  • {repo['name']} ({visibility})")
        if len(selected_repos) > 5:
            print(f"  ... and {len(selected_repos) - 5} more")
        
        print(f"\n{Fore.YELLOW}Available Actions:{Style.RESET_ALL}")
        print("  1. Make all selected repositories private")
        print("  2. Make all selected repositories public")
        print("  3. Toggle visibility (private ↔ public)")
        print("  4. Show detailed information")
        print("  5. Cancel operation")
        
        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Choose action (1-5): {Style.RESET_ALL}").strip()
                
                if choice == '1':
                    return self._bulk_visibility_operation(selected_repos, 'private')
                elif choice == '2':
                    return self._bulk_visibility_operation(selected_repos, 'public')
                elif choice == '3':
                    return self._toggle_repository_visibility(selected_repos)
                elif choice == '4':
                    return self._show_repository_details(selected_repos)
                elif choice == '5':
                    print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                    return 0
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter 1-5{Style.RESET_ALL}")
                    
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return 0
    
    def _bulk_visibility_operation(self, repos: List[Dict[str, Any]], target_visibility: str) -> int:
        """Perform bulk visibility change operation"""
        is_private = target_visibility == 'private'
        action = "private" if is_private else "public"
        
        # Filter repos that need changes
        repos_to_change = [repo for repo in repos if repo['private'] != is_private]
        
        if not repos_to_change:
            print(f"{Fore.GREEN}All selected repositories are already {action}{Style.RESET_ALL}")
            return 0
        
        print(f"\n{Fore.CYAN}Operation: Make {len(repos_to_change)} repositories {action}{Style.RESET_ALL}")
        
        # Confirmation
        confirm = input(f"{Fore.YELLOW}Are you sure? This action cannot be undone easily (y/N): {Style.RESET_ALL}")
        if confirm.lower() != 'y':
            print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
            return 0
        
        successful = 0
        failed = 0
        
        print(f"\n{Fore.CYAN}Processing repositories...{Style.RESET_ALL}")
        with tqdm(total=len(repos_to_change), desc=f"Making repositories {action}") as pbar:
            for repo in repos_to_change:
                repo_name = repo['name']
                pbar.set_postfix_str(f"Processing {repo_name}")
                
                if self.github_api.update_repository_visibility(repo_name, private=is_private):
                    successful += 1
                    status_icon = "🔒" if is_private else "🌐"
                    print(f"{Fore.GREEN}✓ {status_icon} {repo_name} → {action}{Style.RESET_ALL}")
                else:
                    failed += 1
                    print(f"{Fore.RED}✗ Failed to update {repo_name}{Style.RESET_ALL}")
                
                pbar.update(1)
                time.sleep(1)  # Rate limiting
        
        # Summary
        print(f"\n{Fore.CYAN}═══ Operation Summary ═══{Style.RESET_ALL}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total processed: {len(repos_to_change)}")
        
        if successful > 0:
            print(f"\n{Fore.GREEN}Successfully updated {successful} repositories to {action}!{Style.RESET_ALL}")
        
        return 0 if failed == 0 else 1
    
    def _toggle_repository_visibility(self, repos: List[Dict[str, Any]]) -> int:
        """Toggle visibility of repositories (private ↔ public)"""
        print(f"\n{Fore.CYAN}Toggle Operation: Converting repositories to opposite visibility{Style.RESET_ALL}")
        
        changes = []
        for repo in repos:
            current = "private" if repo['private'] else "public"
            target = "public" if repo['private'] else "private"
            changes.append(f"  • {repo['name']}: {current} → {target}")
        
        print("\n".join(changes))
        
        # Confirmation
        confirm = input(f"\n{Fore.YELLOW}Proceed with toggle operation? (y/N): {Style.RESET_ALL}")
        if confirm.lower() != 'y':
            print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
            return 0
        
        successful = 0
        failed = 0
        
        print(f"\n{Fore.CYAN}Processing repositories...{Style.RESET_ALL}")
        with tqdm(total=len(repos), desc="Toggling repository visibility") as pbar:
            for repo in repos:
                repo_name = repo['name']
                new_private = not repo['private']
                new_visibility = "private" if new_private else "public"
                
                pbar.set_postfix_str(f"Processing {repo_name}")
                
                if self.github_api.update_repository_visibility(repo_name, private=new_private):
                    successful += 1
                    status_icon = "🔒" if new_private else "🌐"
                    print(f"{Fore.GREEN}✓ {status_icon} {repo_name} → {new_visibility}{Style.RESET_ALL}")
                else:
                    failed += 1
                    print(f"{Fore.RED}✗ Failed to toggle {repo_name}{Style.RESET_ALL}")
                
                pbar.update(1)
                time.sleep(1)  # Rate limiting
        
        # Summary
        print(f"\n{Fore.CYAN}═══ Toggle Summary ═══{Style.RESET_ALL}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total processed: {len(repos)}")
        
        return 0 if failed == 0 else 1
    
    def _show_repository_details(self, repos: List[Dict[str, Any]]) -> int:
        """Show detailed information about selected repositories"""
        print(f"\n{Fore.CYAN}═══ Repository Details ═══{Style.RESET_ALL}")
        
        for repo in repos:
            visibility = "🔒 Private" if repo['private'] else "🌐 Public"
            stars = repo.get('stargazers_count', 0)
            forks = repo.get('forks_count', 0)
            size = repo.get('size', 0)
            language = repo.get('language', 'Unknown')
            updated = repo.get('updated_at', '')[:10] if repo.get('updated_at') else 'Unknown'
            
            print(f"\n{Fore.YELLOW}📁 {repo['name']}{Style.RESET_ALL}")
            print(f"   {visibility}")
            print(f"   ⭐ Stars: {stars} | 🍴 Forks: {forks} | 📦 Size: {size} KB")
            print(f"   💻 Language: {language} | 📅 Updated: {updated}")
            if repo.get('description'):
                print(f"   📝 {repo['description'][:80]}{'...' if len(repo.get('description', '')) > 80 else ''}")
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return 0
    
    def _execute_follow_operation(self, usernames: List[str], operation_name: str) -> int:
        """Execute follow operation with progress tracking"""
        successful = 0
        failed = 0
        
        with tqdm(total=len(usernames), desc=f"Following users ({operation_name})") as pbar:
            for username in usernames:
                pbar.set_postfix_str(f"Processing {username}")
                
                try:
                    if self.github_api.follow_user(username):
                        successful += 1
                        print(f"{Fore.GREEN}✓ Followed {username}{Style.RESET_ALL}")
                    else:
                        failed += 1
                        print(f"{Fore.RED}✗ Failed to follow {username}{Style.RESET_ALL}")
                    
                    # Rate limiting delay
                    time.sleep(random.uniform(1, 3))
                
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
                    break
                except Exception as e:
                    self.logger.error(f"Error following {username}: {e}")
                    failed += 1
                
                pbar.update(1)
        
        self._print_operation_summary(f"Auto-follow ({operation_name})", successful, failed, 0)
        return 0 if failed == 0 else 1
    
    def _execute_unfollow_operation(self, usernames: List[str], operation_name: str) -> int:
        """Execute unfollow operation with progress tracking"""
        successful = 0
        failed = 0
        
        with tqdm(total=len(usernames), desc=f"Unfollowing users ({operation_name})") as pbar:
            for username in usernames:
                pbar.set_postfix_str(f"Processing {username}")
                
                try:
                    if self.github_api.unfollow_user(username):
                        successful += 1
                        print(f"{Fore.GREEN}✓ Unfollowed {username}{Style.RESET_ALL}")
                    else:
                        failed += 1
                        print(f"{Fore.RED}✗ Failed to unfollow {username}{Style.RESET_ALL}")
                    
                    # Rate limiting delay
                    time.sleep(random.uniform(1, 3))
                
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
                    break
                except Exception as e:
                    self.logger.error(f"Error unfollowing {username}: {e}")
                    failed += 1
                
                pbar.update(1)
        
        self._print_operation_summary(f"Unfollow ({operation_name})", successful, failed, 0)
        return 0 if failed == 0 else 1
    
    def _print_operation_summary(self, operation: str, successful: int, failed: int, 
                               skipped: int):
        """Print operation summary"""
        print(f"\n{Fore.CYAN}{operation} Operation Summary:{Style.RESET_ALL}")
        
        print(f"Successful: {Fore.GREEN}{successful}{Style.RESET_ALL}")
        if failed > 0:
            print(f"Failed: {Fore.RED}{failed}{Style.RESET_ALL}")
        if skipped > 0:
            print(f"Skipped: {Fore.YELLOW}{skipped}{Style.RESET_ALL}")
        
        total = successful + failed + skipped
        if total > 0:
            success_rate = (successful / total) * 100
            print(f"Success Rate: {success_rate:.1f}%")
    
    def debug_repository_access(self) -> int:
        """Debug repository access and permissions"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║         Repository Access Debug         ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Check basic authentication
        print(f"{Fore.CYAN}1. Testing GitHub authentication...{Style.RESET_ALL}")
        if self.github_api.validate_token():
            print(f"{Fore.GREEN}✓ Authentication successful{Style.RESET_ALL}")
            print(f"  Username: {self.github_api.username}")
        else:
            print(f"{Fore.RED}✗ Authentication failed{Style.RESET_ALL}")
            return 1
        
        # Check token scopes
        print(f"\n{Fore.CYAN}2. Checking token scopes...{Style.RESET_ALL}")
        try:
            response = self.github_api._make_request('GET', '/user')
            if response.status_code == 200:
                scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
                scopes = [scope.strip() for scope in scopes if scope.strip()]
                print(f"  Current scopes: {', '.join(scopes) if scopes else 'None'}")
                
                required_scopes = ['repo', 'user:follow']
                for scope in required_scopes:
                    if scope in scopes:
                        print(f"  {Fore.GREEN}✓ {scope}{Style.RESET_ALL}")
                    else:
                        print(f"  {Fore.RED}✗ {scope} (missing){Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Cannot check scopes: {response.status_code}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ Error checking scopes: {e}{Style.RESET_ALL}")
        
        # Check repository permissions
        print(f"\n{Fore.CYAN}3. Testing repository access...{Style.RESET_ALL}")
        permissions = self.github_api.check_repository_permissions()
        
        for perm, value in permissions.items():
            status = f"{Fore.GREEN}✓" if value else f"{Fore.RED}✗"
            print(f"  {status} {perm.replace('_', ' ').title()}: {value}{Style.RESET_ALL}")
        
        # Test repository listing
        print(f"\n{Fore.CYAN}4. Testing repository listing...{Style.RESET_ALL}")
        try:
            # Test different endpoints
            endpoints = [
                ('/user/repos', 'Authenticated user repos'),
                (f'/users/{self.github_api.username}/repos', 'Public user repos')
            ]
            
            for endpoint, description in endpoints:
                response = self.github_api._make_request('GET', endpoint, params={'per_page': 1})
                if response.status_code == 200:
                    data = response.json()
                    print(f"  {Fore.GREEN}✓ {description}: {len(data)} repos found{Style.RESET_ALL}")
                else:
                    print(f"  {Fore.RED}✗ {description}: HTTP {response.status_code}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}✗ Repository listing error: {e}{Style.RESET_ALL}")
        
        # Test actual repository fetching
        print(f"\n{Fore.CYAN}5. Testing full repository fetch...{Style.RESET_ALL}")
        try:
            repos = self.github_api.get_user_repositories()
            public_count = len([r for r in repos if not r.get('private', False)])
            private_count = len([r for r in repos if r.get('private', False)])
            
            print(f"  {Fore.GREEN}✓ Total repositories: {len(repos)}{Style.RESET_ALL}")
            print(f"    - Public: {public_count}")
            print(f"    - Private: {private_count}")
            
            if repos:
                print(f"\n{Fore.CYAN}Sample repositories:{Style.RESET_ALL}")
                for repo in repos[:3]:
                    visibility = "Private" if repo.get('private', False) else "Public"
                    print(f"    • {repo['name']} ({visibility})")
        except Exception as e:
            print(f"  {Fore.RED}✗ Full fetch error: {e}{Style.RESET_ALL}")
        
        # Rate limit status
        print(f"\n{Fore.CYAN}6. Rate limit status...{Style.RESET_ALL}")
        try:
            rate_limit = self.github_api.get_rate_limit_status()
            if rate_limit and 'rate' in rate_limit:
                remaining = rate_limit['rate'].get('remaining', 'N/A')
                limit = rate_limit['rate'].get('limit', 'N/A')
                reset_time = rate_limit['rate'].get('reset', 'N/A')
                print(f"  Remaining: {remaining}/{limit}")
                print(f"  Reset time: {reset_time}")
            else:
                print(f"  {Fore.YELLOW}Rate limit info not available{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}✗ Rate limit check error: {e}{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}Debug complete!{Style.RESET_ALL}")
        return 0
    
    def toggle_repositories_visibility(self, filter_type: str = 'all') -> int:
        """Toggle visibility of selected repositories"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║         Repository Visibility Toggle     ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Get repositories with permission checking
        permissions = self.github_api.check_repository_permissions()
        
        print(f"{Fore.CYAN}Fetching repositories...{Style.RESET_ALL}")
        repos = self.github_api.get_user_repositories()
        
        if not repos:
            print(f"{Fore.RED}No repositories found or unable to access repositories.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Possible issues:{Style.RESET_ALL}")
            print(f"  1. No repositories in account")
            print(f"  2. Token lacks proper permissions")
            print(f"  3. Network connectivity issues")
            return 1
        
        # Filter repositories based on type
        if filter_type == 'public':
            filtered_repos = [repo for repo in repos if not repo['private']]
        elif filter_type == 'private':
            filtered_repos = [repo for repo in repos if repo['private']]
        else:
            filtered_repos = repos
        
        if not filtered_repos:
            print(f"{Fore.YELLOW}No {filter_type} repositories found{Style.RESET_ALL}")
            return 0
        
        # Check write permissions for repository operations
        if not permissions.get('can_write_repos', False):
            print(f"{Fore.RED}Cannot modify repositories. Token lacks 'repo' scope.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Please generate a new token with 'repo' scope for repository modifications.{Style.RESET_ALL}")
            return 1
        
        # Display repository summary
        total_repos = len(repos)
        public_count = len([r for r in repos if not r['private']])
        private_count = len([r for r in repos if r['private']])
        
        print(f"{Fore.GREEN}Repository Summary:{Style.RESET_ALL}")
        print(f"  Total repositories: {total_repos}")
        print(f"  Public: {public_count}")
        print(f"  Private: {private_count}")
        print(f"  Showing: {len(filtered_repos)} {filter_type} repositories")
        print()
        
        # Interactive repository selection
        selected_repos = self._select_repositories_for_toggle(filtered_repos)
        if not selected_repos:
            return 0
        
        # Perform toggle operation
        return self._toggle_repository_visibility(selected_repos)
    
    def _select_repositories_for_toggle(self, repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Select repositories for toggle operation"""
        print(f"{Fore.CYAN}Repository List (Toggle Mode):{Style.RESET_ALL}")
        print(f"{'#':<3} {'Name':<30} {'Current':<10} {'Will Become':<12} {'Stars':<6} {'Updated':<12}")
        print("-" * 80)
        
        for i, repo in enumerate(repos):
            current = "Private" if repo['private'] else "Public"
            will_become = "Public" if repo['private'] else "Private"
            current_color = Fore.RED if repo['private'] else Fore.GREEN
            will_color = Fore.GREEN if repo['private'] else Fore.RED
            stars = repo.get('stargazers_count', 0)
            updated = repo.get('updated_at', '')[:10] if repo.get('updated_at') else 'Unknown'
            
            print(f"{i+1:<3} {repo['name']:<30} {current_color}{current:<10}{Style.RESET_ALL} "
                  f"{will_color}{will_become:<12}{Style.RESET_ALL} {stars:<6} {updated:<12}")
        
        print()
        print(f"{Fore.YELLOW}Selection Options:{Style.RESET_ALL}")
        print("  Enter repository numbers (e.g., 1,3,5-10)")
        print("  Type 'all' to toggle all repositories")
        print("  Type 'quit' or 'exit' to cancel")
        print()
        
        while True:
            try:
                selection = input(f"{Fore.CYAN}Select repositories to toggle: {Style.RESET_ALL}").strip().lower()
                
                if selection in ['quit', 'exit', 'q']:
                    print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                    return []
                
                if selection == 'all':
                    return repos
                else:
                    # Parse number selection
                    return self._parse_repository_selection(selection, repos)
                    
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return []
            except EOFError:
                print(f"\n{Fore.YELLOW}Operation cancelled (EOF){Style.RESET_ALL}")
                return []
            except Exception as e:
                print(f"{Fore.RED}Invalid selection: {e}{Style.RESET_ALL}")
                continue
