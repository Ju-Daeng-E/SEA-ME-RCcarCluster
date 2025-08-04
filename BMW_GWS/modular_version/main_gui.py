"""
Main GUI application for BMW PiRacer Integrated Control System
"""

import sys
import threading
import time
from datetime import datetime
from typing import Optional

# PyQt5 imports (optional)
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QFrame, QTextEdit, QGridLayout,
                               QGroupBox, QPushButton, QProgressBar, QShortcut)
    from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject, QThread
    from PyQt5.QtGui import QFont, QKeySequence
    PYQT5_AVAILABLE = True
    BaseMainWindow = QMainWindow
except ImportError as e:
    print(f"⚠️ PyQt5 library not found: {e}")
    print("GUI will not be available. Install PyQt5: pip install PyQt5")
    PYQT5_AVAILABLE = False
    BaseMainWindow = object

# Local imports
from constants import Constants, LogLevel
from data_models import BMWState, PiRacerState
from logger import Logger
from bmw_lever_controller import BMWLeverController
from can_controller import CANController
from speed_sensor import SpeedSensor
from gamepad_controller import GamepadController
from gui_widgets import SpeedometerWidget, GearDisplayWidget

class SignalEmitter(QObject):
    """Native PyQt5 signal emission class"""
    gear_changed = pyqtSignal(str)
    lever_changed = pyqtSignal(str)
    button_changed = pyqtSignal(str, str)
    can_status_changed = pyqtSignal(bool)
    message_received = pyqtSignal(str)
    debug_info = pyqtSignal(str)
    stats_updated = pyqtSignal(int)
    speed_updated = pyqtSignal(float)
    piracer_status_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()

