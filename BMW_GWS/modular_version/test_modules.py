#!/usr/bin/env python3
"""
Test script for BMW PiRacer Integrated Control System modules
Verifies that all modules can be imported and basic functionality works
"""

import sys
import os

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing module imports...")
    
    try:
        from constants import Constants, LogLevel
        print("✅ constants.py - OK")
    except ImportError as e:
        print(f"❌ constants.py - FAILED: {e}")
        return False
    
    try:
        from data_models import BMWState, PiRacerState
        print("✅ data_models.py - OK")
    except ImportError as e:
        print(f"❌ data_models.py - FAILED: {e}")
        return False
    
    try:
        from logger import Logger
        print("✅ logger.py - OK")
    except ImportError as e:
        print(f"❌ logger.py - FAILED: {e}")
        return False
    
    try:
        from crc_calculator import CRCCalculator
        print("✅ crc_calculator.py - OK")
    except ImportError as e:
        print(f"❌ crc_calculator.py - FAILED: {e}")
        return False
    
    try:
        from speed_sensor import SpeedSensor
        print("✅ speed_sensor.py - OK")
    except ImportError as e:
        print(f"❌ speed_sensor.py - FAILED: {e}")
        return False
    
    try:
        from bmw_lever_controller import BMWLeverController
        print("✅ bmw_lever_controller.py - OK")
    except ImportError as e:
        print(f"❌ bmw_lever_controller.py - FAILED: {e}")
        return False
    
    try:
        from can_controller import CANController
        print("✅ can_controller.py - OK")
    except ImportError as e:
        print(f"❌ can_controller.py - FAILED: {e}")
        return False
    
    try:
        from gamepad_controller import GamepadController
        print("✅ gamepad_controller.py - OK")
    except ImportError as e:
        print(f"❌ gamepad_controller.py - FAILED: {e}")
        return False
    
    try:
        from gui_widgets import SpeedometerWidget, GearDisplayWidget
        print("✅ gui_widgets.py - OK")
    except ImportError as e:
        print(f"❌ gui_widgets.py - FAILED: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic functionality of modules"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        from constants import Constants, LogLevel
        from data_models import BMWState, PiRacerState
        from logger import Logger
        
        # Test constants
        assert Constants.BMW_CAN_CHANNEL == 'can0'
        assert Constants.SPEED_SENSOR_PIN == 16
        print("✅ Constants - OK")
        
        # Test data models
        bmw_state = BMWState()
        piracer_state = PiRacerState()
        assert bmw_state.current_gear == 'N'
        assert piracer_state.current_speed == 0.0
        print("✅ Data models - OK")
        
        # Test logger
        logger = Logger(LogLevel.INFO)
        logger.info("Test message")
        print("✅ Logger - OK")
        
        # Test CRC calculator
        from crc_calculator import CRCCalculator
        crc_calc = CRCCalculator()
        test_data = b'\x01\x02\x03\x04'
        crc_result = crc_calc.bmw_3fd_crc(test_data)
        assert isinstance(crc_result, int)
        print("✅ CRC calculator - OK")
        
        # Test BMW lever controller
        from bmw_lever_controller import BMWLeverController
        lever_controller = BMWLeverController(logger)
        print("✅ BMW lever controller - OK")
        
        # Test CAN controller
        from can_controller import CANController
        can_controller = CANController(logger)
        print("✅ CAN controller - OK")
        
        # Test gamepad controller
        from gamepad_controller import GamepadController
        gamepad_controller = GamepadController(logger, piracer_state)
        print("✅ Gamepad controller - OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test - FAILED: {e}")
        return False

def test_gui_imports():
    """Test GUI-related imports"""
    print("\n🧪 Testing GUI imports...")
    
    try:
        from main_gui import BMWPiRacerIntegratedControl
        print("✅ main_gui.py - OK")
        return True
    except ImportError as e:
        print(f"⚠️ main_gui.py - WARNING (PyQt5 may not be available): {e}")
        return True  # Not critical for basic functionality

def main():
    """Main test function"""
    print("🚀 BMW PiRacer Modular System - Module Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed. Check dependencies.")
        return False
    
    # Test basic functionality
    if not test_basic_functionality():
        print("\n❌ Basic functionality tests failed.")
        return False
    
    # Test GUI imports
    test_gui_imports()
    
    print("\n✅ All tests passed! Modular system is ready.")
    print("\n📋 Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Setup CAN interface: sudo ip link set can0 up type can bitrate 500000")
    print("3. Run the system: python3 main.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 