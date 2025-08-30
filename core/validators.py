"""
Validation utilities for Github-Repository-Manager
"""

import re
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from .logger import Logger

class Validators:
    """Input validation and data sanitization"""
    
    def __init__(self):
        self.logger = Logger()
        # GitHub username pattern: alphanumeric, hyphens, max 39 chars
        self.username_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$')
    
    def validate_username(self, username: str) -> bool:
        """Validate GitHub username format"""
        if not username or not isinstance(username, str):
            return False
        
        # Check basic pattern
        if not self.username_pattern.match(username):
            return False
        
        # Additional checks
        if username.startswith('-') or username.endswith('-'):
            return False
        
        if '--' in username:
            return False
        
        return True
    
    async def validate_usernames(self, usernames: List[str]) -> List[str]:
        """Validate list of usernames and return valid ones"""
        valid_usernames = []
        invalid_count = 0
        
        for username in usernames:
            username = username.strip()
            if self.validate_username(username):
                valid_usernames.append(username)
            else:
                invalid_count += 1
                self.logger.warning(f"Invalid username format: {username}")
        
        if invalid_count > 0:
            self.logger.warning(f"Filtered out {invalid_count} invalid usernames")
        
        return valid_usernames
    
    async def validate_file_path(self, file_path: str) -> bool:
        """Validate file path exists and is readable"""
        try:
            path = Path(file_path)
            return path.exists() and path.is_file() and os.access(path, os.R_OK)
        except Exception:
            return False
    
    def validate_positive_integer(self, value: Any, min_value: int = 1) -> bool:
        """Validate positive integer within range"""
        try:
            num = int(value)
            return num >= min_value
        except (ValueError, TypeError):
            return False
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file operations"""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        # Ensure it doesn't start/end with dots or spaces
        sanitized = sanitized.strip('. ')
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "unnamed_file"
        
        return sanitized
    
    def validate_delay_range(self, delay: int, min_delay: int = 1, max_delay: int = 60) -> bool:
        """No delay validation - all delays removed for follow/unfollow operations"""
        return True
    
    def validate_api_response(self, response_data: Dict[str, Any], 
                            required_fields: List[str]) -> bool:
        """Validate API response contains required fields"""
        if not isinstance(response_data, dict):
            return False
        
        for field in required_fields:
            if field not in response_data:
                self.logger.warning(f"Missing required field in API response: {field}")
                return False
        
        return True
    
    def validate_github_token_format(self, token: str) -> bool:
        """Validate GitHub token format"""
        if not token or not isinstance(token, str):
            return False
        
        # GitHub personal access tokens start with 'ghp_' and are 40 chars total
        # Classic tokens are 40 chars hex
        token = token.strip()
        
        if token.startswith('ghp_'):
            return len(token) == 40
        elif re.match(r'^[a-f0-9]{40}$', token):
            return True
        
        return False
    
    def validate_operation_limits(self, operation: str, count: int) -> bool:
        """No operation limits - all follow/unfollow operations allowed"""
        # Rate limits purged - no restrictions on follow/unfollow operations
        self.logger.info(f"Operation {operation} with {count} items - no limits enforced")
        return True
