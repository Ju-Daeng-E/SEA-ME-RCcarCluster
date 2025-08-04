#!/usr/bin/env python3
"""
Debug script to identify segfault causes in BMW PiRacer system
"""

import sys
import os
import traceback

def test_pyqt5_basic():
    """Test basic PyQt5 functionality"""
    print("🔍 Testing basic PyQt5 import...")
    try:
        from PyQt5.QtWidgets import QApplication, QLabel
        from PyQt5.QtCore import QCoreApplication, Qt
        print("✅ PyQt5 basic imports successful")
        
        # Test Qt application creation
        print("🔍 Testing QApplication creation...")
        if hasattr(QCoreApplication, 'setAttribute'):
            QCoreApplication.setAttribute(Qt.AA_X11InitThreads, True)
        
        app = QApplication([])
        print("✅ QApplication created successfully")
        
        # Test basic widget
        print("🔍 Testing basic widget creation...")
        label = QLabel("Test")
        print("✅ Widget created successfully")
        
        app.quit()
        del app
        print("✅ QApplication cleaned up successfully")
        return True
        
    except Exception as e:
        print(f"❌ PyQt5 basic test failed: {e}")
        print(f"📊 Traceback: {traceback.format_exc()}")
        return False

def test_local_imports():
    """Test local module imports"""
    print("🔍 Testing local module imports...")
    
    modules = [
        'constants',
        'logger', 
        'data_models',
        'bmw_lever_controller',
        'can_controller',
        'speed_sensor',
        'gamepad_controller',
        'gui_widgets'
    ]
    
    failed_modules = []
    
    for module in modules:
        try:
            exec(f"import {module}")
            print(f"✅ {module} imported successfully")
        except Exception as e:
            print(f"❌ {module} import failed: {e}")
            failed_modules.append(module)
    
    return len(failed_modules) == 0

def test_can_interface():
    """Test CAN interface setup"""
    print("🔍 Testing CAN interface...")
    try:
        import can
        print("✅ python-can imported successfully")
        
        # Test CAN interface creation (don't actually connect)
        print("🔍 Testing CAN interface creation...")
        # This should not cause segfault
        return True
        
    except Exception as e:
        print(f"❌ CAN interface test failed: {e}")
        print(f"📊 Traceback: {traceback.format_exc()}")
        return False

def test_gpio():
    """Test GPIO functionality"""
    print("🔍 Testing GPIO imports...")
    try:
        import RPi.GPIO
        print("✅ RPi.GPIO imported successfully")
        return True
    except Exception as e:
        print(f"❌ GPIO test failed: {e}")
        return False

def test_main_gui_import():
    """Test main_gui module import"""
    print("🔍 Testing main_gui import...")
    try:
        from main_gui import BMWPiRacerIntegratedControl
        print("✅ main_gui imported successfully")
        return True
    except Exception as e:
        print(f"❌ main_gui import failed: {e}")
        print(f"📊 Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all debug tests"""
    print("🚀 BMW PiRacer Segfault Debug Tool")
    print("=" * 50)
    
    # Set DISPLAY
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
        print("🖥️ DISPLAY set to :0")
    
    tests = [
        ("Local Imports", test_local_imports),
        ("CAN Interface", test_can_interface),
        ("GPIO", test_gpio),
        ("PyQt5 Basic", test_pyqt5_basic),
        ("Main GUI Import", test_main_gui_import),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed with exception: {e}")
            print(f"📊 Traceback: {traceback.format_exc()}")
            results[test_name] = False
    
    print(f"\n{'='*50}")
    print("🔍 DEBUG RESULTS SUMMARY:")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} : {status}")
    
    failed_tests = [name for name, result in results.items() if not result]
    
    if failed_tests:
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        print("💡 Segfault likely caused by one of these failures")
    else:
        print("\n✅ All basic tests passed")
        print("💡 Segfault may be in the GUI initialization or threading")

if __name__ == "__main__":
    main()