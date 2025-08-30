"""
Command implementations for Github-Repository-Manager
"""

import asyncio
import time
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
    
    # follow_from_list method removed as per revision requirements
    
    # unfollow_from_list method removed as per revision requirements
    
    async def auto_follow_followers(self, target_username: str, limit: int, 
                            filter_verified: bool, min_followers: int) -> int:
        """Auto-follow followers of a target user"""
        print(f"{Fore.CYAN}Getting followers of {target_username}...{Style.RESET_ALL}")
        
        # Get target user's followers
        followers = await self.github_api.get_followers(target_username)
        if not followers:
            print(f"{Fore.RED}No followers found for {target_username}{Style.RESET_ALL}")
            return 1
        
        print(f"{Fore.GREEN}Found {len(followers)} followers{Style.RESET_ALL}")
        
        # Filter out users we're already following
        current_following = set(await self.github_api.get_following())
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
                    user_info = await self.github_api.get_user_info(username)
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
        
        # No operation limits - proceed with all candidates
        self.logger.info(f"Processing {len(candidates)} candidates - no limits enforced")
        
        # Perform follows
        return await self._execute_follow_operation(candidates, f"auto-following followers of {target_username}")
    
    async def follow_back_followers(self, limit: int = 100) -> int:
        """Follow back users who are following you but you don't follow back"""
        print(f"{Fore.CYAN}Analyzing follow relationships for follow back...{Style.RESET_ALL}")
        
        # Get current followers and following - use cache-aware methods that include local state
        followers = set(await self.github_api.get_followers())
        following = set(await self.github_api.get_following())
        
        # Find followers we're not following back
        follow_back_candidates = list(followers - following)
        
        # Additional validation: Check if we're already following each candidate
        print(f"{Fore.CYAN}Validating follow status for candidates with retry logic...{Style.RESET_ALL}")
        validated_candidates = []
        
        for username in follow_back_candidates:
            # Use retry logic to handle API consistency issues
            if not await self.github_api.is_following_with_retry(username):
                validated_candidates.append(username)
            else:
                print(f"{Fore.YELLOW}⚠️  Already following {username} (confirmed with retry validation){Style.RESET_ALL}")
        
        follow_back_candidates = validated_candidates
        
        if not follow_back_candidates:
            print(f"{Fore.GREEN}You're already following back all your followers!{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.YELLOW}Found {len(follow_back_candidates)} followers you haven't followed back{Style.RESET_ALL}")
        
        # Apply limit
        if len(follow_back_candidates) > limit:
            follow_back_candidates = follow_back_candidates[:limit]
            print(f"{Fore.CYAN}Limited to {limit} users for follow back{Style.RESET_ALL}")
        
        # Show confirmation
        print(f"\n{Fore.GREEN}Users to follow back:{Style.RESET_ALL}")
        for i, username in enumerate(follow_back_candidates[:10], 1):
            print(f"  {i}. {username}")
        if len(follow_back_candidates) > 10:
            print(f"  ... and {len(follow_back_candidates) - 10} more")
        
        # Ask for confirmation
        try:
            confirm = input(f"\n{Fore.CYAN}Follow back {len(follow_back_candidates)} users? (y/N): {Style.RESET_ALL}").strip().lower()
            if confirm not in ['y', 'yes']:
                print(f"{Fore.YELLOW}Follow back operation cancelled{Style.RESET_ALL}")
                return 0
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Follow back operation cancelled{Style.RESET_ALL}")
            return 130
        
        # Perform follow back operations
        result = await self._execute_follow_operation(follow_back_candidates, "follow back")
        
        # Complete follow back operations - local state is already updated in follow_user()
        if follow_back_candidates:
            print(f"{Fore.CYAN}✓ Follow back operation completed{Style.RESET_ALL}")
            # Do NOT invalidate cache - rely on local state tracking for immediate consistency
        
        return result
    
    async def unfollow_non_followers(self, whitelist_path: Optional[str], min_days: int, 
                             no_confirm: bool = False) -> int:
        """Unfollow users who don't follow back"""
        print(f"{Fore.CYAN}Analyzing follow relationships...{Style.RESET_ALL}")
        
        # Get current following and followers
        following = set(await self.github_api.get_following())
        followers = set(await self.github_api.get_followers())
        
        # Find non-followers
        non_followers = following - followers
        
        if not non_followers:
            print(f"{Fore.GREEN}All users you follow also follow you back!{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.YELLOW}Found {len(non_followers)} users who don't follow back{Style.RESET_ALL}")
        
        # Load whitelist if provided
        whitelist = set()
        if whitelist_path:
            whitelist_users = await self.file_manager.load_user_list(whitelist_path)
            whitelist = set(await self.validators.validate_usernames(whitelist_users))
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
        
        # Apply min_days filtering by checking user profile creation dates as proxy
        if min_days > 0:
            print(f"{Fore.CYAN}Applying minimum {min_days} days filter...{Style.RESET_ALL}")
            filtered_candidates = []
            cutoff_date = datetime.now() - timedelta(days=min_days)
            
            with tqdm(total=len(candidates), desc="Filtering by minimum days") as pbar:
                for username in candidates:
                    user_info = await self.github_api.get_user_info(username)
                    if user_info and user_info.get('created_at'):
                        try:
                            created_date = datetime.fromisoformat(user_info['created_at'].replace('Z', '+00:00'))
                            if created_date < cutoff_date:
                                filtered_candidates.append(username)
                        except (ValueError, TypeError):
                            # If date parsing fails, include the user (conservative approach)
                            filtered_candidates.append(username)
                    else:
                        # If we can't get user info, include them (conservative approach)
                        filtered_candidates.append(username)
                    pbar.update(1)
            
            original_count = len(candidates)
            candidates = filtered_candidates
            filtered_count = original_count - len(candidates)
            if filtered_count > 0:
                print(f"{Fore.YELLOW}Filtered out {filtered_count} users (followed less than {min_days} days ago){Style.RESET_ALL}")
        
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
        return await self._execute_unfollow_operation(candidates, "cleanup non-followers")
    
    async def show_statistics(self, username: Optional[str], detailed: bool = False) -> int:
        """Show follow/follower statistics"""
        target_user = username or self.github_api.username
        
        print(f"{Fore.CYAN}Getting statistics for {target_user}...{Style.RESET_ALL}")
        
        # Get user info
        user_info = await self.github_api.get_user_info(target_user)
        if not user_info:
            print(f"{Fore.RED}Could not get user information for {target_user}{Style.RESET_ALL}")
            return 1
        
        # Get follow data
        followers = await self.github_api.get_followers(target_user)
        following = await self.github_api.get_following(target_user)
        
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
            # Detailed analysis for authenticated user with local state consideration
            print(f"\n{Fore.CYAN}Detailed Analysis:{Style.RESET_ALL}")
            
            followers_set = set(followers)
            following_set = set(following)
            
            # Apply local state adjustments for accurate real-time stats
            # Add recently followed users to following set
            following_set.update(self.github_api._recently_followed)
            # Remove recently unfollowed users from following set
            following_set.difference_update(self.github_api._recently_unfollowed)
            
            # Debug info for recently followed users
            if self.github_api._recently_followed:
                recently_followed_count = len(self.github_api._recently_followed)
                print(f"{Fore.YELLOW}[DEBUG] Recently followed: {recently_followed_count} users{Style.RESET_ALL}")
            
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
        rate_limit = await self.github_api.get_rate_limit_status()
        if rate_limit and 'rate' in rate_limit:
            remaining = rate_limit['rate'].get('remaining', 'N/A')
            limit = rate_limit['rate'].get('limit', 'N/A')
            print(f"\n{Fore.CYAN}API Rate Limit: {remaining}/{limit} remaining{Style.RESET_ALL}")
        
        return 0
    
    async def create_backup(self) -> int:
        """Create backup of current follow/follower state"""
        print(f"{Fore.CYAN}Creating backup of follow/follower state...{Style.RESET_ALL}")
        
        try:
            # Get current state
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
                print(f"{Fore.GREEN}Backup created successfully: {backup_path}{Style.RESET_ALL}")
                return 0
            else:
                print(f"{Fore.RED}Failed to create backup{Style.RESET_ALL}")
                return 1
        
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            print(f"{Fore.RED}Error creating backup: {e}{Style.RESET_ALL}")
            return 1
    
    async def restore_backup(self, backup_path: str) -> int:
        """Restore from backup file"""
        print(f"{Fore.CYAN}Restoring from backup: {backup_path}{Style.RESET_ALL}")
        
        backup_data = await self.file_manager.restore_backup(backup_path)
        if not backup_data:
            print(f"{Fore.RED}Failed to load backup file{Style.RESET_ALL}")
            return 1
        
        # Extract backup data
        backup_followers = set(backup_data.get('followers', []))
        backup_following = set(backup_data.get('following', []))
        
        print(f"Backup contains:")
        print(f"  Followers: {len(backup_followers)}")
        print(f"  Following: {len(backup_following)}")
        
        # Get current state
        print(f"\n{Fore.CYAN}Analyzing current state...{Style.RESET_ALL}")
        current_followers = set(await self.github_api.get_followers())
        current_following = set(await self.github_api.get_following())
        
        print(f"Current state:")
        print(f"  Followers: {len(current_followers)}")
        print(f"  Following: {len(current_following)}")
        
        # Calculate differences
        users_to_follow = backup_following - current_following
        users_to_unfollow = current_following - backup_following
        
        print(f"\n{Fore.CYAN}Restore analysis:{Style.RESET_ALL}")
        print(f"  Users to follow: {len(users_to_follow)}")
        print(f"  Users to unfollow: {len(users_to_unfollow)}")
        
        if not users_to_follow and not users_to_unfollow:
            print(f"{Fore.GREEN}Your current following state matches the backup!{Style.RESET_ALL}")
            return 0
        
        # Show changes preview
        if users_to_follow:
            print(f"\n{Fore.GREEN}Users to follow (first 10):{Style.RESET_ALL}")
            for username in list(users_to_follow)[:10]:
                print(f"  + {username}")
            if len(users_to_follow) > 10:
                print(f"  ... and {len(users_to_follow) - 10} more")
        
        if users_to_unfollow:
            print(f"\n{Fore.RED}Users to unfollow (first 10):{Style.RESET_ALL}")
            for username in list(users_to_unfollow)[:10]:
                print(f"  - {username}")
            if len(users_to_unfollow) > 10:
                print(f"  ... and {len(users_to_unfollow) - 10} more")
        
        # Confirmation
        confirm = input(f"\n{Fore.YELLOW}Proceed with restore operation? (y/N): {Style.RESET_ALL}")
        if confirm.lower() != 'y':
            print(f"{Fore.YELLOW}Restore cancelled{Style.RESET_ALL}")
            return 0
        
        # Execute restore operations
        total_operations = len(users_to_follow) + len(users_to_unfollow)
        success_count = 0
        error_count = 0
        
        if users_to_follow:
            print(f"\n{Fore.CYAN}Following users from backup...{Style.RESET_ALL}")
            with tqdm(total=len(users_to_follow), desc="Following users") as pbar:
                for username in users_to_follow:
                    if await self.github_api.follow_user(username):
                        success_count += 1
                        print(f"{Fore.GREEN}✓ Followed {username}{Style.RESET_ALL}")
                    else:
                        error_count += 1
                        print(f"{Fore.RED}✗ Failed to follow {username}{Style.RESET_ALL}")
                    pbar.update(1)
        
        if users_to_unfollow:
            print(f"\n{Fore.CYAN}Unfollowing users not in backup...{Style.RESET_ALL}")
            with tqdm(total=len(users_to_unfollow), desc="Unfollowing users") as pbar:
                for username in users_to_unfollow:
                    if await self.github_api.unfollow_user(username):
                        success_count += 1
                        print(f"{Fore.GREEN}✓ Unfollowed {username}{Style.RESET_ALL}")
                    else:
                        error_count += 1
                        print(f"{Fore.RED}✗ Failed to unfollow {username}{Style.RESET_ALL}")
                    pbar.update(1)
        
        # Summary
        print(f"\n{Fore.CYAN}═══ Restore Summary ═══{Style.RESET_ALL}")
        print(f"✅ Successful operations: {success_count}")
        print(f"❌ Failed operations: {error_count}")
        print(f"📊 Total operations: {total_operations}")
        
        if error_count == 0:
            print(f"\n{Fore.GREEN}Backup restore completed successfully!{Style.RESET_ALL}")
            return 0
        else:
            print(f"\n{Fore.YELLOW}Backup restore completed with {error_count} errors.{Style.RESET_ALL}")
            return 1
    
    async def list_backups(self) -> int:
        """List available backup files"""
        backups = await self.file_manager.list_backups()
        
        if not backups:
            print(f"{Fore.YELLOW}No backup files found{Style.RESET_ALL}")
            return 0
        
        print(f"{Fore.CYAN}Available backups:{Style.RESET_ALL}")
        print(f"{'Name':<30} {'Size':<10} {'Modified':<20}")
        print("-" * 62)
        
        for backup in backups:
            print(f"{backup['name']:<30} {backup['size']:<10} {backup['modified']:<20}")
        
        return 0
    
    async def run_legacy_bulk_private(self) -> int:
        """Run legacy git-bulk-private functionality"""
        print(f"{Fore.CYAN}Running legacy bulk private repository operation...{Style.RESET_ALL}")
        
        try:
            repos = await self.github_api.get_user_repositories()
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
                    
                    if await self.github_api.update_repository_visibility(repo_name, private=True):
                        successful += 1
                        print(f"{Fore.GREEN}✓ Made {repo_name} private{Style.RESET_ALL}")
                    else:
                        failed += 1
                        print(f"{Fore.RED}✗ Failed to update {repo_name}{Style.RESET_ALL}")
                    
                    pbar.update(1)
            
            print(f"\n{Fore.CYAN}Repository Privacy Update Summary:{Style.RESET_ALL}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            
            return 0 if failed == 0 else 1
        
        except Exception as e:
            self.logger.error(f"Error in legacy bulk private operation: {e}")
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
            return 1
    
    async def repository_manager(self, make_private: bool = False, make_public: bool = False, 
                          filter_type: str = 'all') -> int:
        """Enhanced repository visibility management with interactive selection"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║              Github-Repository-Manager               ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║                  by RafalW3bCraft                          ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Check repository permissions first
        print(f"{Fore.CYAN}Checking repository access permissions...{Style.RESET_ALL}")
        permissions = await self.github_api.check_repository_permissions()
        
        if not permissions['can_read_public']:
            print(f"{Fore.RED}Unable to read repositories. Please check your GitHub token.{Style.RESET_ALL}")
            return 1
        
        if not permissions['can_read_private']:
            print(f"{Fore.YELLOW}Warning: Cannot access private repositories. Token may lack 'repo' scope.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Only public repositories will be shown.{Style.RESET_ALL}")
        
        # Get all repositories
        print(f"{Fore.CYAN}Fetching your repositories...{Style.RESET_ALL}")
        repos = await self.github_api.get_user_repositories()
        
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
            return await self._bulk_visibility_operation(filtered_repos, target_visibility)
        
        # Interactive mode - display repositories with selection
        return await self._interactive_repository_selection(filtered_repos)
    
    async def _interactive_repository_selection(self, repos: List[Dict[str, Any]]) -> int:
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
                return await self._process_selected_repositories(selected_repos)
                
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
    
    async def _process_selected_repositories(self, selected_repos: List[Dict[str, Any]]) -> int:
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
                    return await self._bulk_visibility_operation(selected_repos, 'private')
                elif choice == '2':
                    return await self._bulk_visibility_operation(selected_repos, 'public')
                elif choice == '3':
                    return await self._toggle_repository_visibility(selected_repos)
                elif choice == '4':
                    return await self._show_repository_details(selected_repos)
                elif choice == '5':
                    print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                    return 0
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter 1-5{Style.RESET_ALL}")
                    
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return 0
    
    async def _bulk_visibility_operation(self, repos: List[Dict[str, Any]], target_visibility: str) -> int:
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
                
                if await self.github_api.update_repository_visibility(repo_name, private=is_private):
                    successful += 1
                    status_icon = "🔒" if is_private else "🌐"
                    print(f"{Fore.GREEN}✓ {status_icon} {repo_name} → {action}{Style.RESET_ALL}")
                else:
                    failed += 1
                    print(f"{Fore.RED}✗ Failed to update {repo_name}{Style.RESET_ALL}")
                
                pbar.update(1)
        
        # Summary
        print(f"\n{Fore.CYAN}═══ Operation Summary ═══{Style.RESET_ALL}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total processed: {len(repos_to_change)}")
        
        if successful > 0:
            print(f"\n{Fore.GREEN}Successfully updated {successful} repositories to {action}!{Style.RESET_ALL}")
        
        return 0 if failed == 0 else 1
    
    async def _toggle_repository_visibility(self, repos: List[Dict[str, Any]]) -> int:
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
                
                if await self.github_api.update_repository_visibility(repo_name, private=new_private):
                    successful += 1
                    status_icon = "🔒" if new_private else "🌐"
                    print(f"{Fore.GREEN}✓ {status_icon} {repo_name} → {new_visibility}{Style.RESET_ALL}")
                else:
                    failed += 1
                    print(f"{Fore.RED}✗ Failed to toggle {repo_name}{Style.RESET_ALL}")
                
                pbar.update(1)
        
        # Summary
        print(f"\n{Fore.CYAN}═══ Toggle Summary ═══{Style.RESET_ALL}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total processed: {len(repos)}")
        
        return 0 if failed == 0 else 1
    
    async def _show_repository_details(self, repos: List[Dict[str, Any]]) -> int:
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
    
    async def _execute_follow_operation(self, usernames: List[str], operation_name: str) -> int:
        """Execute follow operation with concurrent batch processing for maximum speed"""
        successful = 0
        failed = 0
        start_time = time.time()
        
        # Batch size for concurrent operations - maximized for speed (GitHub allows up to 5000 req/hour)
        batch_size = 25
        
        async def follow_user_safe(username: str):
            """Safely follow a user and return result"""
            try:
                result = await self.github_api.follow_user(username)
                return username, result
            except Exception as e:
                self.logger.error(f"Error following {username}: {e}")
                return username, False
        
        # Process in batches for optimal performance
        with tqdm(total=len(usernames), desc=f"Following users ({operation_name})") as pbar:
            for i in range(0, len(usernames), batch_size):
                batch = usernames[i:i + batch_size]
                
                try:
                    # Execute batch concurrently for maximum speed
                    tasks = [follow_user_safe(username) for username in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Process results
                    for result in results:
                        if isinstance(result, Exception):
                            failed += 1
                            pbar.update(1)
                            continue
                        
                        username, success = result
                        pbar.set_postfix_str(f"Batch processed")
                        
                        if success:
                            successful += 1
                            print(f"{Fore.GREEN}✓ Followed {username}{Style.RESET_ALL}")
                        else:
                            failed += 1
                            print(f"{Fore.RED}✗ Failed to follow {username}{Style.RESET_ALL}")
                        
                        pbar.update(1)
                
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
                    break
        
        # Calculate and display performance metrics
        total_time = time.time() - start_time
        operations_per_second = len(usernames) / total_time if total_time > 0 else 0
        
        self._print_operation_summary(f"Auto-follow ({operation_name})", successful, failed, 0)
        print(f"{Fore.CYAN}⚡ Performance: {operations_per_second:.1f} operations/second{Style.RESET_ALL}")
        print(f"{Fore.CYAN}⏱️  Total time: {total_time:.2f} seconds{Style.RESET_ALL}")
        return 0 if failed == 0 else 1
    
    async def _execute_unfollow_operation(self, usernames: List[str], operation_name: str) -> int:
        """Execute unfollow operation with concurrent batch processing for maximum speed"""
        successful = 0
        failed = 0
        start_time = time.time()
        
        # Batch size for concurrent operations - maximized for speed (GitHub allows up to 5000 req/hour)
        batch_size = 25
        
        async def unfollow_user_safe(username: str):
            """Safely unfollow a user and return result"""
            try:
                result = await self.github_api.unfollow_user(username)
                return username, result
            except Exception as e:
                self.logger.error(f"Error unfollowing {username}: {e}")
                return username, False
        
        # Process in batches for optimal performance
        with tqdm(total=len(usernames), desc=f"Unfollowing users ({operation_name})") as pbar:
            for i in range(0, len(usernames), batch_size):
                batch = usernames[i:i + batch_size]
                
                try:
                    # Execute batch concurrently for maximum speed
                    tasks = [unfollow_user_safe(username) for username in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Process results
                    for result in results:
                        if isinstance(result, Exception):
                            failed += 1
                            pbar.update(1)
                            continue
                        
                        username, success = result
                        pbar.set_postfix_str(f"Batch processed")
                        
                        if success:
                            successful += 1
                            print(f"{Fore.GREEN}✓ Unfollowed {username}{Style.RESET_ALL}")
                        else:
                            failed += 1
                            print(f"{Fore.RED}✗ Failed to unfollow {username}{Style.RESET_ALL}")
                        
                        pbar.update(1)
                
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
                    break
        
        # Calculate and display performance metrics
        total_time = time.time() - start_time
        operations_per_second = len(usernames) / total_time if total_time > 0 else 0
        
        self._print_operation_summary(f"Unfollow ({operation_name})", successful, failed, 0)
        print(f"{Fore.CYAN}⚡ Performance: {operations_per_second:.1f} operations/second{Style.RESET_ALL}")
        print(f"{Fore.CYAN}⏱️  Total time: {total_time:.2f} seconds{Style.RESET_ALL}")
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
    
    async def debug_repository_access(self) -> int:
        """Debug repository access and permissions"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║         Repository Access Debug         ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Check basic authentication
        print(f"{Fore.CYAN}1. Testing GitHub authentication...{Style.RESET_ALL}")
        if await self.github_api.validate_token():
            print(f"{Fore.GREEN}✓ Authentication successful{Style.RESET_ALL}")
            print(f"  Username: {self.github_api.username}")
        else:
            print(f"{Fore.RED}✗ Authentication failed{Style.RESET_ALL}")
            return 1
        
        # Check token scopes
        print(f"\n{Fore.CYAN}2. Checking token scopes...{Style.RESET_ALL}")
        try:
            response = await self.github_api._make_request('GET', '/user')
            if response.status == 200:
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
                print(f"{Fore.RED}✗ Cannot check scopes: {response.status}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ Error checking scopes: {e}{Style.RESET_ALL}")
        
        # Check repository permissions
        print(f"\n{Fore.CYAN}3. Testing repository access...{Style.RESET_ALL}")
        permissions = await self.github_api.check_repository_permissions()
        
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
                response = await self.github_api._make_request('GET', endpoint, params={'per_page': 1})
                if response.status == 200:
                    data = await response.json()
                    print(f"  {Fore.GREEN}✓ {description}: {len(data)} repos found{Style.RESET_ALL}")
                else:
                    print(f"  {Fore.RED}✗ {description}: HTTP {response.status}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}✗ Repository listing error: {e}{Style.RESET_ALL}")
        
        # Test actual repository fetching
        print(f"\n{Fore.CYAN}5. Testing full repository fetch...{Style.RESET_ALL}")
        try:
            repos = await self.github_api.get_user_repositories()
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
            rate_limit = await self.github_api.get_rate_limit_status()
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
    
    async def toggle_repositories_visibility(self, filter_type: str = 'all') -> int:
        """Toggle visibility of selected repositories"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║         Repository Visibility Toggle     ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
        
        # Get repositories with permission checking
        permissions = await self.github_api.check_repository_permissions()
        
        print(f"{Fore.CYAN}Fetching repositories...{Style.RESET_ALL}")
        repos = await self.github_api.get_user_repositories()
        
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
        return await self._toggle_repository_visibility(selected_repos)
    
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
    
    async def create_repository(self, name: str, description: str = "", private: bool = True) -> int:
        """Create a new repository"""
        print(f"{Fore.CYAN}Creating repository '{name}'...{Style.RESET_ALL}")
        
        try:
            repo_data = await self.github_api.create_repository(
                name=name,
                description=description,
                private=private,
                auto_init=True
            )
            
            if repo_data:
                print(f"{Fore.GREEN}✓ Repository created successfully!{Style.RESET_ALL}")
                print(f"  Name: {repo_data['name']}")
                print(f"  URL: {repo_data['html_url']}")
                print(f"  Clone URL: {repo_data['clone_url']}")
                print(f"  Visibility: {'Private' if repo_data['private'] else 'Public'}")
                return 0
            else:
                print(f"{Fore.RED}Failed to create repository{Style.RESET_ALL}")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error creating repository: {e}")
            print(f"{Fore.RED}Error creating repository: {e}{Style.RESET_ALL}")
            return 1
    
    async def clone_repository(self, repo_url: str, local_path: str = "") -> int:
        """Clone a repository"""
        print(f"{Fore.CYAN}Cloning repository from {repo_url}...{Style.RESET_ALL}")
        
        try:
            success = await self.github_api.clone_repository(repo_url, local_path)
            
            if success:
                final_path = local_path or f"./cloned_repos/{repo_url.split('/')[-1].replace('.git', '')}"
                print(f"{Fore.GREEN}✓ Repository cloned successfully to {final_path}{Style.RESET_ALL}")
                return 0
            else:
                print(f"{Fore.RED}Failed to clone repository{Style.RESET_ALL}")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error cloning repository: {e}")
            print(f"{Fore.RED}Error cloning repository: {e}{Style.RESET_ALL}")
            return 1
    
    async def search_users_advanced(self, min_followers: int = 100, min_repos: int = 5, 
                             language: str = "", location: str = "", limit: int = 50) -> int:
        """Search users by followers, repositories, and other criteria"""
        print(f"{Fore.CYAN}Searching for users with advanced criteria...{Style.RESET_ALL}")
        print(f"  Min followers: {min_followers}")
        print(f"  Min repositories: {min_repos}")
        if language:
            print(f"  Language: {language}")
        if location:
            print(f"  Location: {location}")
        
        try:
            users = await self.github_api.search_users_by_criteria(
                min_followers=min_followers,
                min_repos=min_repos,
                language=language,
                location=location,
                per_page=limit
            )
            
            if not users:
                print(f"{Fore.YELLOW}No users found matching criteria{Style.RESET_ALL}")
                return 0
            
            print(f"\n{Fore.GREEN}Found {len(users)} users:{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Fetching detailed user information...{Style.RESET_ALL}")
            
            # Fetch detailed info for each user
            user_details = []
            with tqdm(total=len(users), desc="Getting user details") as pbar:
                for user in users:
                    username = user['login']
                    
                    # Get detailed user information
                    detailed_user = await self.github_api.get_user_info(username)
                    
                    if detailed_user:
                        user_info = {
                            'username': username,
                            'followers': detailed_user.get('followers', 0),
                            'following': detailed_user.get('following', 0),
                            'repos': detailed_user.get('public_repos', 0),
                            'gists': detailed_user.get('public_gists', 0),
                            'location': detailed_user.get('location', '') or '',
                            'company': detailed_user.get('company', '') or '',
                            'blog': detailed_user.get('blog', '') or '',
                            'twitter': detailed_user.get('twitter_username', '') or '',
                            'bio': detailed_user.get('bio', '') or '',
                            'created_at': detailed_user.get('created_at', ''),
                            'updated_at': detailed_user.get('updated_at', ''),
                            'hireable': detailed_user.get('hireable', False)
                        }
                        
                        # Get additional data: starred repos and most used language
                        starred_count = await self._get_user_starred_count(username)
                        most_used_lang = await self._get_user_top_language(username)
                        last_activity = await self._get_user_last_activity(username)
                        
                        user_info.update({
                            'starred': starred_count,
                            'top_language': most_used_lang,
                            'last_active': last_activity
                        })
                        
                        user_details.append(user_info)
                    else:
                        user_details.append({'username': username, 'error': True})
                    
                    pbar.update(1)
            
            # Display enhanced user information
            self._display_enhanced_user_results(user_details)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error searching users: {e}")
            print(f"{Fore.RED}Error searching users: {e}{Style.RESET_ALL}")
            return 1
    
    async def _get_user_starred_count(self, username: str) -> int:
        """Get count of repositories starred by user"""
        try:
            starred_repos = await self.github_api.get_user_starred_repos(username, per_page=1)
            if starred_repos:
                # Get total count from headers if available, otherwise make additional calls
                return len(starred_repos) if len(starred_repos) < 100 else await self._count_all_starred(username)
            return 0
        except Exception as e:
            self.logger.debug(f"Error getting starred count for {username}: {e}")
            return 0
    
    async def _count_all_starred(self, username: str) -> int:
        """Count all starred repositories (for users with >100 stars)"""
        try:
            count = 0
            page = 1
            while True:
                starred_repos = await self.github_api.get_user_starred_repos(username, per_page=100)
                if not starred_repos:
                    break
                count += len(starred_repos)
                if len(starred_repos) < 100:
                    break
                page += 1
                if page > 10:  # Limit to prevent excessive API calls
                    count = f"{count}+"
                    break
            return count
        except Exception:
            return 0
    
    async def _get_user_top_language(self, username: str) -> str:
        """Get user's most used programming language"""
        try:
            repos = await self.github_api.get_user_repositories(username)
            if not repos:
                return ""
            
            # Count languages from repositories
            language_count = {}
            for repo in repos[:20]:  # Limit to first 20 repos for performance
                language = repo.get('language')
                if language:
                    language_count[language] = language_count.get(language, 0) + 1
            
            if language_count:
                return max(language_count, key=language_count.get)
            return ""
        except Exception as e:
            self.logger.debug(f"Error getting top language for {username}: {e}")
            return ""
    
    async def _get_user_last_activity(self, username: str) -> str:
        """Get user's last activity date"""
        try:
            repos = await self.github_api.get_user_repositories(username)
            if not repos:
                return ""
            
            # Find the most recently updated repository
            latest_update = None
            for repo in repos[:10]:  # Check first 10 repos
                pushed_at = repo.get('pushed_at')
                if pushed_at:
                    from datetime import datetime
                    try:
                        update_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
                        if not latest_update or update_date > latest_update:
                            latest_update = update_date
                    except ValueError:
                        continue
            
            if latest_update:
                from datetime import datetime, timezone
                days_ago = (datetime.now(timezone.utc) - latest_update).days
                if days_ago == 0:
                    return "Today"
                elif days_ago == 1:
                    return "Yesterday"
                elif days_ago < 7:
                    return f"{days_ago}d ago"
                elif days_ago < 30:
                    return f"{days_ago//7}w ago"
                elif days_ago < 365:
                    return f"{days_ago//30}m ago"
                else:
                    return f"{days_ago//365}y ago"
            return ""
        except Exception as e:
            self.logger.debug(f"Error getting last activity for {username}: {e}")
            return ""
    
    def _display_enhanced_user_results(self, user_details: List[Dict[str, Any]]):
        """Display enhanced user search results"""
        if not user_details:
            return
        
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║                                  USER SEARCH RESULTS                                 ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        for i, user in enumerate(user_details, 1):
            if user.get('error'):
                print(f"\n{Fore.RED}❌ {user['username']} - Error fetching data{Style.RESET_ALL}")
                continue
            
            # Header with username and basic stats
            username = user['username']
            followers = self._format_number(user.get('followers', 0))
            following = self._format_number(user.get('following', 0))
            repos = self._format_number(user.get('repos', 0))
            
            print(f"\n{Fore.YELLOW}┌─ {i:2d}. @{username} {Style.RESET_ALL}")
            print(f"{Fore.GREEN}   👥 {followers} followers  •  👤 {following} following  •  📚 {repos} repos{Style.RESET_ALL}")
            
            # Stars and language
            starred = self._format_number(user.get('starred', 0))
            top_lang = user.get('top_language', '')
            last_active = user.get('last_active', '')
            
            print(f"{Fore.CYAN}   ⭐ {starred} starred", end="")
            if top_lang:
                print(f"  •  💻 {top_lang}", end="")
            if last_active:
                print(f"  •  🕒 {last_active}", end="")
            print(f"{Style.RESET_ALL}")
            
            # Location and company
            location = user.get('location', '').strip()
            company = user.get('company', '').strip()
            if location or company:
                print(f"{Fore.MAGENTA}   ", end="")
                if location:
                    print(f"📍 {location[:30]}", end="")
                    if company:
                        print(f"  •  🏢 {company[:25]}", end="")
                elif company:
                    print(f"🏢 {company[:30]}", end="")
                print(f"{Style.RESET_ALL}")
            
            # Social links
            social_links = []
            blog = user.get('blog', '').strip()
            twitter = user.get('twitter', '').strip()
            
            if blog:
                if not blog.startswith(('http://', 'https://')):
                    blog = f"https://{blog}"
                social_links.append(f"🌐 {blog[:35]}")
            if twitter:
                social_links.append(f"🐦 @{twitter}")
            
            if social_links:
                print(f"{Fore.BLUE}   {' • '.join(social_links)}{Style.RESET_ALL}")
            
            # Bio
            bio = user.get('bio', '').strip()
            if bio:
                bio_short = bio[:80] + "..." if len(bio) > 80 else bio
                print(f"{Fore.WHITE}   💬 {bio_short}{Style.RESET_ALL}")
            
            # Hireable status
            if user.get('hireable'):
                print(f"{Fore.GREEN}   ✅ Available for hire{Style.RESET_ALL}")
            
            # Account age
            created_at = user.get('created_at', '')
            if created_at:
                try:
                    from datetime import datetime
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    years_on_github = (datetime.now().year - created_date.year)
                    if years_on_github > 0:
                        print(f"{Fore.YELLOW}   📅 {years_on_github} years on GitHub{Style.RESET_ALL}")
                except:
                    pass
        
        print(f"\n{Fore.CYAN}Found {len([u for u in user_details if not u.get('error')])} users with complete data{Style.RESET_ALL}")
    
    def _format_number(self, num: int) -> str:
        """Format numbers for display (e.g., 1.2k, 5.3m)"""
        if isinstance(num, str):
            return num
        if num >= 1000000:
            return f"{num/1000000:.1f}m"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        else:
            return str(num)
