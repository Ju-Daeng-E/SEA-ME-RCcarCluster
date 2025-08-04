#!/usr/bin/env python3
"""
BMW PiRacer Integrated Control System - Modular Version
Main entry point for the modularized BMW PiRacer control system

Features:
- BMW Gear Lever Control (P/R/N/D/M1-M8)
- Gamepad Throttle/Steering Control
- Real-time Speed Display via GPIO16
- BMW CAN Bus + GPIO16 Speed Sensor
- Modular Architecture for Easy Maintenance
- PyQt5 Dashboard (Optional)
"""

import sys
import os
import can
import time
import signal
import traceback
from datetime import datetime

# PyQt5 import (optional)
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication
    PYQT5_AVAILABLE = True
    print("✅ PyQt5 successfully imported - GUI enabled")
except ImportError as e:
    print(f"⚠️ PyQt5 library not found: {e}")
    print("GUI will not be available. Install PyQt5: pip install PyQt5")
    PYQT5_AVAILABLE = False

# Local imports
from constants import Constants
from logger import Logger, LogLevel
from main_gui import BMWPiRacerIntegratedControl

def setup_can_interfaces():
    """Setup CAN interfaces (BMW CAN only)"""
    print("🔧 Setting up BMW CAN interface...")
    
    # BMW CAN (can0) setup
    result_down = os.system(f"sudo ip link set {Constants.BMW_CAN_CHANNEL} down 2>/dev/null")
    result_up = os.system(f"sudo ip link set {Constants.BMW_CAN_CHANNEL} up type can bitrate {Constants.CAN_BITRATE} 2>/dev/null")
    
    if result_up == 0:
        print(f"✓ BMW CAN interface ({Constants.BMW_CAN_CHANNEL}) configured successfully")
    else:
        print(f"⚠ Failed to configure BMW CAN interface ({Constants.BMW_CAN_CHANNEL})")

def run_headless_mode():
    """Run in headless mode without GUI"""
    print("⚠️ Running in headless mode without GUI")
    print("⚠️ Install PyQt5 to enable the dashboard: pip install PyQt5")
    
    # Setup CAN interfaces
    setup_can_interfaces()
    
    # Headless mode execution
    try:
        # Simple CAN monitoring only
        bus = can.interface.Bus(channel='can0', interface='socketcan')
        print("🚀 Headless mode: Monitoring CAN messages... (Press Ctrl+C to exit)")
        
        while True:
            msg = bus.recv(timeout=1.0)
            if msg and msg.arbitration_id == Constants.LEVER_MESSAGE_ID:  # BMW lever message
                print(f"📨 BMW Lever Message: {msg}")
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error in headless mode: {e}")
        print("💡 Make sure CAN interface is properly configured")

def signal_handler(signum, frame):
    """Handle signals gracefully"""
    print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main function with improved error handling"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Auto-set DISPLAY environment variable
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':0'
            print("🖥️ DISPLAY environment variable auto-set to: :0")
        
        # Startup message
        features = [
            "- BMW Gear Lever Control (P/R/N/D/M1-M8)",
            "- Gamepad Throttle/Steering Control", 
            "- Real-time Speed Display via GPIO16",
            "- BMW CAN Bus + GPIO16 Speed Sensor",
            "- Modular Architecture for Easy Maintenance"
        ]
        
        print("🚀 BMW PiRacer Integrated Control System Started - Modular Version")
        print("Features:")
        for feature in features:
            print(feature)
        
        # Display check (after auto-setting)
        display_available = os.environ.get('DISPLAY') is not None
        
        if PYQT5_AVAILABLE and display_available:
            features.append("- Integrated PyQt5 Dashboard")
            print("🎨 Launching PyQt5 GUI...")
            try:
                # Set Qt application attributes before creating QApplication
                if hasattr(QCoreApplication, 'setAttribute'):
                    from PyQt5.QtCore import Qt
                    QCoreApplication.setAttribute(Qt.AA_X11InitThreads, True)
                
                app = QApplication(sys.argv)
                app.setQuitOnLastWindowClosed(True)
                
                # Auto-setup CAN interfaces
                setup_can_interfaces()
                
                # Create main window with error handling
                print("🏗️ Creating main window...")
                window = BMWPiRacerIntegratedControl()
                print("🌟 Showing GUI window...")
                window.show()
                
                print("✅ GUI launched successfully!")
                return app.exec_()
                
            except Exception as e:
                print(f"❌ GUI launch failed: {e}")
                print(f"📊 Error details: {traceback.format_exc()}")
                print("💡 Running in headless mode instead...")
                run_headless_mode()
        elif PYQT5_AVAILABLE and not display_available:
            print("⚠️ PyQt5 available but no display detected (DISPLAY environment variable not set)")
            print("💡 To run with GUI:")
            print("   - Connect a monitor and run: DISPLAY=:0 python3 main.py")
            print("   - Or use VNC/X11 forwarding")
            print("💡 Running in headless mode...")
            run_headless_mode()
        else:
            run_headless_mode()
            
    except Exception as e:
        print(f"❌ Fatal error in main: {e}")
        print(f"📊 Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 