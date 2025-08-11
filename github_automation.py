#!/usr/bin/env python3
"""
GitHub Automation Suite - Enhanced CLI tool for GitHub follow/unfollow operations
Extends gitMaster-init with advanced automation capabilities
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional, List
import colorama
from colorama import Fore, Style

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.github_api import GitHubAPI
from core.file_manager import FileManager
from core.logger import Logger
from core.validators import Validators
from cli.commands import Commands
from cli.interactive import InteractiveMode

# Initialize colorama for cross-platform colored output
colorama.init(autoreset=True)

class GitHubAutomation:
    """Main application class for GitHub automation suite"""
    
    def __init__(self):
        self.logger = Logger()
        self.validators = Validators()
        self.file_manager = FileManager()
        self.github_api: Optional[GitHubAPI] = None
        self.commands: Optional[Commands] = None
        
    def initialize_api(self) -> bool:
        """Initialize GitHub API connection with validation"""
        try:
            self.github_api = GitHubAPI()
            if not self.github_api.validate_token():
                self.logger.error("GitHub token validation failed")
                return False
            
            self.commands = Commands(self.github_api, self.file_manager, self.logger)
            self.logger.info("GitHub API initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GitHub API: {e}")
            return False
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create comprehensive argument parser with subcommands"""
        parser = argparse.ArgumentParser(
            description="gitMaster-init v1.0.0 - Advanced GitHub Repository Management by RafalW3bCraft",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
GitMaster-init Unified Examples:
  # Repository Management
  %(prog)s repo-manager                          # Interactive repository selection
  %(prog)s repo-manager --make-private           # Bulk make repositories private
  %(prog)s repo-manager --make-public            # Bulk make repositories public
  %(prog)s repo-manager --filter public          # Show only public repositories
  %(prog)s repo-manager --toggle-visibility      # Toggle repository visibility
  
  # Automation (All via repo-manager)
  %(prog)s repo-manager --auto-follow octocat --limit 50
  %(prog)s repo-manager --unfollow-nonfollowers --whitelist data/whitelist.txt
  %(prog)s repo-manager --stats --stats-username octocat
  %(prog)s repo-manager --interactive
  %(prog)s repo-manager --backup-create
  
  # Debug & Diagnostics
  %(prog)s repo-manager --debug                  # Debug repository access

Author: RafalW3bCraft | License: MIT | GitHub: RafalW3bCraft/gitMaster-init
            """
        )
        
        # Global options
        parser.add_argument('--verbose', '-v', action='store_true',
                          help='Enable verbose logging')
        # Removed dry-run mode as per revision requirements
        parser.add_argument('--no-confirm', action='store_true',
                          help='Skip confirmation prompts')
        
        # Create subparsers for different commands
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # GitMaster-init Unified Repository Management Command
        repo_parser = subparsers.add_parser('repo-manager',
                                          help='GitMaster-init: Unified repository and automation management')
        
        # Repository visibility management options
        repo_visibility = repo_parser.add_argument_group('Repository Visibility Management')
        repo_visibility.add_argument('--make-private', action='store_true',
                                   help='Bulk make selected repositories private')
        repo_visibility.add_argument('--make-public', action='store_true',
                                   help='Bulk make selected repositories public')
        repo_visibility.add_argument('--toggle-visibility', action='store_true',
                                   help='Toggle visibility of selected repositories')
        repo_visibility.add_argument('--filter', choices=['all', 'public', 'private'],
                                   default='all', help='Filter repositories by visibility')
        
        # Automation features integrated into repo-manager
        automation = repo_parser.add_argument_group('Automation Features')
        automation.add_argument('--auto-follow', type=str, metavar='USERNAME',
                              help='Auto-follow followers of specified user')
        automation.add_argument('--limit', type=int, default=100,
                              help='Maximum users to follow (default: 100)')
        automation.add_argument('--filter-verified', action='store_true',
                              help='Only follow verified users')
        automation.add_argument('--min-followers', type=int, default=0,
                              help='Minimum followers required (default: 0)')
        
        automation.add_argument('--unfollow-nonfollowers', action='store_true',
                              help='Unfollow users who don\'t follow back')
        automation.add_argument('--whitelist', type=str,
                              help='Path to whitelist file (users to never unfollow)')
        automation.add_argument('--min-days', type=int, default=7,
                              help='Minimum days since following (default: 7)')
        
        automation.add_argument('--stats', action='store_true',
                              help='Show follow/follower statistics')
        automation.add_argument('--stats-username', type=str,
                              help='Username to analyze (default: authenticated user)')
        automation.add_argument('--detailed', action='store_true',
                              help='Show detailed statistics')
        
        automation.add_argument('--interactive', action='store_true',
                              help='Start interactive automation mode')
        
        # Backup management integrated
        backup = repo_parser.add_argument_group('Backup Management')
        backup.add_argument('--backup-create', action='store_true',
                          help='Create backup of current follow/follower state')
        backup.add_argument('--backup-restore', type=str,
                          help='Restore from backup file')
        backup.add_argument('--backup-list', action='store_true',
                          help='List available backups')
        
        # Debug command integrated into repo-manager
        debug = repo_parser.add_argument_group('Debug & Diagnostics')
        debug.add_argument('--debug', action='store_true',
                         help='Debug repository access and GitHub API permissions')
        
        # Legacy compatibility (deprecated - redirect to repo-manager)
        legacy_parser = subparsers.add_parser('legacy-bulk-private',
                                            help='DEPRECATED: Use "repo-manager" instead')
        
        # Standalone debug command (for backward compatibility)
        debug_parser = subparsers.add_parser('debug',
                                          help='Debug repository access and GitHub API permissions')
        
        return parser
    
    def run(self):
        """Main application entry point"""
        parser = self.create_parser()
        args = parser.parse_args()
        
        # Handle no command case
        if not args.command:
            parser.print_help()
            return 1
        
        # Set logging level
        if args.verbose:
            self.logger.set_level('DEBUG')
        
        # Initialize API connection
        if not self.initialize_api():
            print(f"{Fore.RED}Failed to initialize GitHub API. Check your token and connection.{Style.RESET_ALL}")
            return 1
        
        try:
            # Ensure commands is not None
            if not self.commands:
                print(f"{Fore.RED}Commands not initialized properly{Style.RESET_ALL}")
                return 1
            
            # Route to unified repo-manager command handler
            if args.command == 'repo-manager':
                return self._handle_unified_repo_manager(args)
            
            elif args.command == 'legacy-bulk-private':
                print(f"{Fore.YELLOW}WARNING: 'legacy-bulk-private' is deprecated. Use 'repo-manager' instead.{Style.RESET_ALL}")
                return self.commands.run_legacy_bulk_private()
            
            elif args.command == 'debug':
                return self.commands.debug_repository_access()
            
            else:
                parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
            return 130
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            print(f"{Fore.RED}An unexpected error occurred. Check logs for details.{Style.RESET_ALL}")
            return 1
    
    def _handle_unified_repo_manager(self, args) -> int:
        """Handle unified repo-manager command with all automation features"""
        # Determine which operation to perform based on provided arguments
        operations_count = 0
        
        # Check repository visibility operations
        if args.make_private:
            operations_count += 1
        if args.make_public:
            operations_count += 1
        if args.toggle_visibility:
            operations_count += 1
            
        # Check automation operations
        if args.auto_follow:
            operations_count += 1
        if args.unfollow_nonfollowers:
            operations_count += 1
        if args.stats:
            operations_count += 1
        if args.interactive:
            operations_count += 1
            
        # Check backup operations
        if args.backup_create:
            operations_count += 1
        if args.backup_restore:
            operations_count += 1
        if args.backup_list:
            operations_count += 1
            
        # Check debug operation
        if args.debug:
            operations_count += 1
        
        # If multiple operations specified, show error
        if operations_count > 1:
            print(f"{Fore.RED}Error: Only one operation can be performed at a time{Style.RESET_ALL}")
            print(f"Please specify only one of the available options.")
            return 1
        
        # If no specific operation, start interactive repository manager
        if operations_count == 0:
            if not self.commands:
                print(f"{Fore.RED}Commands not properly initialized{Style.RESET_ALL}")
                return 1
            return self.commands.repository_manager(
                make_private=False,
                make_public=False,
                filter_type=args.filter
            )
        
        # Handle specific operations
        try:
            # Ensure commands is initialized
            if not self.commands:
                print(f"{Fore.RED}Commands not properly initialized{Style.RESET_ALL}")
                return 1
            
            # Repository visibility operations
            if args.make_private:
                return self.commands.repository_manager(
                    make_private=True,
                    make_public=False,
                    filter_type=args.filter
                )
            
            elif args.make_public:
                return self.commands.repository_manager(
                    make_private=False,
                    make_public=True,
                    filter_type=args.filter
                )
            
            elif args.toggle_visibility:
                return self.commands.toggle_repositories_visibility(args.filter)
            
            # Automation operations
            elif args.auto_follow:
                return self.commands.auto_follow_followers(
                    args.auto_follow, args.limit, args.filter_verified,
                    args.min_followers
                )
            
            elif args.unfollow_nonfollowers:
                return self.commands.unfollow_non_followers(
                    args.whitelist, args.min_days, args.no_confirm
                )
            
            elif args.stats:
                return self.commands.show_statistics(args.stats_username, args.detailed)
            
            elif args.interactive:
                if not self.github_api:
                    print(f"{Fore.RED}GitHub API not initialized{Style.RESET_ALL}")
                    return 1
                interactive = InteractiveMode(self.github_api, self.file_manager, self.logger)
                return interactive.start()
            
            # Backup operations
            elif args.backup_create:
                return self.commands.create_backup()
            
            elif args.backup_restore:
                return self.commands.restore_backup(args.backup_restore)
            
            elif args.backup_list:
                return self.commands.list_backups()
            
            # Debug operation
            elif args.debug:
                return self.commands.debug_repository_access()
            
            else:
                # This should not happen due to operations_count check above
                print(f"{Fore.RED}Unknown operation{Style.RESET_ALL}")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error in repo-manager operation: {e}")
            print(f"{Fore.RED}Operation failed. Check logs for details.{Style.RESET_ALL}")
            return 1

def main():
    """Entry point for the application"""
    app = GitHubAutomation()
    return app.run()

if __name__ == "__main__":
    sys.exit(main())
