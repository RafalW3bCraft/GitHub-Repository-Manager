"""
Logging configuration for GitHub Automation Suite
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

class Logger:
    """Simplified logging for GitHub Automation Suite"""
    
    def __init__(self, name: str = "github_automation"):
        self.name = name
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_file = os.getenv('LOG_FILE', 'logs/github_automation.log')
        
        # Ensure logs directory exists
        Path(self.log_file).parent.mkdir(exist_ok=True)
        
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup simple logger with basic file output"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.log_level))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Simple formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # File handler only
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)
    
    def set_level(self, level: str):
        """Set logging level"""
        level = level.upper()
        if hasattr(logging, level):
            self.logger.setLevel(getattr(logging, level))
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(getattr(logging, level))
    
    # Removed comprehensive operation logging as per revision requirements
