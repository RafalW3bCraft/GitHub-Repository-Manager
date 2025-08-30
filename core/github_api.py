"""
GitHub API client with comprehensive error handling and rate limiting
"""

import os
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from .logger import Logger

class GitHubAPI:
    """GitHub API client with enhanced functionality"""
    
    def __init__(self):
        self.base_url = os.getenv('GITHUB_API_BASE_URL', 'https://api.github.com')
        self.token = os.getenv('GITHUB_TOKEN') or os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
        self.username = os.getenv('GITHUB_USERNAME')
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '10'))  # Reduced timeout for faster operations
        
        if not self.token:
            raise ValueError("GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN environment variable is required")
        
        self.logger = Logger()
        self.session = None
        
        # Local state tracking for API consistency issues
        self._recently_followed = set()  # Track recently followed users
        self._recently_unfollowed = set()  # Track recently unfollowed users
        self._last_follow_operation_time = 0
        self._followers_cache = None
        self._following_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 5   # Cache TTL in seconds - optimized for speed
        
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create configured aiohttp session"""
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Automation-Suite/2.0'
        }
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        # Optimized connector for maximum concurrent connections
        connector = aiohttp.TCPConnector(
            limit=100,          # Maximum number of connections
            limit_per_host=50,  # Maximum connections per host
            keepalive_timeout=30,  # Keep connections alive for reuse
            enable_cleanup_closed=True
        )
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
        return self.session
    
    async def validate_token(self) -> bool:
        """Validate GitHub token and check required scopes"""
        try:
            response = await self._make_request('GET', '/user')
            if response.status == 200:
                user_data = await response.json()
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
                self.logger.error(f"Token validation failed: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Token validation error: {e}")
            return False
    
    async def check_repository_permissions(self) -> Dict[str, bool]:
        """Check what repository operations are available with current token"""
        permissions = {
            'can_read_public': False,
            'can_read_private': False,
            'can_write_repos': False
        }
        
        try:
            # Test reading public repositories
            response = await self._make_request('GET', '/user/repos', params={'per_page': 1, 'visibility': 'public'})
            permissions['can_read_public'] = response.status == 200
            
            # Test reading private repositories
            response = await self._make_request('GET', '/user/repos', params={'per_page': 1, 'visibility': 'private'})
            permissions['can_read_private'] = response.status == 200
            
            # Test repository write access (check token scopes)
            response = await self._make_request('GET', '/user')
            if response.status == 200:
                scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
                scopes = [scope.strip() for scope in scopes if scope.strip()]
                permissions['can_write_repos'] = 'repo' in scopes or 'public_repo' in scopes
            
            self.logger.info(f"Repository permissions: {permissions}")
            return permissions
            
        except Exception as e:
            self.logger.error(f"Error checking repository permissions: {e}")
            return permissions
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> aiohttp.ClientResponse:
        """Make API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        if not self.session:
            await self._create_session()
        
        try:
            if self.session is None:
                raise RuntimeError("Session not properly initialized")
            
            response = await self.session.request(method, url, **kwargs)
            return response
                
        except aiohttp.ClientError as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    async def get_user_info(self, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user information"""
        username = username or self.username
        try:
            response = await self._make_request('GET', f'/users/{username}')
            if response.status == 200:
                return await response.json()
            else:
                self.logger.error(f"Failed to get user info for {username}: {response.status}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None
    
    async def get_followers(self, username: Optional[str] = None, per_page: int = 100) -> List[str]:
        """Get list of followers for a user with local state awareness"""
        username = username or self.username
        
        # Clean old local state entries
        await self._clean_local_state()
        
        # Use cache if valid and it's for the authenticated user
        if (username == self.username and self._is_cache_valid() and 
            self._followers_cache is not None):
            self.logger.debug("Using cached followers data")
            return self._followers_cache
        
        followers = []
        page = 1
        
        try:
            while True:
                response = await self._make_request('GET', f'/users/{username}/followers', 
                                            params={'per_page': per_page, 'page': page})
                
                if response.status != 200:
                    self.logger.error(f"Failed to get followers: {response.status}")
                    break
                
                data = await response.json()
                if not data:
                    break
                
                followers.extend([user['login'] for user in data])
                page += 1
                
                # GitHub API pagination limit check
                if len(data) < per_page:
                    break
            
            # Cache results for authenticated user
            if username == self.username:
                self._followers_cache = followers
                self._cache_timestamp = time.time()
            
            self.logger.info(f"Retrieved {len(followers)} followers for {username}")
            return followers
            
        except Exception as e:
            self.logger.error(f"Error getting followers: {e}")
            return []
    
    async def get_following(self, username: Optional[str] = None, per_page: int = 100) -> List[str]:
        """Get list of users being followed with local state awareness"""
        username = username or self.username
        
        # Clean old local state entries
        await self._clean_local_state()
        
        # Use cache if valid and it's for the authenticated user
        if (username == self.username and self._is_cache_valid() and 
            self._following_cache is not None):
            self.logger.debug("Using cached following data")
            # Apply local state changes to cached data
            following = self._following_cache.copy()
            # Add recently followed users
            following.extend([u for u in self._recently_followed if u not in following])
            # Remove recently unfollowed users
            following = [u for u in following if u not in self._recently_unfollowed]
            return following
        
        following = []
        page = 1
        
        try:
            while True:
                response = await self._make_request('GET', f'/users/{username}/following',
                                            params={'per_page': per_page, 'page': page})
                
                if response.status != 200:
                    self.logger.error(f"Failed to get following: {response.status}")
                    break
                
                data = await response.json()
                if not data:
                    break
                
                following.extend([user['login'] for user in data])
                page += 1
                
                if len(data) < per_page:
                    break
            
            # Cache results for authenticated user
            if username == self.username:
                self._following_cache = following
                self._cache_timestamp = time.time()
                # Apply local state changes to fresh data
                following.extend([u for u in self._recently_followed if u not in following])
                following = [u for u in following if u not in self._recently_unfollowed]
            
            self.logger.info(f"Retrieved {len(following)} following for {username}")
            return following
            
        except Exception as e:
            self.logger.error(f"Error getting following: {e}")
            return []
    
    async def follow_user(self, username: str) -> bool:
        """Follow a user and update local state"""
        try:
            response = await self._make_request('PUT', f'/user/following/{username}')
            
            if response.status == 204:
                self.logger.info(f"Successfully followed {username}")
                # Update local state tracking
                self._recently_followed.add(username)
                self._recently_unfollowed.discard(username)
                self._last_follow_operation_time = time.time()
                # Do NOT invalidate cache - let cache-aware methods use local state
                return True
            elif response.status == 404:
                self.logger.warning(f"User {username} not found")
                return False
            else:
                self.logger.error(f"Failed to follow {username}: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error following {username}: {e}")
            return False
    
    async def unfollow_user(self, username: str) -> bool:
        """Unfollow a user and update local state"""
        try:
            response = await self._make_request('DELETE', f'/user/following/{username}')
            
            if response.status == 204:
                self.logger.info(f"Successfully unfollowed {username}")
                # Update local state tracking
                self._recently_unfollowed.add(username)
                self._recently_followed.discard(username)
                self._last_follow_operation_time = time.time()
                # Do NOT invalidate cache - let cache-aware methods use local state
                return True
            elif response.status == 404:
                self.logger.warning(f"User {username} not found or not being followed")
                return False
            else:
                self.logger.error(f"Failed to unfollow {username}: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unfollowing {username}: {e}")
            return False
    
    async def is_following(self, username: str) -> bool:
        """Check if currently following a user with local state consideration"""
        try:
            # Check local state first for recent operations
            if username in self._recently_followed:
                self.logger.debug(f"Using local state: recently followed {username}")
                return True
            if username in self._recently_unfollowed:
                self.logger.debug(f"Using local state: recently unfollowed {username}")
                return False
            
            response = await self._make_request('GET', f'/user/following/{username}')
            return response.status == 204
        except Exception as e:
            self.logger.error(f"Error checking following status for {username}: {e}")
            return False
    
    async def is_follower(self, username: str) -> bool:
        """Check if a user is following the authenticated user"""
        try:
            response = await self._make_request('GET', f'/users/{username}/following/{self.username}')
            return response.status == 204
        except Exception as e:
            self.logger.error(f"Error checking follower status for {username}: {e}")
            return False

    def _invalidate_cache(self):
        """Invalidate followers/following cache"""
        self._followers_cache = None
        self._following_cache = None
        self._cache_timestamp = 0
        self.logger.debug("Cache invalidated")

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        return (self._cache_timestamp > 0 and 
                (time.time() - self._cache_timestamp) < self._cache_ttl)

    async def _clean_local_state(self):
        """Clean old local state entries after sufficient time has passed"""
        current_time = time.time()
        # Clean state after 1 minute to prevent memory buildup and enable faster operations
        if current_time - self._last_follow_operation_time > 60:
            self._recently_followed.clear()
            self._recently_unfollowed.clear()
            self.logger.debug("Cleaned old local state entries")

    async def is_following_with_retry(self, username: str, max_retries: int = 3) -> bool:
        """Check if following with immediate retry logic for API consistency"""
        result = False
        for attempt in range(max_retries):
            result = await self.is_following(username)
            
            # If we think we're following them based on local state, validate with API
            if username in self._recently_followed and not result:
                if attempt < max_retries - 1:
                    self.logger.debug(f"API inconsistency detected for {username}, immediate retry {attempt + 1}/{max_retries}")
                    # Immediate retry without artificial delay
                    continue
                else:
                    self.logger.warning(f"API still inconsistent for {username} after {max_retries} retries")
            
            return result
        
        return result
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            response = await self._make_request('GET', '/rate_limit')
            if response.status == 200:
                return await response.json()
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error getting rate limit status: {e}")
            return {}
    
    async def get_user_repositories(self, username: Optional[str] = None, 
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
                response = await self._make_request('GET', endpoint, params=params)
                
                if response.status != 200:
                    self.logger.error(f"Failed to get repositories: {response.status}")
                    if response.status == 403:
                        self.logger.error("Insufficient permissions. Ensure token has 'repo' scope for private repositories")
                    break
                
                data = await response.json()
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
    
    async def update_repository_visibility(self, repo_name: str, private: bool = True) -> bool:
        """Update repository visibility (git-bulk-private integration)"""
        try:
            data = {'private': private}
            response = await self._make_request('PATCH', f'/repos/{self.username}/{repo_name}', 
                                        json=data)
            
            if response.status == 200:
                visibility = "private" if private else "public"
                self.logger.info(f"Successfully made {repo_name} {visibility}")
                return True
            else:
                self.logger.error(f"Failed to update {repo_name}: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating repository {repo_name}: {e}")
            return False
    
    async def create_repository(self, name: str, description: str = "", private: bool = True, 
                         auto_init: bool = True, gitignore_template: str = "", 
                         license_template: str = "") -> Optional[Dict[str, Any]]:
        """Create a new repository"""
        try:
            data = {
                'name': name,
                'description': description,
                'private': private,
                'auto_init': auto_init
            }
            
            if gitignore_template:
                data['gitignore_template'] = gitignore_template
            if license_template:
                data['license_template'] = license_template
            
            response = await self._make_request('POST', '/user/repos', json=data)
            
            if response.status == 201:
                repo_data = await response.json()
                self.logger.info(f"Successfully created repository: {name}")
                return repo_data
            else:
                self.logger.error(f"Failed to create repository {name}: {response.status}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating repository {name}: {e}")
            return None
    
    async def search_users_by_criteria(self, min_followers: int = 100, min_repos: int = 5, 
                                language: str = "", location: str = "", 
                                sort: str = "followers", per_page: int = 100) -> List[Dict[str, Any]]:
        """Search users based on followers, repositories, and other criteria"""
        try:
            # Build search query
            query_parts = []
            
            if min_followers > 0:
                query_parts.append(f"followers:>={min_followers}")
            if min_repos > 0:
                query_parts.append(f"repos:>={min_repos}")
            if language:
                query_parts.append(f"language:{language}")
            if location:
                query_parts.append(f"location:{location}")
            
            if not query_parts:
                query_parts.append("followers:>=10")  # Default minimum
            
            query = " ".join(query_parts)
            
            params = {
                'q': query,
                'sort': sort,
                'order': 'desc',
                'per_page': min(per_page, 100)
            }
            
            response = await self._make_request('GET', '/search/users', params=params)
            
            if response.status == 200:
                search_data = await response.json()
                users = search_data.get('items', [])
                self.logger.info(f"Found {len(users)} users matching criteria")
                return users
            else:
                self.logger.error(f"Failed to search users: {response.status}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error searching users: {e}")
            return []
    
    async def search_repositories_by_stars(self, min_stars: int = 100, language: str = "", 
                                    topic: str = "", sort: str = "stars", 
                                    per_page: int = 100) -> List[Dict[str, Any]]:
        """Search repositories by star count and other criteria"""
        try:
            query_parts = []
            
            if min_stars > 0:
                query_parts.append(f"stars:>={min_stars}")
            if language:
                query_parts.append(f"language:{language}")
            if topic:
                query_parts.append(f"topic:{topic}")
            
            if not query_parts:
                query_parts.append("stars:>=10")  # Default minimum
            
            query = " ".join(query_parts)
            
            params = {
                'q': query,
                'sort': sort,
                'order': 'desc',
                'per_page': min(per_page, 100)
            }
            
            response = await self._make_request('GET', '/search/repositories', params=params)
            
            if response.status == 200:
                search_data = await response.json()
                repos = search_data.get('items', [])
                self.logger.info(f"Found {len(repos)} repositories matching criteria")
                return repos
            else:
                self.logger.error(f"Failed to search repositories: {response.status}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error searching repositories: {e}")
            return []
    
    async def clone_repository(self, repo_url: str, local_path: str = "") -> bool:
        """Clone a repository to local directory"""
        try:
            import subprocess
            import os
            from pathlib import Path
            
            if not local_path:
                # Extract repo name from URL
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                local_path = f"./cloned_repos/{repo_name}"
            
            # Create directory if it doesn't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Use git clone command
            cmd = ['git', 'clone', repo_url, local_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"Successfully cloned repository to {local_path}")
                return True
            else:
                self.logger.error(f"Failed to clone repository: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cloning repository: {e}")
            return False
    
    async def get_user_starred_repos(self, username: Optional[str] = None, 
                              per_page: int = 100) -> List[Dict[str, Any]]:
        """Get repositories starred by a user"""
        username = username or self.username
        starred_repos = []
        page = 1
        
        try:
            while True:
                response = await self._make_request('GET', f'/users/{username}/starred',
                                            params={'per_page': per_page, 'page': page})
                
                if response.status != 200:
                    self.logger.error(f"Failed to get starred repos: {response.status}")
                    break
                
                data = await response.json()
                if not data:
                    break
                
                starred_repos.extend(data)
                page += 1
                
                if len(data) < per_page:
                    break
            
            self.logger.info(f"Retrieved {len(starred_repos)} starred repositories for {username}")
            return starred_repos
            
        except Exception as e:
            self.logger.error(f"Error getting starred repositories: {e}")
            return []
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
