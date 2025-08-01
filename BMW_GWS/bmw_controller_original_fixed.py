#!/usr/bin/env python3
"""
BMW PiRacer Controller - Original Fixed Version
원본 기능을 유지하면서 segfault 문제만 해결한 버전
"""

import sys
import os

# 환경 변수 먼저 설정
if not os.environ.get('DISPLAY'):
    os.environ['DISPLAY'] = ':0'

# 필요한 모듈들 import
import can
import time
import threading
import crccheck
import logging
import RPi.GPIO as GPIO
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from multiprocessing import Process, Value, Array

# PyQt5 안전한 import
GUI_AVAILABLE = False
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QFrame, QTextEdit, QGridLayout,
                               QGroupBox, QPushButton, QProgressBar)
    from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
    
    # QApplication 테스트
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
        test_app.processEvents()
        
    GUI_AVAILABLE = True
    print("✅ PyQt5 GUI available and tested")
    
except Exception as e:
    print(f"⚠️ PyQt5 GUI not available: {e}, running in console mode")
    GUI_AVAILABLE = False

# PiRacer import
try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
    print("✅ PiRacer imports successful")
except ImportError as e:
    print(f"❌ PiRacer import failed: {e}")
    PIRACER_AVAILABLE = False
    sys.exit(1)

# 기본 클래스들
class BMWGear(Enum):
    PARK = "P"
    REVERSE = "R" 
    NEUTRAL = "N"
    DRIVE = "D"
    MANUAL = "M"

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
        self.update_pending = False
        
    def set_speed(self, speed: float):
        """속도 설정 (안전한 업데이트)"""
        new_speed = max(0, min(speed, self.max_speed))
        if abs(self.current_speed - new_speed) > 0.1 and not self.update_pending:
            self.current_speed = new_speed
            self.update_pending = True
            QTimer.singleShot(100, self.safe_update)
            
    def safe_update(self):
        """안전한 업데이트"""
        self.update_pending = False
        self.update()
        
    def paintEvent(self, event):
        """안전한 그리기"""
        painter = None
        try:
            painter = QPainter(self)
            if not painter.isActive():
                return
                
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), QColor(30, 30, 30))
            
            # 속도 텍스트
            painter.setPen(QPen(QColor(0, 255, 100), 2))
            painter.setFont(QFont("Arial", 24, QFont.Bold))
            
            speed_text = f"{self.current_speed:.1f}"
            painter.drawText(self.rect(), Qt.AlignCenter, speed_text)
            
            # 단위
            painter.setFont(QFont("Arial", 12))
            unit_rect = self.rect().adjusted(0, 30, 0, 0)
            painter.drawText(unit_rect, Qt.AlignCenter, "km/h")
            
        except Exception as e:
            print(f"❌ Speedometer paint error: {e}")
        finally:
            if painter and painter.isActive():
                painter.end()

class SafeGearDisplay(QWidget):
    """안전한 기어 표시 위젯"""
    def __init__(self):
        super().__init__()
        self.current_gear = "P"
        self.manual_gear = 1
        self.setFixedSize(150, 100)
        self.update_pending = False
        
    def set_gear(self, gear: str, manual_gear: int = 1):
        """기어 설정 (안전한 업데이트)"""
        if (self.current_gear != gear or self.manual_gear != manual_gear) and not self.update_pending:
            self.current_gear = gear
            self.manual_gear = manual_gear
            self.update_pending = True
            QTimer.singleShot(100, self.safe_update)
            
    def safe_update(self):
        """안전한 업데이트"""
        self.update_pending = False
        self.update()
        
    def paintEvent(self, event):
        """안전한 그리기"""
        painter = None
        try:
            painter = QPainter(self)
            if not painter.isActive():
                return
                
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), QColor(20, 20, 20))
            
            # 기어 텍스트
            color = QColor(0, 120, 215)
            if self.current_gear == 'D':
                color = QColor(0, 255, 0)
            elif self.current_gear == 'R':
                color = QColor(255, 0, 0)
            elif self.current_gear == 'P':
                color = QColor(255, 255, 0)
                
            painter.setPen(QPen(color, 2))
            painter.setFont(QFont("Arial", 32, QFont.Bold))
            
            gear_text = self.current_gear
            if self.current_gear == 'M':
                gear_text += str(self.manual_gear)
                
            painter.drawText(self.rect(), Qt.AlignCenter, gear_text)
            
        except Exception as e:
            print(f"❌ Gear display paint error: {e}")
        finally:
            if painter and painter.isActive():
                painter.end()

class SafeMainWindow(QMainWindow):
    """안전한 메인 윈도우"""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("BMW PiRacer Controller - Safe Original")
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
        
        # 업데이트 타이머 (느린 속도로 안전하게)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.safe_update)
        self.update_timer.start(200)  # 200ms 주기 (5Hz)
        
        print("✅ Safe GUI window initialized")
        
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
                     f"T: {state.throttle:+.2f} | "
                     f"S: {state.steering:+.2f}")
            self.status_label.setText(status)
            
        except Exception as e:
            print(f"❌ GUI update error: {e}")
            
    def closeEvent(self, event):
        """안전한 종료"""
        print("🛑 GUI closing...")
        self.update_timer.stop()
        self.controller.running = False
        event.accept()

