"""
Rate limiting functionality for GitHub API requests
"""

import time
import random
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from .logger import Logger

class RateLimiter:
    """Simple rate limiting for GitHub API"""
    
    def __init__(self):
        self.logger = Logger()
        self.min_delay = float(os.getenv('MIN_DELAY', '1'))
        self.max_delay = float(os.getenv('MAX_DELAY', '3'))
        
        # GitHub API rate limit tracking (simplified)
        self.remaining_requests = 5000  # Default for authenticated requests
        self.reset_time = None
        self.last_request_time = None
    
    def wait_if_needed(self):
        """Apply simple rate limiting delay"""
        current_time = time.time()
        
        # Simple delay calculation
        delay = random.uniform(self.min_delay, self.max_delay)
        
        # Ensure minimum time between requests
        if self.last_request_time:
            time_since_last = current_time - self.last_request_time
            if time_since_last < delay:
                sleep_time = delay - time_since_last
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def update_from_headers(self, headers):
        """Update rate limit info from API response headers"""
        try:
            if 'X-RateLimit-Remaining' in headers:
                self.remaining_requests = int(headers['X-RateLimit-Remaining'])
            
            if 'X-RateLimit-Reset' in headers:
                self.reset_time = int(headers['X-RateLimit-Reset'])
            
            # Log rate limit status periodically
            if self.remaining_requests % 100 == 0:
                self.logger.debug(f"Rate limit status: {self.remaining_requests} requests remaining")
        
        except (ValueError, KeyError) as e:
            self.logger.debug(f"Error parsing rate limit headers: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status"""
        reset_in = None
        if self.reset_time:
            reset_in = max(0, self.reset_time - time.time())
        
        return {
            'remaining_requests': self.remaining_requests,
            'reset_in_seconds': reset_in,
            'last_request_time': self.last_request_time
        }
