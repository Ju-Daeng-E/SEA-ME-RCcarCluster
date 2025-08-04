"""
Speed sensor GPIO control for BMW PiRacer Integrated Control System
"""

import time
import threading
from typing import Callable

# Try to import RPi.GPIO, fallback to mock if not available
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("⚠️ RPi.GPIO library not found. Using mock GPIO for testing.")
    GPIO_AVAILABLE = False

from constants import Constants
from logger import Logger

class SpeedSensor:
    """Speed sensor GPIO control class"""
    
    def __init__(self, logger: Logger, speed_callback: Callable[[float], None]):
        self.logger = logger
        self.speed_callback = speed_callback
        self.counter = 0
        self.velocity_kmh = 0.0
        self.previous_micros = 0
        self.running = False
        self.calculation_thread = None
        
        # GPIO setup (polling mode)
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()  # Clean up existing setup
            except:
                pass
                
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(Constants.SPEED_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                self.logger.info(f"✓ Speed sensor initialized on GPIO {Constants.SPEED_SENSOR_PIN} (polling mode)")
            except Exception as e:
                self.logger.error(f"Speed sensor GPIO setup failed: {e}")
        else:
            self.logger.warning("⚠️ GPIO not available - speed sensor running in simulation mode")
    
    def _count_pulses_polling(self):
        """Polling mode pulse count"""
        if GPIO_AVAILABLE:
            current_state = GPIO.input(Constants.SPEED_SENSOR_PIN)
            current_micros = time.time() * 1000000  # microseconds
            
            # Edge detection if state changed
            if hasattr(self, 'last_state') and current_state != self.last_state:
                if current_micros - self.previous_micros >= Constants.PULSE_DEBOUNCE_MICROS:
                    self.counter += 1
                    self.previous_micros = current_micros
                    
            self.last_state = current_state
        else:
            # Mock pulse generation for testing
            if hasattr(self, 'mock_pulse_counter'):
                self.mock_pulse_counter += 1
                if self.mock_pulse_counter % 100 == 0:  # Simulate pulses
                    self.counter += 1
            else:
                self.mock_pulse_counter = 0
    
    def _calculate_speed(self):
        """Speed calculation thread (polling mode)"""
        if GPIO_AVAILABLE:
            try:
                self.last_state = GPIO.input(Constants.SPEED_SENSOR_PIN)  # Initial state
            except:
                self.last_state = 1  # Default value
        else:
            self.last_state = 1  # Mock state
        
        while self.running:
            try:
                # Poll for pulses (1ms interval)
                for _ in range(int(Constants.SPEED_CALCULATION_INTERVAL * 1000)):
                    if not self.running:
                        break
                    self._count_pulses_polling()
                    time.sleep(0.001)  # 1ms polling
                
                # RPM calculation
                rpm = (60 * self.counter) / Constants.PULSES_PER_TURN
                
                # Wheel circumference (m)
                wheel_circ_m = 3.1416 * (Constants.WHEEL_DIAMETER_MM / 1000.0)
                
                # Speed (km/h)
                self.velocity_kmh = (rpm * wheel_circ_m * 60) / 1000.0
                
                # Speed update callback
                self.speed_callback(self.velocity_kmh)
                
                # Debug log
                if self.counter > 0:  # Only log when moving
                    self.logger.debug(f"🏁 RPM: {rpm:.1f} | Speed: {self.velocity_kmh:.2f} km/h | Pulses: {self.counter}")
                
                # Reset counter
                self.counter = 0
                
            except Exception as e:
                self.logger.error(f"Speed calculation error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start speed calculation"""
        if not self.running:
            self.running = True
            self.calculation_thread = threading.Thread(target=self._calculate_speed, daemon=True)
            self.calculation_thread.start()
            self.logger.info("🟢 Speed sensor started")
    
    def stop(self):
        """Stop speed calculation"""
        self.running = False
        self.logger.info("🔴 Speed sensor stopped (polling mode)")
    
    def cleanup(self):
        """Cleanup"""
        self.stop()
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup(Constants.SPEED_SENSOR_PIN)
            except Exception as e:
                self.logger.error(f"GPIO cleanup error: {e}") 