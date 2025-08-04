"""
Data models and state classes for BMW PiRacer Integrated Control System
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class BMWState:
    """BMW state data class"""
    current_gear: str = 'N'
    manual_gear: int = 1
    lever_position: str = 'Unknown'
    park_button: str = 'Released'
    unlock_button: str = 'Released'
    last_update: Optional[str] = None

@dataclass
class PiRacerState:
    """PiRacer state data class"""
    throttle_input: float = 0.0
    steering_input: float = 0.0
    current_speed: float = 0.0
    speed_gear: int = 1 