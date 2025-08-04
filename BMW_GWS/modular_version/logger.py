"""
Custom logger implementation for BMW PiRacer Integrated Control System
"""

import logging
from datetime import datetime
from typing import Callable
from constants import LogLevel

class Logger:
    """Custom logger class with multiple handlers"""
    
    def __init__(self, level: LogLevel = LogLevel.INFO):
        self.level = level
        self.handlers = []
    
    def add_handler(self, handler: Callable[[str], None]):
        """Add log handler"""
        self.handlers.append(handler)
    
    def log(self, level: LogLevel, message: str):
        """Log message output"""
        if level.value >= self.level.value:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            formatted_msg = f"{timestamp} {message}"
            for handler in self.handlers:
                handler(formatted_msg)
    
    def debug(self, message: str):
        self.log(LogLevel.DEBUG, f"🔍 {message}")
    
    def info(self, message: str):
        self.log(LogLevel.INFO, f"ℹ️ {message}")
    
    def warning(self, message: str):
        self.log(LogLevel.WARNING, f"⚠️ {message}")
    
    def error(self, message: str):
        self.log(LogLevel.ERROR, f"❌ {message}") 