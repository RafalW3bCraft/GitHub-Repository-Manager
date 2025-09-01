import os
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import random
import asyncio
from pathlib import Path
from tqdm import tqdm
from colorama import Fore, Style


class GitHubActivityGenerator:
    """Generate GitHub activity history with backdated commits"""
    
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger
        self.temp_repo_path = None
        
    async def get_account_creation_date(self) -> str:
        """Get the authenticated user's account creation date"""
        try:
            user_info = await self.github_api.get_user_info()
            if user_info and 'created_at' in user_info:
                # Parse GitHub ISO format and return as YYYY-MM-DD
                created_at = user_info['created_at']
                # GitHub returns format like "2023-02-27T06:10:10Z"
                date_part = created_at.split('T')[0]
                self.logger.info(f"Account created on: {date_part}")
                return date_part
            else:
                # Fallback to known creation date
                fallback_date = "2023-02-27"
                self.logger.warning(f"Could not fetch creation date, using fallback: {fallback_date}")
                return fallback_date
        except Exception as e:
            self.logger.error(f"Error fetching account creation date: {e}")
            return "2023-02-27"  # Your known creation date
    
    def generate_commit_times(self, date: datetime, num_commits: int, randomize: bool = True) -> list:
        """Generate realistic commit times for a given day"""
        if not randomize:
            # Evenly distribute commits throughout the day
            times = []
            hours_interval = 24 / num_commits
            for i in range(num_commits):
                hour = int(i * hours_interval)
                minute = random.randint(0, 59)
                times.append(date.replace(hour=hour, minute=minute, second=random.randint(0, 59)))
            return times
        
        # Randomize times with realistic patterns
        times = []
        
        # Define realistic time ranges (avoid very early morning)
        if date.weekday() < 5:  # Weekday
            # More activity during work hours
            work_hours = [(9, 12), (13, 17), (19, 23)]
            weights = [0.4, 0.4, 0.2]
        else:  # Weekend
            # More relaxed schedule
            work_hours = [(10, 14), (15, 20), (21, 23)]
            weights = [0.3, 0.5, 0.2]
        
        for _ in range(num_commits):
            # Choose time range based on weights
            time_range = random.choices(work_hours, weights=weights)[0]
            hour = random.randint(time_range[0], time_range[1])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            commit_time = date.replace(hour=hour, minute=minute, second=second)
            times.append(commit_time)
        
        # Sort times chronologically
        times.sort()
        return times
    
    def generate_commit_message(self, commit_time: datetime, commit_index: int) -> str:
        """Generate realistic commit messages"""
        messages = [
            f"Daily activity update {commit_time.strftime('%Y-%m-%d %H:%M')}",
            f"Backdated commit {commit_time.strftime('%Y-%m-%d %H:%M')}",
            f"Activity log entry {commit_time.strftime('%m/%d %H:%M')}",
            f"Contribution {commit_time.strftime('%Y-%m-%d')} #{commit_index + 1}",
            f"GitHub activity {commit_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Daily commit {commit_time.strftime('%Y-%m-%d')} - entry {commit_index + 1}",
        ]
        return random.choice(messages)
    
    def generate_file_content(self, commit_time: datetime, commit_index: int) -> str:
        """Generate varied file content to make commits look more realistic"""
        activities = [
            f"Activity recorded at {commit_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Commit #{commit_index + 1} on {commit_time.strftime('%A, %B %d, %Y at %H:%M')}",
            f"GitHub contribution logged: {commit_time.isoformat()}",
            f"Daily progress update - {commit_time.strftime('%Y-%m-%d %H:%M')}",
            f"Backdated activity entry: {commit_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Repository activity: {commit_time.strftime('%Y-%m-%d')} commit {commit_index + 1}",
        ]
        
        return random.choice(activities)
    
    async def create_repository(self, repo_name: str = "github_activity") -> bool:
        """Create the GitHub repository if it doesn't exist"""
        try:
            # Check if repository already exists
            response = await self.github_api._make_request('GET', f'/repos/{self.github_api.username}/{repo_name}')
            
            if response.status == 200:
                self.logger.info(f"Repository '{repo_name}' already exists")
                return True
            elif response.status == 404:
                # Repository doesn't exist, create it
                repo_data = {
                    "name": repo_name,
                    "description": "GitHub activity history generator",
                    "private": False,
                    "auto_init": False
                }
                
                create_response = await self.github_api._make_request('POST', '/user/repos', json=repo_data)
                
                if create_response.status == 201:
                    self.logger.info(f"Successfully created repository '{repo_name}'")
                    return True
                else:
                    self.logger.error(f"Failed to create repository: {create_response.status}")
                    return False
            else:
                self.logger.error(f"Error checking repository: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error creating repository: {e}")
            return False
    
    def setup_git_repo(self, repo_name: str) -> str:
        """Set up local git repository"""
        # Create temporary directory
        self.temp_repo_path = tempfile.mkdtemp(prefix="github_activity_")
        os.chdir(self.temp_repo_path)
        
        # Initialize git repository
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", self.github_api.username], check=True)
        subprocess.run(["git", "config", "user.email", f"{self.github_api.username}@users.noreply.github.com"], check=True)
        
        # Add remote with authentication
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN not found in environment")
        
        remote_url = f"https://{token}@github.com/{self.github_api.username}/{repo_name}.git"
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True, capture_output=True)
        
        # Create initial file
        with open("activity_log.txt", "w") as f:
            f.write(f"GitHub Activity Log for {self.github_api.username}\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
        
        return self.temp_repo_path
    
    def create_backdated_commit(self, commit_time: datetime, message: str, content: str):
        """Create a commit with backdated timestamp"""
        # Update activity log file
        with open("activity_log.txt", "a") as f:
            f.write(f"{content}\n")
        
        # Set environment variables for git
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = commit_time.isoformat()
        env["GIT_COMMITTER_DATE"] = commit_time.isoformat()
        
        # Add and commit
        subprocess.run(["git", "add", "activity_log.txt"], env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], env=env, check=True, capture_output=True)
    
    async def push_commits(self, repo_name: str):
        """Push all commits to GitHub"""
        try:
            # Create main branch and push
            subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)
            
            # Push with progress
            self.logger.info(f"Pushing commits to {repo_name}...")
            result = subprocess.run(
                ["git", "push", "-u", "origin", "main", "--force"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully pushed all commits to {repo_name}")
                return True
            else:
                self.logger.error(f"Push failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error pushing commits: {e}")
            return False
    
    def cleanup_temp_repo(self):
        """Clean up temporary repository"""
        if self.temp_repo_path and os.path.exists(self.temp_repo_path):
            try:
                shutil.rmtree(self.temp_repo_path)
                self.logger.debug("Cleaned up temporary repository")
            except Exception as e:
                self.logger.warning(f"Could not clean up temp repo: {e}")
    
    async def generate_activity(self, start_date: str, end_date: str, max_commits_per_day: int = 10, 
                              repo_name: str = "github_activity") -> bool:
        """Main function to generate GitHub activity"""
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            if start_dt > end_dt:
                self.logger.error("Start date must be before end date")
                return False
            
            # Calculate estimated total commits (will be random per day)
            total_days = (end_dt - start_dt).days + 1
            min_commits_per_day = 3
            avg_commits = (min_commits_per_day + max_commits_per_day) // 2
            estimated_commits = total_days * avg_commits
            
            print(f"\n{Fore.CYAN}=== Activity Generation Plan ==={Style.RESET_ALL}")
            print(f"Date Range: {start_date} to {end_date} ({total_days} days)")
            print(f"Commits per day: {min_commits_per_day} to {max_commits_per_day} (random)")
            print(f"Estimated total commits: ~{estimated_commits:,}")
            print(f"Repository: {repo_name}")
            
            # Create repository
            if not await self.create_repository(repo_name):
                return False
            
            # Set up local git repository
            self.setup_git_repo(repo_name)
            
            # Generate commits day by day
            current_date = start_dt
            commit_count = 0
            
            with tqdm(total=total_days, desc="Generating commits", unit="days") as pbar:
                while current_date <= end_dt:
                    # Randomly choose commits for this day (between 3 and max)
                    daily_commits = random.randint(3, max_commits_per_day)
                    
                    # Generate commit times for this day
                    commit_times = self.generate_commit_times(current_date, daily_commits, True)
                    
                    # Create commits for this day
                    for i, commit_time in enumerate(commit_times):
                        message = self.generate_commit_message(commit_time, i)
                        content = self.generate_file_content(commit_time, i)
                        
                        self.create_backdated_commit(commit_time, message, content)
                        commit_count += 1
                    
                    current_date += timedelta(days=1)
                    pbar.update(1)
                    pbar.set_postfix(commits=commit_count, daily=daily_commits)
            
            # Push to GitHub
            success = await self.push_commits(repo_name)
            
            if success:
                print(f"\n{Fore.GREEN}✓ Successfully generated {commit_count:,} commits{Style.RESET_ALL}")
                print(f"{Fore.GREEN}✓ Repository: https://github.com/{self.github_api.username}/{repo_name}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}✓ Contribution graph updated{Style.RESET_ALL}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error generating activity: {e}")
            return False
        finally:
            self.cleanup_temp_repo()