#!/usr/bin/env python3
"""
BMW Controller - Fixed GUI Version
PyQt5 초기화 오류를 방지하고 안전한 GUI 구현
"""

import sys
import os
import can
import time
import threading
import logging
import RPi.GPIO as GPIO
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
    print("✅ PiRacer imports successful")
except ImportError as e:
    print(f"❌ PiRacer import failed: {e}")
    PIRACER_AVAILABLE = False
    sys.exit(1)

# PyQt5 안전한 import
GUI_AVAILABLE = False
try:
    # DISPLAY 환경변수 설정
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
    
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QFrame)
    from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont
    
    # QApplication 미리 테스트
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    
    GUI_AVAILABLE = True
    print("✅ PyQt5 GUI available")
    
except Exception as e:
    print(f"⚠️ PyQt5 GUI not available: {e}")
    print("Will run in console mode only")
    GUI_AVAILABLE = False

@dataclass
class VehicleState:
    speed: float = 0.0
    gear: str = "P"
    manual_gear: int = 1
    throttle: float = 0.0
    steering: float = 0.0

class SafeSpeedometer(QWidget):
    """안전한 속도계 위젯"""
    def __init__(self):
        super().__init__()
        self.current_speed = 0.0
        self.max_speed = 30.0
        self.setFixedSize(200, 200)
        
    def set_speed(self, speed: float):
        """속도 설정 (안전한 업데이트)"""
        new_speed = max(0, min(speed, self.max_speed))
        if abs(self.current_speed - new_speed) > 0.1:
            self.current_speed = new_speed
            # 안전한 업데이트
            self.update()
        
    def paintEvent(self, event):
        """그리기 이벤트 (안전하게 구현)"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), QColor(20, 20, 20))
            
            # 속도 텍스트
            painter.setPen(QPen(QColor(0, 255, 100), 2))
            painter.setFont(QFont("Arial", 24, QFont.Bold))
            
            speed_text = f"{self.current_speed:.1f}"
            text_rect = painter.fontMetrics().boundingRect(speed_text)
            
            x = (self.width() - text_rect.width()) // 2
            y = (self.height() + text_rect.height()) // 2
            
            painter.drawText(x, y, speed_text)
            
            # km/h 단위
            painter.setFont(QFont("Arial", 12))
            painter.drawText(x, y + 20, "km/h")
            
        except Exception as e:
            print(f"❌ Paint error: {e}")

class SafeGearDisplay(QWidget):
    """안전한 기어 표시 위젯"""
    def __init__(self):
        super().__init__()
        self.current_gear = "P"
        self.manual_gear = 1
        self.setFixedSize(150, 100)
        
    def set_gear(self, gear: str, manual_gear: int = 1):
        """기어 설정 (안전한 업데이트)"""
        if self.current_gear != gear or self.manual_gear != manual_gear:
            self.current_gear = gear
            self.manual_gear = manual_gear
            self.update()
        
    def paintEvent(self, event):
        """그리기 이벤트"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), QColor(20, 20, 20))
            
            # 기어 텍스트
            painter.setPen(QPen(QColor(0, 120, 215), 2))
            painter.setFont(QFont("Arial", 32, QFont.Bold))
            
            gear_text = self.current_gear
            if self.current_gear == 'M':
                gear_text += str(self.manual_gear)
                
            text_rect = painter.fontMetrics().boundingRect(gear_text)
            x = (self.width() - text_rect.width()) // 2
            y = (self.height() + text_rect.height()) // 2
            
            painter.drawText(x, y, gear_text)
            
        except Exception as e:
            print(f"❌ Gear paint error: {e}")

class SafeMainWindow(QMainWindow):
    """안전한 메인 윈도우"""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("BMW PiRacer Controller - Safe GUI")
        self.setGeometry(100, 100, 800, 600)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 레이아웃
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 상단 레이아웃
        top_layout = QHBoxLayout()
        
        # 속도계
        self.speedometer = SafeSpeedometer()
        top_layout.addWidget(self.speedometer)
        
        # 기어 표시
        self.gear_display = SafeGearDisplay()
        top_layout.addWidget(self.gear_display)
        
        main_layout.addLayout(top_layout)
        
        # 상태 라벨
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("color: white; background-color: #2b2b2b; padding: 10px;")
        main_layout.addWidget(self.status_label)
        
        # 업데이트 타이머
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.safe_update)
        self.update_timer.start(100)  # 100ms 주기
        
        print("✅ Safe GUI initialized")
        
    def safe_update(self):
        """안전한 GUI 업데이트"""
        try:
            state = self.controller.state
            
            # 속도 업데이트
            self.speedometer.set_speed(state.speed)
            
            # 기어 업데이트
            self.gear_display.set_gear(state.gear, state.manual_gear)
            
            # 상태 업데이트
            status = (f"Speed: {state.speed:.1f} km/h | "
                     f"Gear: {state.gear} | "
                     f"Throttle: {state.throttle:+.1f} | "
                     f"Steering: {state.steering:+.1f}")
            self.status_label.setText(status)
            
        except Exception as e:
            print(f"❌ GUI update error: {e}")
            
    def closeEvent(self, event):
        """안전한 종료"""
        print("🛑 GUI closing...")
        self.update_timer.stop()
        self.controller.running = False
        event.accept()

