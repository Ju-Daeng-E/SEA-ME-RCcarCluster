"""
CAN bus control for BMW PiRacer Integrated Control System
"""

# Try to import can, fallback to mock if not available
try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    print("⚠️ python-can library not found. Using mock CAN for testing.")
    CAN_AVAILABLE = False

from typing import Optional
from constants import Constants
from logger import Logger
from crc_calculator import CRCCalculator

class CANController:
    """CAN bus control class"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.bmw_bus: Optional[object] = None
        self.running = True
        self.crc_calc = CRCCalculator()
        self.gws_counter = 0x01
        
    def setup_can_interfaces(self) -> bool:
        """Setup CAN interfaces"""
        if CAN_AVAILABLE:
            bmw_ok = self._setup_single_can(Constants.BMW_CAN_CHANNEL, "BMW")
            return bmw_ok
        else:
            self.logger.warning("⚠️ CAN not available - running in simulation mode")
            return False
    
    def _setup_single_can(self, channel: str, name: str) -> bool:
        """Setup single CAN interface"""
        if not CAN_AVAILABLE:
            return False
            
        try:
            bus = can.interface.Bus(channel=channel, interface='socketcan')
            self.bmw_bus = bus
            self.logger.info(f"✓ {name} CAN connected ({channel})")
            return True
        except Exception as e:
            self.logger.warning(f"⚠ {name} CAN not available: {e}")
            return False
    
    def send_gear_led(self, gear: str, flash: bool = False):
        """Send gear LED (optimized)"""
        if not CAN_AVAILABLE or not self.bmw_bus:
            return
        
        gear_led_codes = {
            'P': 0x20, 'R': 0x40, 'N': 0x60, 'D': 0x80, 'S': 0x81,
        }
        
        # LED code determination
        if gear.startswith('M'):
            led_code = 0x81
        elif gear in gear_led_codes:
            led_code = gear_led_codes[gear]
        else:
            return
        
        try:
            self.gws_counter = (self.gws_counter + 1) if self.gws_counter < 0x0E else 0x01
            payload_without_crc = [self.gws_counter, led_code, 0x00, 0x00]
            crc = self.crc_calc.bmw_3fd_crc(payload_without_crc)
            payload = [crc] + payload_without_crc
            
            message = can.Message(
                arbitration_id=Constants.LED_MESSAGE_ID,
                data=payload,
                is_extended_id=False
            )
            
            self.bmw_bus.send(message)
        except Exception as e:
            self.logger.error(f"LED send error: {e}")
    
    def shutdown(self):
        """Shutdown CAN bus"""
        self.running = False
        if CAN_AVAILABLE and self.bmw_bus:
            self.bmw_bus.shutdown() 