class BMWPiRacerIntegratedControl(BaseMainWindow):
    """BMW PiRacer Integrated Control System GUI - optimized"""
    
    def __init__(self):
        if PYQT5_AVAILABLE:
            super().__init__()
        
        self._init_system()
        if PYQT5_AVAILABLE:
            self._init_ui()
        self._setup_connections()
        self._start_control_loops()
        
    def _init_system(self):
        """System initialization with error handling"""
        try:
            # Logger setup
            self.logger = Logger(LogLevel.INFO)
            
            # Signal initialization
            self.signals = SignalEmitter()
            
            # State objects
            self.bmw_state = BMWState()
            self.piracer_state = PiRacerState()
            
            # Controllers - initialize with proper error handling
            self.lever_controller = BMWLeverController(self.logger)
            self.can_controller = CANController(self.logger)
            self.speed_sensor = SpeedSensor(self.logger, self._on_speed_updated)
            self.gamepad_controller = GamepadController(self.logger, self.piracer_state)
            
            # Statistics
            self.message_count = 0
            self.running = True
            
            # Logger handler addition
            self.logger.add_handler(self.signals.message_received.emit)
            
            # Signal connections
            self._connect_signals()
            
            print("✅ System initialization completed")
            
        except Exception as e:
            print(f"❌ System initialization failed: {e}")
            import traceback
            print(f"📊 Traceback: {traceback.format_exc()}")
            raise
        
    def _connect_signals(self):
        """Signal connections"""
        signal_connections = [
            (self.signals.gear_changed, self.update_gear_display),
            (self.signals.lever_changed, self.update_lever_display),
            (self.signals.button_changed, self.update_button_display),
            (self.signals.can_status_changed, self.update_can_status),
            (self.signals.message_received, self.add_log_message),
            (self.signals.debug_info, self.add_debug_info),
            (self.signals.stats_updated, self.update_stats),
            (self.signals.speed_updated, self.update_speed_display),
            (self.signals.piracer_status_changed, self.update_piracer_status),
        ]
        
        for signal, slot in signal_connections:
            signal.connect(slot)
        
    def _init_ui(self):
        """UI initialization"""
        if not PYQT5_AVAILABLE:
            return
            
        self.setWindowTitle("BMW PiRacer Integrated Control System - Modular")
        self.setGeometry(0, 0, Constants.WINDOW_WIDTH, Constants.WINDOW_HEIGHT)
        self.showFullScreen()
        self.setStyleSheet(self._get_stylesheet())
        
        # ESC key to exit
        self.exit_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.exit_shortcut.activated.connect(self.close)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        
        # UI components (1280x400 optimized)
        main_layout.addLayout(self._create_header())  # Header: ~50px
        main_layout.addLayout(self._create_dashboard(), 3)  # Dashboard: ~200px
        main_layout.addLayout(self._create_status_panel(), 2)  # Status: ~100px
        main_layout.addWidget(self._create_log_panel(), 1)  # Log: ~50px
        
        central_widget.setLayout(main_layout)
        
    def _get_stylesheet(self) -> str:
        """Return stylesheet"""
        return f"""
            QMainWindow {{
                background-color: #1a1a1a;
                color: white;
            }}
            QLabel {{
                color: white;
            }}
            QGroupBox {{
                color: white;
                border: 2px solid {Constants.BMW_BLUE};
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QTextEdit {{
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
            }}
            QPushButton {{
                background-color: {Constants.BMW_BLUE};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #106ebe;
            }}
            QPushButton:pressed {{
                background-color: #005a9e;
            }}
            QProgressBar {{
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
            }}
            QProgressBar::chunk {{
                background-color: {Constants.BMW_BLUE};
                border-radius: 3px;
            }}
        """
        
    def _create_header(self):
        """Create header"""
        if not PYQT5_AVAILABLE:
            return None
            
        header_layout = QHBoxLayout()
        
        # BMW logo (smaller adjustment)
        logo_label = QLabel("🚗 BMW")
        logo_label.setFont(QFont("Arial", 16, QFont.Bold))
        logo_label.setStyleSheet(f"color: {Constants.BMW_BLUE};")
        
        # Title (smaller adjustment)
        title_label = QLabel("PiRacer Control System - Modular")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        
        # Exit button
        self.exit_button = QPushButton("❌ Exit")
        self.exit_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.exit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
            QPushButton:pressed {{
                background-color: #bd2130;
            }}
        """)
        self.exit_button.clicked.connect(self.close)
        
        # Time
        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.time_label.setFont(QFont("Arial", 10))
        self.time_label.setAlignment(Qt.AlignRight)
        
        # Time update timer
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000 // Constants.TIME_UPDATE_RATE)
        
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(self.time_label)
        header_layout.addWidget(self.exit_button)
        
        return header_layout
        
    def _create_dashboard(self):
        """Create dashboard"""
        if not PYQT5_AVAILABLE:
            return None
            
        dashboard_layout = QHBoxLayout()
        
        dashboard_layout.addWidget(self._create_gear_panel(), 1)
        dashboard_layout.addWidget(self._create_speed_panel(), 1)
        dashboard_layout.addWidget(self._create_piracer_panel(), 1)
        
        return dashboard_layout
        
    def _create_gear_panel(self):
        """Create gear display panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("Current Gear")
        layout = QVBoxLayout()
        
        self.gear_widget = GearDisplayWidget()
        self.gear_widget.setMinimumSize(*Constants.GEAR_DISPLAY_SIZE)
        self.gear_widget.setMaximumSize(150, 120)
        layout.addWidget(self.gear_widget)
        
        self.last_update_label = QLabel("Last Update: Never")
        self.last_update_label.setAlignment(Qt.AlignCenter)
        self.last_update_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.last_update_label)
        
        group.setLayout(layout)
        return group
        
    def _create_speed_panel(self):
        """Create speedometer panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("Speedometer (GPIO16)")
        layout = QVBoxLayout()
        
        self.speedometer_widget = SpeedometerWidget()
        self.speedometer_widget.setMinimumSize(*Constants.SPEEDOMETER_SIZE)
        self.speedometer_widget.setMaximumSize(150, 150)
        layout.addWidget(self.speedometer_widget)
        
        self.speed_gear_label = QLabel("Speed Gear: 1")
        self.speed_gear_label.setAlignment(Qt.AlignCenter)
        self.speed_gear_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.speed_gear_label)
        
        group.setLayout(layout)
        return group
        
    def _create_piracer_panel(self):
        """Create PiRacer control panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("PiRacer Control")
        layout = QVBoxLayout()
        
        # Throttle progress bar
        throttle_label = QLabel("Throttle:")
        self.throttle_bar = QProgressBar()
        self.throttle_bar.setRange(-100, 100)
        self.throttle_bar.setValue(0)
        
        # Steering progress bar
        steering_label = QLabel("Steering:")
        self.steering_bar = QProgressBar()
        self.steering_bar.setRange(-100, 100)
        self.steering_bar.setValue(0)
        
        # PiRacer status
        self.piracer_status_label = QLabel("Status: Unknown")
        self.piracer_status_label.setFont(QFont("Arial", 10))
        
        layout.addWidget(throttle_label)
        layout.addWidget(self.throttle_bar)
        layout.addWidget(steering_label)
        layout.addWidget(self.steering_bar)
        layout.addWidget(self.piracer_status_label)
        
        group.setLayout(layout)
        return group
        
    def _create_status_panel(self):
        """Create status panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        status_layout = QHBoxLayout()
        status_layout.addWidget(self._create_bmw_status_panel(), 1)
        status_layout.addWidget(self._create_system_status_panel(), 1)
        return status_layout
        
    def _create_bmw_status_panel(self):
        """Create BMW status panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("BMW Lever Status")
        layout = QVBoxLayout()
        
        # Lever position
        self.lever_pos_label = QLabel("Lever Position:")
        self.lever_pos_value = QLabel("Unknown")
        self.lever_pos_value.setFont(QFont("Arial", 12, QFont.Bold))
        self.lever_pos_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
        
        # Button states
        self.park_btn_label = QLabel("Park Button:")
        self.park_btn_value = QLabel("Released")
        self.unlock_btn_label = QLabel("Unlock Button:")
        self.unlock_btn_value = QLabel("Released")
        
        for widget in [self.lever_pos_label, self.lever_pos_value, 
                      self.park_btn_label, self.park_btn_value,
                      self.unlock_btn_label, self.unlock_btn_value]:
            layout.addWidget(widget)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
        
    def _create_system_status_panel(self):
        """Create system status panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("System Status")
        layout = QVBoxLayout()
        
        # CAN status
        self.can_status_label = QLabel("BMW CAN:")
        self.can_status_value = QLabel("Disconnected")
        self.can_status_value.setStyleSheet(f"color: {Constants.ERROR_RED};")
        
        self.speed_sensor_label = QLabel("Speed Sensor:")
        self.speed_sensor_value = QLabel("GPIO Ready")
        self.speed_sensor_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
        
        # Message counter
        self.msg_count_label = QLabel("Messages:")
        self.msg_count_value = QLabel("0")
        
        # Control buttons
        self.connect_btn = QPushButton("Connect CAN")
        self.connect_btn.clicked.connect(self._toggle_can_connection)
        
        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.clicked.connect(self._clear_logs)
        
        for widget in [self.can_status_label, self.can_status_value,
                      self.speed_sensor_label, self.speed_sensor_value,
                      self.msg_count_label, self.msg_count_value,
                      self.connect_btn, self.clear_btn]:
            layout.addWidget(widget)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
        
    def _create_log_panel(self):
        """Create log panel"""
        if not PYQT5_AVAILABLE:
            return None
            
        group = QGroupBox("Real-time System Logs")
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(40)  # Reduced log area
        self.log_text.setFont(QFont("Consolas", Constants.LOG_FONT_SIZE))
        
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group
        
    def _setup_connections(self):
        """Setup connections"""
        bmw_ok = self.can_controller.setup_can_interfaces()
        self.signals.can_status_changed.emit(bmw_ok)
        
        if bmw_ok:
            self._start_bmw_monitoring()
            self._start_led_control()
        
        # Start speed sensor
        self.speed_sensor.start()
        
        # Start gamepad controller
        self.gamepad_controller.start()
            
    def _start_control_loops(self):
        """Start control loops"""
        pass  # Gamepad control is handled by GamepadController
        
    def _start_bmw_monitoring(self):
        """Start BMW CAN monitoring with proper Qt threading"""
        class BMWMonitorThread(QThread):
            message_ready = pyqtSignal(object)
            error_occurred = pyqtSignal(str)
            
            def __init__(self, can_controller, running_flag):
                super().__init__()
                self.can_controller = can_controller
                self.running_flag = running_flag
            
            def run(self):
                while self.running_flag() and self.can_controller.bmw_bus:
                    try:
                        msg = self.can_controller.bmw_bus.recv(timeout=Constants.BMW_CAN_TIMEOUT)
                        if msg:
                            self.message_ready.emit(msg)
                    except Exception as e:
                        if self.running_flag():
                            self.error_occurred.emit(f"BMW CAN Error: {e}")
                            time.sleep(0.1)
        
        self.bmw_thread = BMWMonitorThread(self.can_controller, lambda: self.running)
        self.bmw_thread.message_ready.connect(self._bmw_message_handler)
        self.bmw_thread.error_occurred.connect(lambda msg: self.logger.error(msg))
        self.bmw_thread.start()
    
    def _on_speed_updated(self, speed_kmh: float):
        """Speed update callback"""
        self.piracer_state.current_speed = speed_kmh
        self.signals.speed_updated.emit(speed_kmh)
    
    def _start_led_control(self):
        """Start LED control with proper Qt threading"""
        class LEDControlThread(QThread):
            def __init__(self, can_controller, bmw_state, running_flag):
                super().__init__()
                self.can_controller = can_controller
                self.bmw_state = bmw_state
                self.running_flag = running_flag
            
            def run(self):
                update_interval = 1.0 / Constants.LED_UPDATE_RATE
                
                while self.running_flag() and self.can_controller.bmw_bus:
                    if self.bmw_state.current_gear != 'Unknown':
                        self.can_controller.send_gear_led(self.bmw_state.current_gear, flash=False)
                    time.sleep(update_interval)
        
        if self.can_controller.bmw_bus:
            self.led_thread = LEDControlThread(self.can_controller, self.bmw_state, lambda: self.running)
            self.led_thread.start()
    
    def _bmw_message_handler(self, msg):
        """BMW CAN message handler"""
        self.message_count += 1
        self.signals.stats_updated.emit(self.message_count)
        
        if msg.arbitration_id == Constants.LEVER_MESSAGE_ID:
            # BMW gear lever message
            if self.lever_controller.decode_lever_message(msg, self.bmw_state):
                # UI update signal emission
                self.signals.lever_changed.emit(self.bmw_state.lever_position)
                self.signals.button_changed.emit(self.bmw_state.park_button, self.bmw_state.unlock_button)
                self.signals.gear_changed.emit(self.bmw_state.current_gear)
                
                # Gear change LED update
                if self.bmw_state.current_gear != 'Unknown':
                    self.can_controller.send_gear_led(self.bmw_state.current_gear, flash=False)
    
    # UI update methods
    def _update_time(self):
        """Update time"""
        if PYQT5_AVAILABLE and hasattr(self, 'time_label'):
            self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
    
    def update_gear_display(self, gear: str):
        """Update gear display"""
        if hasattr(self, 'gear_widget'):
            self.gear_widget.set_gear(gear, self.bmw_state.manual_gear)
        if hasattr(self, 'last_update_label') and self.bmw_state.last_update:
            self.last_update_label.setText(f"Last Update: {self.bmw_state.last_update}")
    
    def update_lever_display(self, lever_pos: str):
        """Update lever position display"""
        if hasattr(self, 'lever_pos_value'):
            self.lever_pos_value.setText(lever_pos)
    
    def update_button_display(self, park_btn: str, unlock_btn: str):
        """Update button state display"""
        if not PYQT5_AVAILABLE:
            return
            
        if hasattr(self, 'park_btn_value'):
            self.park_btn_value.setText(park_btn)
        if hasattr(self, 'unlock_btn_value'):
            self.unlock_btn_value.setText(unlock_btn)
        
        park_color = "#ff4444" if park_btn == "Pressed" else "#44ff44"
        unlock_color = "#ff4444" if unlock_btn == "Pressed" else "#44ff44"
        
        if hasattr(self, 'park_btn_value'):
            self.park_btn_value.setStyleSheet(f"color: {park_color};")
        if hasattr(self, 'unlock_btn_value'):
            self.unlock_btn_value.setStyleSheet(f"color: {unlock_color};")
    
    def update_can_status(self, connected: bool):
        """Update CAN status"""
        if not PYQT5_AVAILABLE:
            return
            
        if hasattr(self, 'can_status_value'):
            if connected:
                self.can_status_value.setText("Connected")
                self.can_status_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
            else:
                self.can_status_value.setText("Disconnected")
                self.can_status_value.setStyleSheet(f"color: {Constants.ERROR_RED};")
    
    def update_speed_display(self, speed: float):
        """Update speed display"""
        if hasattr(self, 'speedometer_widget'):
            self.speedometer_widget.set_speed(speed)
        if hasattr(self, 'speed_gear_label'):
            self.speed_gear_label.setText(f"Speed Gear: {self.piracer_state.speed_gear}")
        
        # Update throttle and steering bars
        if hasattr(self, 'throttle_bar'):
            self.throttle_bar.setValue(int(self.gamepad_controller.get_throttle_input() * 100))
        if hasattr(self, 'steering_bar'):
            self.steering_bar.setValue(int(self.gamepad_controller.get_steering_input() * 100))
    
    def update_piracer_status(self, status: str):
        """Update PiRacer status"""
        if hasattr(self, 'piracer_status_label'):
            self.piracer_status_label.setText(f"Status: {status}")
    
    def update_stats(self, count: int):
        """Update statistics"""
        if hasattr(self, 'msg_count_value'):
            self.msg_count_value.setText(str(count))
    
    def add_log_message(self, message: str):
        """Add log message"""
        if not PYQT5_AVAILABLE:
            return
            
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        if hasattr(self, 'log_text'):
            self.log_text.append(f"{timestamp} {message}")
            
            # Remove top lines if log gets too long
            if self.log_text.document().blockCount() > Constants.MAX_LOG_LINES:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.select(cursor.BlockUnderCursor)
                cursor.removeSelectedText()
    
    def add_debug_info(self, debug_msg: str):
        """Add debug info"""
        self.add_log_message(debug_msg)
    
    def _clear_logs(self):
        """Clear logs"""
        if hasattr(self, 'log_text'):
            self.log_text.clear()
        self.logger.info("🧹 Logs cleared")
    
    def _toggle_can_connection(self):
        """Toggle CAN connection"""
        self._clear_logs()
        self.logger.info("🔄 Reconnecting CAN interfaces...")
        self._setup_connections()
    
    def closeEvent(self, event):
        """Program exit"""
        print("🛑 Closing application...")
        self.running = False
        
        # Clean shutdown of all components
        try:
            if hasattr(self, 'can_controller'):
                self.can_controller.shutdown()
        except Exception as e:
            print(f"⚠️ Error shutting down CAN controller: {e}")
            
        try:
            if hasattr(self, 'speed_sensor'):
                self.speed_sensor.cleanup()
        except Exception as e:
            print(f"⚠️ Error cleaning up speed sensor: {e}")
            
        try:
            if hasattr(self, 'gamepad_controller'):
                self.gamepad_controller.stop()
        except Exception as e:
            print(f"⚠️ Error stopping gamepad controller: {e}")
        
        # Stop all timers
        try:
            if hasattr(self, 'time_timer'):
                self.time_timer.stop()
        except Exception as e:
            print(f"⚠️ Error stopping timer: {e}")
        
        # Stop Qt threads properly
        try:
            if hasattr(self, 'bmw_thread'):
                self.bmw_thread.quit()
                self.bmw_thread.wait(3000)  # Wait up to 3 seconds
        except Exception as e:
            print(f"⚠️ Error stopping BMW thread: {e}")
            
        try:
            if hasattr(self, 'led_thread'):
                self.led_thread.quit()
                self.led_thread.wait(3000)  # Wait up to 3 seconds
        except Exception as e:
            print(f"⚠️ Error stopping LED thread: {e}")
        
        if PYQT5_AVAILABLE and event:
            event.accept()
        
        print("✅ Application closed successfully")
    
    def show(self):
        """Show the window"""
        if PYQT5_AVAILABLE:
            super().show()
    
    def close(self):
        """Close the window"""
        if PYQT5_AVAILABLE:
            super().close()
        else:
            self.closeEvent(None) 