class BMWControllerFixedGUI:
    def __init__(self):
        self.running = False
        self.state = VehicleState()
        
        # 로깅 설정
        self.setup_logging()
        
        # CAN 설정
        self.can_bus = None
        self.setup_can()
        
        # GPIO 설정
        self.speed_pin = 18
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.speed_pin, GPIO.IN)
        
        # PiRacer 설정
        if PIRACER_AVAILABLE:
            self.piracer = PiRacerStandard()
            self.gamepad = ShanWanGamepad()
            self.logger.info("✅ PiRacer initialized")
        
        # GUI 설정
        self.app = None
        self.window = None
        
        if GUI_AVAILABLE:
            self.setup_gui()
        
    def setup_logging(self):
        """로깅 설정"""
        os.makedirs("logs", exist_ok=True)
        log_file = f'logs/bmw_fixed_gui_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] [%(levelname)-7s] %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"📝 Session log file: {log_file}")
        
    def setup_can(self):
        """CAN 설정"""
        try:
            self.can_bus = can.interface.Bus(channel='can0', interface='socketcan')
            self.logger.info("✅ BMW CAN bus initialized")
        except Exception as e:
            self.logger.error(f"❌ CAN setup failed: {e}")
            
    def setup_gui(self):
        """GUI 설정"""
        try:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
            
            self.window = SafeMainWindow(self)
            self.logger.info("✅ GUI setup completed")
            
        except Exception as e:
            self.logger.error(f"❌ GUI setup failed: {e}")
            global GUI_AVAILABLE
            GUI_AVAILABLE = False
            
    def run(self):
        """메인 실행"""
        self.logger.info("🚗 BMW Controller Starting...")
        self.running = True
        
        try:
            if GUI_AVAILABLE and self.window:
                self.window.show()
                self.logger.info("✅ GUI shown")
                
                # 제어 스레드
                control_thread = threading.Thread(target=self.control_loop, daemon=True)
                control_thread.start()
                
                # GUI 이벤트 루프
                self.app.exec_()
            else:
                self.logger.info("Running in console mode")
                self.control_loop()
                
        except Exception as e:
            self.logger.error(f"❌ Runtime error: {e}")
        finally:
            self.cleanup()
            
    def control_loop(self):
        """제어 루프"""
        while self.running:
            try:
                if PIRACER_AVAILABLE:
                    gamepad_data = self.gamepad.read_data()
                    
                    if gamepad_data:
                        throttle = gamepad_data.analog_stick_right.y * 0.5
                        steering = gamepad_data.analog_stick_left.x
                        
                        if self.state.gear in ['D', 'R', 'M']:
                            if self.state.gear == 'R':
                                throttle = -abs(throttle)
                                
                            self.piracer.set_throttle_percent(throttle)
                            self.piracer.set_steering_percent(steering)
                            
                            self.state.throttle = throttle
                            self.state.steering = steering
                        else:
                            self.piracer.set_throttle_percent(0.0)
                            self.piracer.set_steering_percent(0.0)
                            self.state.throttle = 0.0
                            self.state.steering = 0.0
                
                time.sleep(0.1)
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Control loop error: {e}")
                    time.sleep(1.0)
                    
    def cleanup(self):
        """정리"""
        self.logger.info("🔧 Starting cleanup...")
        self.running = False
        
        if PIRACER_AVAILABLE:
            self.piracer.set_throttle_percent(0.0)
            self.piracer.set_steering_percent(0.0)
            
        if self.can_bus:
            self.can_bus.shutdown()
            
        GPIO.cleanup()
        self.logger.info("✅ Cleanup completed")

if __name__ == "__main__":
    controller = BMWControllerFixedGUI()
    controller.run()