"""
Constants and configuration for BMW PiRacer Integrated Control System
"""

from enum import Enum

class Constants:
    """System constants and configuration"""
    
    # CAN related
    BMW_CAN_CHANNEL = 'can0'
    CAN_BITRATE = 500000
    LEVER_MESSAGE_ID = 0x197
    LED_MESSAGE_ID = 0x3FD
    HEARTBEAT_MESSAGE_ID = 0x55e
    
    # Speed sensor related (GPIO)
    SPEED_SENSOR_PIN = 16  # GPIO 16 (Physical Pin 36)
    PULSES_PER_TURN = 40  # encoder wheel: 20 slots × 2 (rising+falling)
    WHEEL_DIAMETER_MM = 64  # mm
    
    # Timing
    BMW_CAN_TIMEOUT = 1.0
    GAMEPAD_UPDATE_RATE = 20  # Hz
    LED_UPDATE_RATE = 10  # Hz
    TIME_UPDATE_RATE = 1  # Hz
    TOGGLE_TIMEOUT = 0.5
    SPEED_CALCULATION_INTERVAL = 1.0  # Speed calculation interval (seconds)
    PULSE_DEBOUNCE_MICROS = 700  # Pulse debouncing microseconds
    
    # UI related (1280x400 optimized)
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 400
    MAX_LOG_LINES = 30
    LOG_FONT_SIZE = 7
    SPEEDOMETER_SIZE = (100, 100)
    GEAR_DISPLAY_SIZE = (100, 80)
    
    # Performance related
    MAX_SPEED = 50.0  # km/h
    SPEED_GEARS = 4
    MANUAL_GEARS = 8
    
    # Colors
    BMW_BLUE = "#0078d4"
    SUCCESS_GREEN = "#00ff00"
    ERROR_RED = "#ff0000"
    WARNING_ORANGE = "#ff8800"

class GearType(Enum):
    """Gear type enumeration"""
    PARK = 'P'
    REVERSE = 'R'
    NEUTRAL = 'N'
    DRIVE = 'D'
    SPORT = 'S'
    MANUAL = 'M'
    UNKNOWN = 'Unknown'

class LeverPosition(Enum):
    """Lever position enumeration"""
    CENTER = 0x0E
    UP_R = 0x1E
    UP_PLUS = 0x2E
    DOWN_D = 0x3E
    SIDE_S = 0x7E
    MANUAL_DOWN = 0x5E
    MANUAL_UP = 0x6E

class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3 