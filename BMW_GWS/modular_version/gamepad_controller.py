"""
Gamepad controller for BMW PiRacer Integrated Control System
"""

import time
import threading
from typing import Optional
from constants import Constants
from data_models import PiRacerState
from logger import Logger

# PiRacer imports (optional)
try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
except ImportError:
    print("⚠️ PiRacer library not found. Running in simulation mode.")
    PIRACER_AVAILABLE = False

class GamepadController:
    """Gamepad controller for PiRacer"""
    
    def __init__(self, logger: Logger, piracer_state: PiRacerState):
        self.logger = logger
        self.piracer_state = piracer_state
        self.running = False
        self.control_thread = None
        
        # PiRacer objects
        self.piracer = None
        self.gamepad = None
        
        # Initialize PiRacer if available
        if PIRACER_AVAILABLE:
            try:
                self.piracer = PiRacerStandard()
                self.gamepad = ShanWanGamepad()
                self.logger.info("✓ PiRacer and gamepad initialized")
            except Exception as e:
                self.logger.error(f"PiRacer initialization failed: {e}")
        else:
            self.logger.warning("⚠️ PiRacer not available - running in simulation mode")
    
    def start(self):
        """Start gamepad control"""
        if not self.running and self.gamepad and self.piracer:
            self.running = True
            self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self.control_thread.start()
            self.logger.info("🎮 Gamepad control started")
        elif not PIRACER_AVAILABLE:
            self.logger.warning("⚠️ Gamepad control not started - PiRacer not available")
    
    def stop(self):
        """Stop gamepad control"""
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=1.0)
        self.logger.info("🛑 Gamepad control stopped")
    
    def _control_loop(self):
        """Main gamepad control loop"""
        last_l2 = last_r2 = False
        update_interval = 1.0 / Constants.GAMEPAD_UPDATE_RATE
        
        while self.running:
            try:
                gamepad_input = self.gamepad.read_data()
                
                # Speed gear control (L2/R2)
                if gamepad_input.button_l2 and not last_l2:
                    self.piracer_state.speed_gear = max(1, self.piracer_state.speed_gear - 1)
                    self.logger.info(f"🔽 Speed Gear: {self.piracer_state.speed_gear}")
                if gamepad_input.button_r2 and not last_r2:
                    self.piracer_state.speed_gear = min(Constants.SPEED_GEARS, self.piracer_state.speed_gear + 1)
                    self.logger.info(f"🔼 Speed Gear: {self.piracer_state.speed_gear}")
                
                last_l2 = gamepad_input.button_l2
                last_r2 = gamepad_input.button_r2
                
                # Joystick input
                self.piracer_state.throttle_input = -gamepad_input.analog_stick_right.y
                self.piracer_state.steering_input = -gamepad_input.analog_stick_left.x
                
                # PiRacer control
                self.piracer.set_throttle_percent(self.piracer_state.throttle_input)
                self.piracer.set_steering_percent(self.piracer_state.steering_input)
                
                time.sleep(update_interval)
                
            except Exception as e:
                self.logger.error(f"Gamepad error: {e}")
                time.sleep(1)
    
    def get_throttle_input(self) -> float:
        """Get current throttle input"""
        return self.piracer_state.throttle_input
    
    def get_steering_input(self) -> float:
        """Get current steering input"""
        return self.piracer_state.steering_input
    
    def get_speed_gear(self) -> int:
        """Get current speed gear"""
        return self.piracer_state.speed_gear
    
    def is_available(self) -> bool:
        """Check if PiRacer is available"""
        return PIRACER_AVAILABLE and self.piracer is not None and self.gamepad is not None 