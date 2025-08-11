"""
GitHub API client with comprehensive error handling and rate limiting
"""

import os
import time
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .rate_limiter import RateLimiter
from .logger import Logger

class GitHubAPI:
    """GitHub API client with enhanced functionality"""
    
    def __init__(self):
        self.base_url = os.getenv('GITHUB_API_BASE_URL', 'https://api.github.com')
        self.token = os.getenv('GITHUB_TOKEN') or os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
        self.username = os.getenv('GITHUB_USERNAME')
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
        if not self.token:
            raise ValueError("GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN environment variable is required")
        
        self.logger = Logger()
        self.rate_limiter = RateLimiter()
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create configured requests session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Automation-Suite/2.0'
        })
        
        return session
    
    def validate_token(self) -> bool:
        """Validate GitHub token and check required scopes"""
        try:
            response = self._make_request('GET', '/user')
            if response.status_code == 200:
                user_data = response.json()
                if not self.username:
                    # Auto-detect username if not provided
                    self.username = user_data.get('login')
                    self.logger.info(f"Auto-detected username: {self.username}")
                
                # Check token scopes
                scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
                scopes = [scope.strip() for scope in scopes if scope.strip()]
                
                # Required scopes for different functionality
                required_scopes = ['user:follow']  # For follow/unfollow operations
                recommended_scopes = ['repo']      # For repository operations (private repos)
                
                missing_scopes = [scope for scope in required_scopes if scope not in scopes]
                missing_recommended = [scope for scope in recommended_scopes if scope not in scopes]
                
                if missing_scopes:
                    self.logger.error(f"Missing required scopes: {missing_scopes}")
                    return False
                
                if missing_recommended:
                    self.logger.warning(f"Missing recommended scopes for full functionality: {missing_recommended}")
                    self.logger.warning("Some features like private repository access may be limited")
                
                self.logger.info("GitHub token validation successful")
                return True
            else:
                self.logger.error(f"Token validation failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Token validation error: {e}")
            return False
    
    def check_repository_permissions(self) -> Dict[str, bool]:
        """Check what repository operations are available with current token"""
        permissions = {
            'can_read_public': False,
            'can_read_private': False,
            'can_write_repos': False
        }
        
        try:
            # Test reading public repositories
            response = self._make_request('GET', '/user/repos', params={'per_page': 1, 'visibility': 'public'})
            permissions['can_read_public'] = response.status_code == 200
            
            # Test reading private repositories
            response = self._make_request('GET', '/user/repos', params={'per_page': 1, 'visibility': 'private'})
            permissions['can_read_private'] = response.status_code == 200
            
            # Test repository write access (check token scopes)
            response = self._make_request('GET', '/user')
            if response.status_code == 200:
                scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
                scopes = [scope.strip() for scope in scopes if scope.strip()]
                permissions['can_write_repos'] = 'repo' in scopes or 'public_repo' in scopes
            
            self.logger.info(f"Repository permissions: {permissions}")
            return permissions
            
        except Exception as e:
            self.logger.error(f"Error checking repository permissions: {e}")
            return permissions
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make rate-limited API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            
            # Update rate limiter with response headers
            self.rate_limiter.update_from_headers(response.headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(reset_time - int(time.time()), 60)
                self.logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_request(method, endpoint, **kwargs)
            
            return response
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    def get_user_info(self, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user information"""
        username = username or self.username
        try:
            response = self._make_request('GET', f'/users/{username}')
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get user info for {username}: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None
    
    def get_followers(self, username: Optional[str] = None, per_page: int = 100) -> List[str]:
        """Get list of followers for a user"""
        username = username or self.username
        followers = []
        page = 1
        
        try:
            while True:
                response = self._make_request('GET', f'/users/{username}/followers', 
                                            params={'per_page': per_page, 'page': page})
                
                if response.status_code != 200:
                    self.logger.error(f"Failed to get followers: {response.status_code}")
                    break
                
                data = response.json()
                if not data:
                    break
                
                followers.extend([user['login'] for user in data])
                page += 1
                
                # GitHub API pagination limit check
                if len(data) < per_page:
                    break
            
            self.logger.info(f"Retrieved {len(followers)} followers for {username}")
            return followers
            
        except Exception as e:
            self.logger.error(f"Error getting followers: {e}")
            return []
    
    def get_following(self, username: Optional[str] = None, per_page: int = 100) -> List[str]:
        """Get list of users being followed"""
        username = username or self.username
        following = []
        page = 1
        
        try:
            while True:
                response = self._make_request('GET', f'/users/{username}/following',
                                            params={'per_page': per_page, 'page': page})
                
                if response.status_code != 200:
                    self.logger.error(f"Failed to get following: {response.status_code}")
                    break
                
                data = response.json()
                if not data:
                    break
                
                following.extend([user['login'] for user in data])
                page += 1
                
                if len(data) < per_page:
                    break
            
            self.logger.info(f"Retrieved {len(following)} following for {username}")
            return following
            
        except Exception as e:
            self.logger.error(f"Error getting following: {e}")
            return []
    
    def follow_user(self, username: str) -> bool:
        """Follow a user"""
        try:
            response = self._make_request('PUT', f'/user/following/{username}')
            
            if response.status_code == 204:
                self.logger.info(f"Successfully followed {username}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"User {username} not found")
                return False
            else:
                self.logger.error(f"Failed to follow {username}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error following {username}: {e}")
            return False
    
    def unfollow_user(self, username: str) -> bool:
        """Unfollow a user"""
        try:
            response = self._make_request('DELETE', f'/user/following/{username}')
            
            if response.status_code == 204:
                self.logger.info(f"Successfully unfollowed {username}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"User {username} not found or not being followed")
                return False
            else:
                self.logger.error(f"Failed to unfollow {username}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unfollowing {username}: {e}")
            return False
    
    def is_following(self, username: str) -> bool:
        """Check if currently following a user"""
        try:
            response = self._make_request('GET', f'/user/following/{username}')
            return response.status_code == 204
        except Exception as e:
            self.logger.error(f"Error checking following status for {username}: {e}")
            return False
    
    def is_follower(self, username: str) -> bool:
        """Check if a user is following the authenticated user"""
        try:
            response = self._make_request('GET', f'/users/{username}/following/{self.username}')
            return response.status_code == 204
        except Exception as e:
            self.logger.error(f"Error checking follower status for {username}: {e}")
            return False
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            response = self._make_request('GET', '/rate_limit')
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error getting rate limit status: {e}")
            return {}
    
    def get_user_repositories(self, username: Optional[str] = None, 
                            visibility: str = 'all') -> List[Dict[str, Any]]:
        """Get user repositories with proper private repository support"""
        username = username or self.username
        repos = []
        page = 1
        
        try:
            # Use different endpoints based on whether we're getting our own repos or someone else's
            if username == self.username:
                # Use /user/repos for authenticated user to get private repositories
                endpoint = '/user/repos'
                params = {
                    'per_page': 100,
                    'page': page,
                    'type': 'owner',
                    'sort': 'updated'
                }
                # Only add visibility param if it's specific (GitHub API doesn't accept 'all')
                if visibility in ['public', 'private']:
                    params['visibility'] = visibility
            else:
                # Use /users/{username}/repos for other users (only public repos)
                endpoint = f'/users/{username}/repos'
                params = {
                    'per_page': 100,
                    'page': page,
                    'type': 'owner',
                    'sort': 'updated'
                }
            
            while True:
                params['page'] = page
                response = self._make_request('GET', endpoint, params=params)
                
                if response.status_code != 200:
                    self.logger.error(f"Failed to get repositories: {response.status_code}")
                    if response.status_code == 403:
                        self.logger.error("Insufficient permissions. Ensure token has 'repo' scope for private repositories")
                    break
                
                data = response.json()
                if not data:
                    break
                
                repos.extend(data)
                page += 1
                
                if len(data) < 100:
                    break
            
            # Filter by visibility if specified and we're getting someone else's repos
            if username != self.username and visibility != 'all':
                if visibility == 'public':
                    repos = [repo for repo in repos if not repo.get('private', False)]
                elif visibility == 'private':
                    # Other users' private repos are not accessible, return empty list
                    repos = []
            
            self.logger.info(f"Retrieved {len(repos)} repositories for {username}")
            return repos
            
        except Exception as e:
            self.logger.error(f"Error getting repositories: {e}")
            return []
    
    def update_repository_visibility(self, repo_name: str, private: bool = True) -> bool:
        """Update repository visibility (git-bulk-private integration)"""
        try:
            data = {'private': private}
            response = self._make_request('PATCH', f'/repos/{self.username}/{repo_name}', 
                                        json=data)
            
            if response.status_code == 200:
                visibility = "private" if private else "public"
                self.logger.info(f"Successfully made {repo_name} {visibility}")
                return True
            else:
                self.logger.error(f"Failed to update {repo_name}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating repository {repo_name}: {e}")
            return False