class OriginalFixedController:
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
        self.piracer = None
        self.gamepad = None
        if PIRACER_AVAILABLE:
            try:
                self.piracer = PiRacerStandard()
                self.gamepad = ShanWanGamepad()
                self.logger.info("✅ PiRacer and Gamepad initialized")
            except Exception as e:
                self.logger.error(f"❌ PiRacer init failed: {e}")
        
        # GUI 설정
        self.app = None
        self.window = None
        
    def setup_logging(self):
        """로깅 설정"""
        os.makedirs("logs", exist_ok=True)
        log_file = f'logs/bmw_original_fixed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
            
    def gear_listener(self):
        """기어 상태 수신"""
        self.logger.info("🔍 Gear listener started")
        
        while self.running:
            try:
                if self.can_bus:
                    message = self.can_bus.recv(timeout=1.0)
                    if message and message.arbitration_id == 0x12F:
                        gear_data = self.parse_gear_data(message.data)
                        if gear_data:
                            old_gear = self.state.gear
                            self.state.gear = gear_data['gear']
                            self.state.manual_gear = gear_data.get('manual_gear', 1)
                            
                            if old_gear != self.state.gear:
                                self.logger.info(f"🔧 Gear: {old_gear} → {self.state.gear}")
                else:
                    time.sleep(1.0)
                    
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Gear listener error: {e}")
                    time.sleep(1.0)
                    
    def parse_gear_data(self, data: bytes) -> Optional[Dict]:
        """기어 데이터 파싱"""
        if len(data) >= 2:
            gear_byte = data[1]
            gear_map = {0x10: 'P', 0x20: 'R', 0x30: 'N', 0x40: 'D', 0x50: 'M'}
            gear = gear_map.get(gear_byte & 0xF0, 'Unknown')
            manual_gear = data[0] if gear == 'M' else 1
            return {'gear': gear, 'manual_gear': manual_gear}
        return None
        
    def safe_control(self, throttle: float, steering: float) -> bool:
        """안전한 PiRacer 제어"""
        if not self.piracer:
            return False
            
        try:
            # 안전 제한
            throttle = max(-0.4, min(0.4, throttle))  # 40% 제한
            steering = max(-0.6, min(0.6, steering))  # 60% 제한
            
            # 실제 제어
            self.piracer.set_throttle_percent(throttle)
            self.piracer.set_steering_percent(steering)
            
            self.state.throttle = throttle
            self.state.steering = steering
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Control error: {e}")
            # 에러 시 안전 정지
            try:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
            except:
                pass
            return False
        
    def control_loop(self):
        """제어 루프"""
        while self.running:
            try:
                if self.gamepad:
                    gamepad_data = self.gamepad.read_data()
                    
                    if gamepad_data:
                        raw_throttle = gamepad_data.analog_stick_right.y
                        raw_steering = gamepad_data.analog_stick_left.x
                        
                        # 기어에 따른 제어
                        if self.state.gear in ['D', 'R', 'M']:
                            throttle = raw_throttle * 0.4  # 40%로 제한
                            steering = raw_steering * 0.6  # 60%로 제한
                            
                            if self.state.gear == 'R':
                                throttle = -abs(throttle)  # 후진
                                
                            # 안전한 제어 적용
                            self.safe_control(throttle, steering)
                            
                        else:
                            # P 또는 N에서는 정지
                            self.safe_control(0.0, 0.0)
                
                time.sleep(0.05)  # 20Hz
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Control loop error: {e}")
                    time.sleep(1.0)
                    
    def setup_gui(self):
        """GUI 설정"""
        if not GUI_AVAILABLE:
            return False
            
        try:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
            
            self.window = SafeMainWindow(self)
            self.logger.info("✅ GUI setup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ GUI setup failed: {e}")
            return False
            
    def run(self):
        """메인 실행"""
        self.logger.info("🚗 BMW Original Fixed Controller Starting...")
        self.running = True
        
        # 기어 리스너 스레드 시작
        gear_thread = threading.Thread(target=self.gear_listener, daemon=True)
        gear_thread.start()
        
        try:
            if GUI_AVAILABLE and self.setup_gui():
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
            
    def cleanup(self):
        """정리"""
        self.logger.info("🔧 Starting cleanup...")
        self.running = False
        
        if self.piracer:
            try:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
                self.logger.info("✅ Vehicle stopped")
            except:
                pass
            
        if self.can_bus:
            self.can_bus.shutdown()
            self.logger.info("✅ CAN bus closed")
            
        GPIO.cleanup()
        self.logger.info("✅ GPIO cleaned up")
        
        self.logger.info("🏁 BMW Original Fixed Controller shutdown complete")

if __name__ == "__main__":
    controller = OriginalFixedController()
    controller.run()