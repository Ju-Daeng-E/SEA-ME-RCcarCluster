#!/usr/bin/env python3
"""
BMW PiRacer Integrated Control System - GPIO Speed Optimized
BMW F-Series 기어 레버 + PiRacer 제어 + PyQt5 GUI 통합 시스템 (GPIO18 속도 입력)

기능:
- BMW 기어봉으로 기어 제어 (P/R/N/D/M1-M8)
- 게임패드로 스로틀/스티어링 제어
- 실시간 속도 표시 (GPIO16 핀 입력)
- PyQt5 GUI 대시보드
- CAN 대신 GPIO16에서 직접 속도 데이터 수신

최적화 사항:
- GPIO16 핀에서 직접 속도 센서 데이터 읽기
- CAN 속도 버스 제거, BMW CAN만 사용
- 타입 힌트 추가로 코드 안정성 향상
- 상수를 클래스 상단으로 이동
- 캐싱을 통한 CRC 계산 최적화
- 로그 레벨 시스템 도입
- 예외 처리 개선
- 코드 중복 제거 및 메서드 분리
- 성능 최적화 (업데이트 주기 조정)
"""

import sys
import os
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

# PyQt5 import (선택적)
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QFrame, QTextEdit, QGridLayout,
                               QGroupBox, QPushButton, QProgressBar)
    from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
    PYQT5_AVAILABLE = True
    print("✅ PyQt5 successfully imported - GUI enabled")
except ImportError as e:
    print(f"⚠️ PyQt5 라이브러리를 찾을 수 없습니다: {e}")
    print("GUI 없이 실행됩니다. PyQt5 설치: pip install PyQt5")
    PYQT5_AVAILABLE = False
    
    # Mock classes for when PyQt5 is not available
    class QObject:
        pass
    class QMainWindow:
        def __init__(self): pass
        def show(self): pass
        def setWindowTitle(self, title): pass
        def setGeometry(self, x, y, w, h): pass
        def showFullScreen(self): pass
        def setStyleSheet(self, style): pass
        def setCentralWidget(self, widget): pass
        def closeEvent(self, event): pass
    class QWidget:
        def __init__(self): pass
        def setLayout(self, layout): pass
        def setMinimumSize(self, w, h): pass
        def setMaximumSize(self, w, h): pass
        def update(self): pass
        def width(self): return 100
        def height(self): return 100
        def rect(self): return type('MockRect', (), {'adjusted': lambda *args: self})()
        def paintEvent(self, event): pass
    class QApplication:
        def __init__(self, args): pass
        def exec_(self): return 0
    class QVBoxLayout:
        def __init__(self): pass
        def addWidget(self, widget, stretch=0): pass
        def addLayout(self, layout, stretch=0): pass
        def addStretch(self): pass
    class QHBoxLayout:
        def __init__(self): pass
        def addWidget(self, widget, stretch=0): pass
        def addLayout(self, layout, stretch=0): pass
    class QLabel:
        def __init__(self, text=""):
            self.text = text
        def setText(self, text): self.text = text
        def setFont(self, font): pass
        def setAlignment(self, alignment): pass
        def setStyleSheet(self, style): pass
    class QGroupBox:
        def __init__(self, title=""): pass
        def setLayout(self, layout): pass
    class QTextEdit:
        def __init__(self): pass
        def setMaximumHeight(self, h): pass
        def setFont(self, font): pass
        def append(self, text): pass
        def clear(self): pass
        def document(self): return type('MockDoc', (), {'blockCount': lambda: 10})()
        def textCursor(self): return type('MockCursor', (), {
            'movePosition': lambda pos: None,
            'select': lambda sel: None,
            'removeSelectedText': lambda: None,
            'Start': 0, 'BlockUnderCursor': 0
        })()
    class QPushButton:
        def __init__(self, text=""): pass
        def clicked(self): return type('MockSignal', (), {'connect': lambda func: None})()
    class QProgressBar:
        def __init__(self): pass
        def setRange(self, min_val, max_val): pass
        def setValue(self, val): pass
    class QTimer:
        def __init__(self): pass
        def timeout(self): return type('MockSignal', (), {'connect': lambda func: None})()
        def start(self, interval): pass
    class QFont:
        def __init__(self, name, size=10, weight=50): pass
        Bold = 75
    class QPainter:
        def __init__(self, widget): pass
        def setRenderHint(self, hint): pass
        def fillRect(self, rect, color): pass
        def setPen(self, pen): pass
        def drawRoundedRect(self, rect, rx, ry): pass
        def drawEllipse(self, x, y, w, h): pass
        def setFont(self, font): pass
        def drawText(self, rect, alignment, text): pass
        Antialiasing = 1
    class QPen:
        def __init__(self, color, width=1): pass
    class QColor:
        def __init__(self, *args): pass
    class Qt:
        AlignCenter = 0x0084
        AlignRight = 0x0002
    class pyqtSignal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, func): pass

# PiRacer 및 게임패드 import (상세 디버깅 포함)
print("🔍 Starting PiRacer library import...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python executable: {sys.executable}")

try:
    print("🔍 Attempting to import piracer module...")
    import piracer
    print(f"✅ piracer module found at: {piracer.__file__}")
    
    print("🔍 Importing PiRacerStandard...")
    from piracer.vehicles import PiRacerStandard
    print("✅ PiRacerStandard import successful")
    
    print("🔍 Importing ShanWanGamepad...")
    from piracer.gamepads import ShanWanGamepad
    print("✅ ShanWanGamepad import successful")
    
    PIRACER_AVAILABLE = True
    GAMEPAD_CLASS = ShanWanGamepad  # 전역 변수로 저장
    print("✅ All PiRacer imports successful - PIRACER_AVAILABLE = True")
    
except ImportError as e:
    print(f"❌ PiRacer import failed: {e}")
    print(f"🔍 Import error type: {type(e).__name__}")
    import traceback
    print(f"📋 Import traceback:\n{traceback.format_exc()}")
    print("⚠️ 시뮬레이션 모드로 실행됩니다.")
    
    PIRACER_AVAILABLE = False
    PiRacerStandard = None
    GAMEPAD_CLASS = None  # import 실패시 None으로 설정
    
print(f"📊 Final PIRACER_AVAILABLE status: {PIRACER_AVAILABLE}")
print(f"📊 Final GAMEPAD_CLASS status: {GAMEPAD_CLASS is not None}")

# 상수 정의
class Constants:
    # CAN 관련
    BMW_CAN_CHANNEL = 'can0'
    CAN_BITRATE = 500000
    LEVER_MESSAGE_ID = 0x197
    LED_MESSAGE_ID = 0x3FD
    HEARTBEAT_MESSAGE_ID = 0x55e
    
    # 속도센서 관련 (GPIO) 
    SPEED_SENSOR_PIN = 16  # GPIO 16 (Physical Pin 36)
    PULSES_PER_TURN = 40  # encoder wheel: 20 slots × 2 (rising+falling)
    WHEEL_DIAMETER_MM = 64  # mm
    
    # 타이밍
    BMW_CAN_TIMEOUT = 1.0
    GAMEPAD_UPDATE_RATE = 20  # Hz
    LED_UPDATE_RATE = 10  # Hz
    TIME_UPDATE_RATE = 1  # Hz
    TOGGLE_TIMEOUT = 0.5
    SPEED_CALCULATION_INTERVAL = 1.0  # 속도 계산 간격 (초)
    PULSE_DEBOUNCE_MICROS = 700  # 펄스 디바운싱 마이크로초
    
    # UI 관련 (1280x400 최적화)
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 400
    MAX_LOG_LINES = 30
    LOG_FONT_SIZE = 7
    SPEEDOMETER_SIZE = (100, 100)
    GEAR_DISPLAY_SIZE = (100, 80)
    
    # 성능 관련
    MAX_SPEED = 50.0  # km/h
    SPEED_GEARS = 4
    MANUAL_GEARS = 8
    
    # 색상
    BMW_BLUE = "#0078d4"
    SUCCESS_GREEN = "#00ff00"
    ERROR_RED = "#ff0000"
    WARNING_ORANGE = "#ff8800"

class GearType(Enum):
    """기어 타입 열거형"""
    PARK = 'P'
    REVERSE = 'R'
    NEUTRAL = 'N'
    DRIVE = 'D'
    SPORT = 'S'
    MANUAL = 'M'
    UNKNOWN = 'Unknown'

class LeverPosition(Enum):
    """레버 위치 열거형"""
    CENTER = 0x0E
    UP_R = 0x1E
    UP_PLUS = 0x2E
    DOWN_D = 0x3E
    SIDE_S = 0x7E
    MANUAL_DOWN = 0x5E
    MANUAL_UP = 0x6E

@dataclass
class BMWState:
    """BMW 상태 데이터 클래스"""
    current_gear: str = 'D'  # 초기값을 D로 변경 (테스트용)
    manual_gear: int = 1
    lever_position: str = 'Unknown'
    park_button: str = 'Released'
    unlock_button: str = 'Released'
    last_update: Optional[str] = None

@dataclass
class PiRacerState:
    """PiRacer 상태 데이터 클래스"""
    throttle_input: float = 0.0
    steering_input: float = 0.0
    current_speed: float = 0.0
    speed_gear: int = 1

# BMW CRC 클래스들 (캐싱 최적화)
class BMW3FDCRC(crccheck.crc.Crc8Base):
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x70

class BMW197CRC(crccheck.crc.Crc8Base):
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x53

class CRCCalculator:
    """CRC 계산을 위한 캐싱 클래스"""
    def __init__(self):
        self._cache_3fd = {}
        self._cache_197 = {}
    
    def bmw_3fd_crc(self, message: bytes) -> int:
        """BMW 3FD CRC 계산 (캐싱)"""
        message_bytes = bytes(message) if not isinstance(message, bytes) else message
        if message_bytes not in self._cache_3fd:
            self._cache_3fd[message_bytes] = BMW3FDCRC.calc(message_bytes) & 0xFF
        return self._cache_3fd[message_bytes]
    
    def bmw_197_crc(self, message: bytes) -> int:
        """BMW 197 CRC 계산 (캐싱)"""
        message_bytes = bytes(message) if not isinstance(message, bytes) else message
        if message_bytes not in self._cache_197:
            self._cache_197[message_bytes] = BMW197CRC.calc(message_bytes) & 0xFF
        return self._cache_197[message_bytes]

class LogLevel(Enum):
    """로그 레벨"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

class FileLogHandler:
    """파일 로그 핸들러 클래스"""
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        
        # 로그 디렉토리 생성
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Failed to create log directory: {e}")
        
        # 세션별 로그 파일명 생성 (타임스탬프)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = os.path.join(self.log_dir, f"bmw_controller_{timestamp}.log")
        
        # 로그 파일 초기화
        try:
            with open(self.log_filename, 'w', encoding='utf-8') as f:
                f.write(f"BMW PiRacer Controller Log - Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
            print(f"📝 Log file created: {self.log_filename}")
        except Exception as e:
            print(f"❌ Failed to create log file: {e}")
            self.log_filename = None
    
    def write_log(self, message: str):
        """로그 메시지를 파일에 기록"""
        if not self.log_filename:
            return
            
        try:
            with open(self.log_filename, 'a', encoding='utf-8') as f:
                f.write(f"{message}\n")
                f.flush()  # 즉시 디스크에 기록
        except Exception as e:
            print(f"❌ Failed to write log: {e}")
    
    def cleanup_old_logs(self, max_files: int = 10):
        """오래된 로그 파일 정리 (최대 개수 유지)"""
        try:
            log_files = []
            for filename in os.listdir(self.log_dir):
                if filename.startswith("bmw_controller_") and filename.endswith(".log"):
                    filepath = os.path.join(self.log_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    log_files.append((mtime, filepath))
            
            # 시간순 정렬 (오래된 것부터)
            log_files.sort()
            
            # 최대 개수 초과시 오래된 파일 삭제
            if len(log_files) > max_files:
                files_to_delete = log_files[:-max_files]
                for _, filepath in files_to_delete:
                    os.remove(filepath)
                    print(f"🗑️ Removed old log file: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"⚠️ Failed to cleanup old logs: {e}")

class Logger:
    """커스텀 로거 클래스 (파일 로깅 지원)"""
    def __init__(self, level: LogLevel = LogLevel.INFO, enable_file_logging: bool = True):
        self.level = level
        self.handlers = []
        
        # 파일 로깅 설정
        self.file_handler = None
        if enable_file_logging:
            try:
                self.file_handler = FileLogHandler()
                self.file_handler.cleanup_old_logs()
                print(f"✅ File logging enabled: {self.file_handler.log_filename}")
            except Exception as e:
                print(f"⚠️ File logging disabled due to error: {e}")
                self.file_handler = None
    
    def add_handler(self, handler: Callable[[str], None]):
        """로그 핸들러 추가"""
        self.handlers.append(handler)
    
    def log(self, level: LogLevel, message: str):
        """로그 메시지 출력"""
        if level.value >= self.level.value:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            full_timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            
            # 콘솔용 메시지 (짧은 타임스탬프)
            console_msg = f"{timestamp} {message}"
            
            # 파일용 메시지 (긴 타임스탬프, 레벨 포함)
            level_name = level.name.ljust(7)  # 7자리로 맞춤
            file_msg = f"{full_timestamp} [{level_name}] {message}"
            
            # 콘솔 핸들러들에게 전송
            for handler in self.handlers:
                handler(console_msg)
            
            # 파일에 기록
            if self.file_handler:
                self.file_handler.write_log(file_msg)
    
    def debug(self, message: str):
        self.log(LogLevel.DEBUG, f"🔍 {message}")
    
    def info(self, message: str):
        self.log(LogLevel.INFO, f"ℹ️ {message}")
    
    def warning(self, message: str):
        self.log(LogLevel.WARNING, f"⚠️ {message}")
    
    def error(self, message: str):
        self.log(LogLevel.ERROR, f"❌ {message}")
    
    def critical(self, message: str):
        """치명적 에러 로그 (항상 기록)"""
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        critical_msg = f"{timestamp} [CRITICAL] 🚨 {message}"
        
        # 콘솔에 출력 (레벨 무시)
        print(critical_msg)
        
        # 파일에 기록
        if self.file_handler:
            self.file_handler.write_log(critical_msg)
        
        # 모든 핸들러에게 전송
        for handler in self.handlers:
            handler(critical_msg)
    
    def get_log_filename(self) -> Optional[str]:
        """현재 로그 파일명 반환"""
        return self.file_handler.log_filename if self.file_handler else None

class SpeedSensor:
    """속도센서 GPIO 제어 클래스"""
    
    def __init__(self, logger: Logger, speed_callback: Callable[[float], None]):
        self.logger = logger
        self.speed_callback = speed_callback
        self.counter = 0
        self.velocity_kmh = 0.0
        self.previous_micros = 0
        self.running = False
        self.calculation_thread = None
        
        # GPIO 설정 (폴링 방식)
        try:
            GPIO.cleanup()  # 기존 설정 정리
        except:
            pass
            
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(Constants.SPEED_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.logger.info(f"✓ Speed sensor initialized on GPIO {Constants.SPEED_SENSOR_PIN} (polling mode)")
        except Exception as e:
            self.logger.error(f"Speed sensor GPIO setup failed: {e}")
    
    def _count_pulses_polling(self):
        """폴링 방식 펄스 카운트"""
        current_state = GPIO.input(Constants.SPEED_SENSOR_PIN)
        current_micros = time.time() * 1000000  # microseconds
        
        # 이전 상태와 다르면 에지 감지
        if hasattr(self, 'last_state') and current_state != self.last_state:
            if current_micros - self.previous_micros >= Constants.PULSE_DEBOUNCE_MICROS:
                self.counter += 1
                self.previous_micros = current_micros
                
        self.last_state = current_state
    
    def _calculate_speed(self):
        """속도 계산 스레드 (폴링 방식)"""
        try:
            self.last_state = GPIO.input(Constants.SPEED_SENSOR_PIN)  # 초기 상태
        except:
            self.last_state = 1  # 기본값 설정
        
        while self.running:
            try:
                # 폴링으로 펄스 감지 (1ms 간격)
                for _ in range(int(Constants.SPEED_CALCULATION_INTERVAL * 1000)):
                    if not self.running:
                        break
                    self._count_pulses_polling()
                    time.sleep(0.001)  # 1ms 폴링
                
                # RPM 계산
                rpm = (60 * self.counter) / Constants.PULSES_PER_TURN
                
                # 바퀴 둘래 (m)
                wheel_circ_m = 3.1416 * (Constants.WHEEL_DIAMETER_MM / 1000.0)
                
                # 속도 (km/h)
                self.velocity_kmh = (rpm * wheel_circ_m * 60) / 1000.0
                
                # 속도 업데이트 콜백
                self.speed_callback(self.velocity_kmh)
                
                # 디버그 로그
                if self.counter > 0:  # 이동 중일 때만 로그
                    self.logger.debug(f"🏁 RPM: {rpm:.1f} | Speed: {self.velocity_kmh:.2f} km/h | Pulses: {self.counter}")
                
                # 카운터 리셋
                self.counter = 0
                
            except Exception as e:
                self.logger.error(f"Speed calculation error: {e}")
                time.sleep(1)
    
    def start(self):
        """속도 계산 시작"""
        if not self.running:
            self.running = True
            self.calculation_thread = threading.Thread(target=self._calculate_speed, daemon=True)
            self.calculation_thread.start()
            self.logger.info("🟢 Speed sensor started")
    
    def stop(self):
        """속도 계산 중단"""
        self.running = False
        self.logger.info("🔴 Speed sensor stopped (polling mode)")
    
    def cleanup(self):
        """정리"""
        self.stop()
        try:
            GPIO.cleanup(Constants.SPEED_SENSOR_PIN)
        except Exception as e:
            self.logger.error(f"GPIO cleanup error: {e}")

class SignalEmitter(QObject):
    """시그널 방출용 클래스"""
    gear_changed = pyqtSignal(str)
    lever_changed = pyqtSignal(str)
    button_changed = pyqtSignal(str, str)
    can_status_changed = pyqtSignal(bool)
    message_received = pyqtSignal(str)
    debug_info = pyqtSignal(str)
    stats_updated = pyqtSignal(int)
    speed_updated = pyqtSignal(float)
    piracer_status_changed = pyqtSignal(str)

class SpeedometerWidget(QWidget):
    """속도계 표시 위젯 - 최적화됨"""
    
    def __init__(self):
        super().__init__()
        self.current_speed = 0.0
        self.max_speed = Constants.MAX_SPEED
        self.setMinimumSize(*Constants.SPEEDOMETER_SIZE)
        
        # 색상 캐싱
        self.bg_color = QColor(20, 20, 20)
        self.border_color = QColor(0, 120, 215)
        self.speed_color = QColor(0, 255, 100)
        self.text_color = QColor(255, 255, 255)
        self.circle_color = QColor(100, 100, 100)
        
    def set_speed(self, speed: float):
        """속도 설정"""
        new_speed = max(0, min(speed, self.max_speed))
        if abs(self.current_speed - new_speed) > 0.1:  # 작은 변화는 무시
            self.current_speed = new_speed
            # QTimer를 사용하여 안전한 업데이트
            QTimer.singleShot(50, self.update)  # 50ms 지연으로 안전한 업데이트
        
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            if not painter.isActive():
                return
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), self.bg_color)
            
            # 테두리
            painter.setPen(QPen(self.border_color, 3))
            painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
            
            # 속도계 원
            center_x = self.width() // 2
            center_y = self.height() // 2
            radius = min(self.width(), self.height()) // 2 - 20
            
            painter.setPen(QPen(self.circle_color, 2))
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
            
            # 속도 텍스트
            painter.setPen(QPen(self.speed_color))
            font = QFont("Arial", 24, QFont.Bold)
            painter.setFont(font)
            
            speed_text = f"{self.current_speed:.1f}"
            text_rect = self.rect().adjusted(0, -20, 0, 0)
            painter.drawText(text_rect, Qt.AlignCenter, speed_text)
            
            # 단위
            painter.setPen(QPen(self.text_color))
            font = QFont("Arial", 12)
            painter.setFont(font)
            unit_rect = self.rect().adjusted(0, 25, 0, 0)
            painter.drawText(unit_rect, Qt.AlignCenter, "km/h")
            
            painter.end()
            
        except Exception as e:
            print(f"❌ Speedometer paint error: {e}")

class GearDisplayWidget(QWidget):
    """현재 기어 상태 표시 위젯 - 최적화됨"""
    
    def __init__(self):
        super().__init__()
        self.current_gear = 'Unknown'
        self.manual_gear = 1
        self.setMinimumSize(*Constants.GEAR_DISPLAY_SIZE)
        
        # 색상 매핑 캐싱
        self.gear_colors = {
            'P': QColor(255, 100, 100),    # 빨간색
            'R': QColor(255, 140, 0),      # 주황색
            'N': QColor(255, 255, 100),    # 노란색
            'D': QColor(100, 255, 100),    # 녹색
            'M': QColor(100, 150, 255),    # 파란색
            'Unknown': QColor(150, 150, 150)  # 회색
        }
        
        self.status_texts = {
            'P': "PARK",
            'R': "REVERSE", 
            'N': "NEUTRAL",
            'D': "DRIVE",
            'M': lambda gear: f"MANUAL {gear}",
            'Unknown': "UNKNOWN"
        }
        
    def set_gear(self, gear: str, manual_gear: int = 1):
        """기어 상태 업데이트"""
        if self.current_gear != gear or self.manual_gear != manual_gear:
            self.current_gear = gear
            self.manual_gear = manual_gear
            # QTimer를 사용하여 안전한 업데이트
            QTimer.singleShot(50, self.update)  # 50ms 지연으로 안전한 업데이트
        
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            if not painter.isActive():
                return
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 배경
            painter.fillRect(self.rect(), QColor(20, 20, 20))
            
            # 테두리
            painter.setPen(QPen(QColor(0, 120, 215), 3))
            painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
            
            # 기어별 색상 및 상태 텍스트
            gear_key = self.current_gear[0] if self.current_gear.startswith('M') else self.current_gear
            color = self.gear_colors.get(gear_key, self.gear_colors['Unknown'])
            
            if self.current_gear.startswith('M'):
                status_text = self.status_texts['M'](self.manual_gear)
            else:
                status_text = self.status_texts.get(self.current_gear, "UNKNOWN")
            
            # 기어 표시
            painter.setPen(QPen(color))
            font = QFont("Arial", 36, QFont.Bold)
            painter.setFont(font)
            
            gear_rect = self.rect().adjusted(0, -20, 0, 0)
            painter.drawText(gear_rect, Qt.AlignCenter, self.current_gear)
            
            # 상태 텍스트
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Arial", 10)
            painter.setFont(font)
            status_rect = self.rect().adjusted(0, 30, 0, 0)
            painter.drawText(status_rect, Qt.AlignCenter, status_text)
            
            painter.end()
            
        except Exception as e:
            print(f"❌ Gear display paint error: {e}")

class BMWLeverController:
    """BMW 레버 제어 로직을 분리한 클래스"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.lever_position_map = {
            0x0E: 'Center',
            0x1E: 'Up (R)', 
            0x2E: 'Up+ (Beyond R)',
            0x3E: 'Down (D)',
            0x7E: 'Side (S)',
            0x5E: 'Manual Down (-)',
            0x6E: 'Manual Up (+)'
        }
        
        # 토글 제어 변수들
        self.current_lever_position = 0x0E
        self.previous_lever_position = 0x0E
        self.lever_returned_to_center = True
        self.lever_returned_to_manual_center = True
        self.last_toggle_time = 0
        
    def decode_lever_message(self, msg: can.Message, bmw_state: BMWState) -> bool:
        """레버 메시지 디코딩"""
        if len(msg.data) < 4:
            return False
            
        try:
            crc = msg.data[0]
            counter = msg.data[1]
            lever_pos = msg.data[2]
            park_btn = msg.data[3]
            
            # 레버 위치 매핑
            bmw_state.lever_position = self.lever_position_map.get(
                lever_pos, f'Unknown (0x{lever_pos:02X})'
            )
            
            # 버튼 상태
            bmw_state.park_button = 'Pressed' if (park_btn & 0x01) != 0 else 'Released'
            bmw_state.unlock_button = 'Pressed' if (park_btn & 0x02) != 0 else 'Released'
            
            # 토글 처리
            self.previous_lever_position = self.current_lever_position
            self.current_lever_position = lever_pos
            self._handle_toggle_action(lever_pos, park_btn, bmw_state)
            
            bmw_state.last_update = datetime.now().strftime("%H:%M:%S")
            return True
            
        except Exception as e:
            self.logger.error(f"Lever message decode error: {e}")
            return False
    
    def _handle_toggle_action(self, lever_pos: int, park_btn: int, bmw_state: BMWState):
        """토글 방식 기어 전환 처리"""
        current_time = time.time()
        unlock_pressed = (park_btn & 0x02) != 0
        
        # Unlock 버튼 처리
        if unlock_pressed and bmw_state.current_gear == 'P' and lever_pos == 0x0E:
            bmw_state.current_gear = 'N'
            self.logger.info("🔓 Unlock: PARK → NEUTRAL")
            return
        
        # Park 버튼 처리
        if (park_btn & 0x01) != 0 and lever_pos == 0x0E:
            bmw_state.current_gear = 'P'
            self.logger.info("🅿️ Park Button → PARK")
            return
        
        # 토글 타임아웃 체크
        if current_time - self.last_toggle_time < Constants.TOGGLE_TIMEOUT:
            return
        
        # 센터 복귀 토글 처리
        if lever_pos == 0x0E and not self.lever_returned_to_center:
            self.lever_returned_to_center = True
            self._process_toggle_transition(bmw_state)
            self.last_toggle_time = current_time
        elif lever_pos != 0x0E:
            self.lever_returned_to_center = False

        # 수동 센터 복귀 토글 처리
        if lever_pos == 0x7E and not self.lever_returned_to_manual_center:
            self.lever_returned_to_manual_center = True
            self._process_toggle_manual_transition(bmw_state)
            self.last_toggle_time = current_time
        elif lever_pos != 0x7E:
            self.lever_returned_to_manual_center = False
    
    def _process_toggle_transition(self, bmw_state: BMWState):
        """토글 전환 처리"""
        transitions = {
            0x1E: self._handle_up_toggle,      # UP
            0x2E: lambda bs: self._set_gear(bs, 'P', "🎯 UP+ → PARK"),  # UP+
            0x3E: self._handle_down_toggle,    # DOWN
            0x7E: self._handle_side_toggle,    # SIDE
        }
        
        handler = transitions.get(self.previous_lever_position)
        if handler:
            handler(bmw_state)
    
    def _process_toggle_manual_transition(self, bmw_state: BMWState):
        """수동 토글 전환 처리"""
        transitions = {
            0x5E: self._handle_manual_down_toggle,  # Manual Down
            0x6E: self._handle_manual_up_toggle,    # Manual Up
            0x0E: self._handle_side_toggle,         # Center → Side
        }
        
        handler = transitions.get(self.previous_lever_position)
        if handler:
            handler(bmw_state)
    
    def _handle_up_toggle(self, bmw_state: BMWState):
        """위 토글 처리"""
        gear_transitions = {
            'N': ('R', "🎯 N → REVERSE"),
            'D': ('N', "🎯 D → NEUTRAL"),
        }
        
        new_gear, msg = gear_transitions.get(bmw_state.current_gear, ('N', "🎯 UP → NEUTRAL"))
        self._set_gear(bmw_state, new_gear, msg)
    
    def _handle_down_toggle(self, bmw_state: BMWState):
        """아래 토글 처리"""
        gear_transitions = {
            'N': ('D', "🎯 N → DRIVE"),
            'R': ('N', "🎯 R → NEUTRAL"),
        }
        
        new_gear, msg = gear_transitions.get(bmw_state.current_gear, ('D', "🎯 DOWN → DRIVE"))
        self._set_gear(bmw_state, new_gear, msg)
    
    def _handle_side_toggle(self, bmw_state: BMWState):
        """사이드 토글 처리"""
        if bmw_state.current_gear == 'D':
            bmw_state.manual_gear = 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🎯 D → MANUAL M{bmw_state.manual_gear}")
        elif bmw_state.current_gear.startswith('M'):
            self._set_gear(bmw_state, 'D', "🎯 Manual → DRIVE")
        else:
            self._set_gear(bmw_state, 'D', "🎯 SIDE → DRIVE")
    
    def _handle_manual_up_toggle(self, bmw_state: BMWState):
        """수동 업 토글 처리"""
        if bmw_state.current_gear.startswith('M') and bmw_state.manual_gear < Constants.MANUAL_GEARS:
            bmw_state.manual_gear += 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🔼 Manual → M{bmw_state.manual_gear}")
    
    def _handle_manual_down_toggle(self, bmw_state: BMWState):
        """수동 다운 토글 처리"""
        if bmw_state.current_gear.startswith('M') and bmw_state.manual_gear > 1:
            bmw_state.manual_gear -= 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🔽 Manual → M{bmw_state.manual_gear}")
    
    def _set_gear(self, bmw_state: BMWState, gear: str, message: str):
        """기어 설정 헬퍼 메서드"""
        bmw_state.current_gear = gear
        self.logger.info(message)

class CANController:
    """CAN 버스 제어를 담당하는 클래스"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.bmw_bus: Optional[can.interface.Bus] = None
        self.running = True
        self.crc_calc = CRCCalculator()
        self.gws_counter = 0x01
        
    def setup_can_interfaces(self) -> bool:
        """CAN 인터페이스 설정"""
        bmw_ok = self._setup_single_can(Constants.BMW_CAN_CHANNEL, "BMW")
        return bmw_ok
    
    def _setup_single_can(self, channel: str, name: str) -> bool:
        """단일 CAN 인터페이스 설정"""
        try:
            bus = can.interface.Bus(channel=channel, interface='socketcan')
            self.bmw_bus = bus
            self.logger.info(f"✓ {name} CAN connected ({channel})")
            return True
        except Exception as e:
            self.logger.warning(f"⚠ {name} CAN not available: {e}")
            return False
    
    def send_gear_led(self, gear: str, flash: bool = False):
        """기어 LED 전송 (최적화됨)"""
        if not self.bmw_bus:
            return
        
        gear_led_codes = {
            'P': 0x20, 'R': 0x40, 'N': 0x60, 'D': 0x80, 'S': 0x81,
        }
        
        # LED 코드 결정
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
        """CAN 버스 종료"""
        self.running = False
        if self.bmw_bus:
            self.bmw_bus.shutdown()

class BMWPiRacerIntegratedControl(QMainWindow):
    """BMW PiRacer 통합 제어 시스템 GUI - 최적화됨"""
    
    def __init__(self):
        super().__init__()
        self._init_system()
        self._init_ui()
        self._setup_connections()
        self._start_control_loops()
        
    def _init_system(self):
        """시스템 초기화"""
        # 로거 설정 (파일 로깅 활성화)
        self.logger = Logger(LogLevel.INFO, enable_file_logging=True)
        
        # 로그 파일 정보 출력
        log_filename = self.logger.get_log_filename()
        if log_filename:
            print(f"📝 Session log file: {log_filename}")
        else:
            print("⚠️ File logging disabled")
        
        # 시그널 초기화
        self.signals = SignalEmitter()
        
        # 상태 객체들
        self.bmw_state = BMWState()
        self.piracer_state = PiRacerState()
        
        # 컨트롤러들
        self.lever_controller = BMWLeverController(self.logger)
        self.can_controller = CANController(self.logger)
        self.speed_sensor = SpeedSensor(self.logger, self._on_speed_updated)
        
        # 통계
        self.message_count = 0
        self.running = True
        
        # PiRacer 초기화
        self.piracer = None
        self.gamepad = None
        
        self.logger.info("🚀 Starting PiRacer and Gamepad initialization...")
        self.logger.info(f"📊 PIRACER_AVAILABLE status: {PIRACER_AVAILABLE}")
        self.logger.info(f"📊 GAMEPAD_CLASS available: {GAMEPAD_CLASS is not None}")
        
        if PIRACER_AVAILABLE:
            self.logger.info("📦 PiRacer library is available, proceeding with initialization...")
            
            # PiRacer 초기화
            try:
                self.logger.info("🏎️ Initializing PiRacer hardware...")
                self.piracer = PiRacerStandard()
                self.logger.info("✅ PiRacer hardware initialized successfully")
                
            except Exception as e:
                self.logger.error(f"❌ PiRacer hardware initialization failed: {e}")
                self.logger.error(f"🔍 Error type: {type(e).__name__}")
                self.piracer = None
                self.signals.piracer_status_changed.emit(f"PiRacer Error: {e}")
            
            # 게임패드 초기화 (PiRacer와 독립적으로)
            self.logger.info("🎮 Starting gamepad initialization (independent of PiRacer)...")
            self._initialize_gamepad_with_debug()
                    
        else:
            self.logger.warning("⚠️ PiRacer library not available - running in simulation mode")
            self.logger.info("📊 Checking gamepad availability without PiRacer...")
            
            # PiRacer 없어도 게임패드 테스트
            self._initialize_gamepad_with_debug()
            self.signals.piracer_status_changed.emit("PiRacer Not Available")
        
        # 로거 핸들러 추가
        self.logger.add_handler(self.signals.message_received.emit)
        
        # 시그널 연결
        self._connect_signals()
        
    def _connect_signals(self):
        """시그널 연결"""
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
        """UI 초기화"""
        self.setWindowTitle("BMW PiRacer Integrated Control System - GPIO16 Speed Optimized")
        self.setGeometry(0, 0, Constants.WINDOW_WIDTH, Constants.WINDOW_HEIGHT)
        
        # 화면 크기 설정 (1280x400 최적화)
        self.setGeometry(0, 0, Constants.WINDOW_WIDTH, Constants.WINDOW_HEIGHT)
        self.showFullScreen()
        self.setStyleSheet(self._get_stylesheet())
        
        # ESC 키로 나가기 (이미 import된 것 사용)
        try:
            from PyQt5.QtWidgets import QShortcut
            from PyQt5.QtGui import QKeySequence
            self.exit_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
            self.exit_shortcut.activated.connect(self.close)
        except:
            pass  # PyQt5 import 실패시 무시
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        
        # UI 구성 요소들 (1280x400 최적화)
        main_layout.addLayout(self._create_header())  # 헤더: 약 50px
        main_layout.addLayout(self._create_dashboard(), 3)  # 대시보드: 약 200px
        main_layout.addLayout(self._create_status_panel(), 2)  # 상태: 약 100px
        main_layout.addWidget(self._create_log_panel(), 1)  # 로그: 약 50px
        
        central_widget.setLayout(main_layout)
        
    def _get_stylesheet(self) -> str:
        """스타일시트 반환"""
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
        
    def _create_header(self) -> QHBoxLayout:
        """헤더 생성"""
        header_layout = QHBoxLayout()
        
        # BMW 로고 (작게 조정)
        logo_label = QLabel("🚗 BMW")
        logo_label.setFont(QFont("Arial", 16, QFont.Bold))
        logo_label.setStyleSheet(f"color: {Constants.BMW_BLUE};")
        
        # 타이틀 (작게 조정)
        title_label = QLabel("PiRacer Control System - GPIO16")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        
        # 나가기 버튼
        self.exit_button = QPushButton("Exit")
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
        
        # 시간
        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.time_label.setFont(QFont("Arial", 10))
        self.time_label.setAlignment(Qt.AlignRight)
        
        # 시간 업데이트 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000 // Constants.TIME_UPDATE_RATE)
        
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(self.time_label)
        header_layout.addWidget(self.exit_button)
        
        return header_layout
        
    def _create_dashboard(self) -> QHBoxLayout:
        """대시보드 생성"""
        dashboard_layout = QHBoxLayout()
        
        dashboard_layout.addWidget(self._create_gear_panel(), 1)
        dashboard_layout.addWidget(self._create_speed_panel(), 1)
        dashboard_layout.addWidget(self._create_piracer_panel(), 1)
        
        return dashboard_layout
        
    def _create_gear_panel(self) -> QGroupBox:
        """기어 표시 패널 생성"""
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
        
    def _create_speed_panel(self) -> QGroupBox:
        """속도계 패널 생성"""
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
        
    def _create_piracer_panel(self) -> QGroupBox:
        """PiRacer 제어 패널 생성"""
        group = QGroupBox("PiRacer Control")
        layout = QVBoxLayout()
        
        # 스로틀 진행바
        throttle_label = QLabel("Throttle:")
        self.throttle_bar = QProgressBar()
        self.throttle_bar.setRange(-100, 100)
        self.throttle_bar.setValue(0)
        
        # 스티어링 진행바
        steering_label = QLabel("Steering:")
        self.steering_bar = QProgressBar()
        self.steering_bar.setRange(-100, 100)
        self.steering_bar.setValue(0)
        
        # PiRacer 상태
        self.piracer_status_label = QLabel("Status: Unknown")
        self.piracer_status_label.setFont(QFont("Arial", 10))
        
        # 게임패드 재연결 버튼
        self.reconnect_gamepad_btn = QPushButton("Reconnect Gamepad")
        self.reconnect_gamepad_btn.clicked.connect(self._manual_gamepad_reconnect)
        self.reconnect_gamepad_btn.setFont(QFont("Arial", 9))
        
        layout.addWidget(throttle_label)
        layout.addWidget(self.throttle_bar)
        layout.addWidget(steering_label)
        layout.addWidget(self.steering_bar)
        layout.addWidget(self.piracer_status_label)
        layout.addWidget(self.reconnect_gamepad_btn)
        
        group.setLayout(layout)
        return group
        
    def _create_status_panel(self) -> QHBoxLayout:
        """상태 패널 생성"""
        status_layout = QHBoxLayout()
        status_layout.addWidget(self._create_bmw_status_panel(), 1)
        status_layout.addWidget(self._create_system_status_panel(), 1)
        return status_layout
        
    def _create_bmw_status_panel(self) -> QGroupBox:
        """BMW 상태 패널 생성"""
        group = QGroupBox("BMW Lever Status")
        layout = QVBoxLayout()
        
        # 레버 위치
        self.lever_pos_label = QLabel("Lever Position:")
        self.lever_pos_value = QLabel("Unknown")
        self.lever_pos_value.setFont(QFont("Arial", 12, QFont.Bold))
        self.lever_pos_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
        
        # 버튼 상태
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
        
    def _create_system_status_panel(self) -> QGroupBox:
        """시스템 상태 패널 생성"""
        group = QGroupBox("System Status")
        layout = QVBoxLayout()
        
        # CAN 상태
        self.can_status_label = QLabel("BMW CAN:")
        self.can_status_value = QLabel("Disconnected")
        self.can_status_value.setStyleSheet(f"color: {Constants.ERROR_RED};")
        
        self.speed_sensor_label = QLabel("Speed Sensor:")
        self.speed_sensor_value = QLabel("GPIO Ready")
        self.speed_sensor_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
        
        # 메시지 카운터
        self.msg_count_label = QLabel("Messages:")
        self.msg_count_value = QLabel("0")
        
        # 제어 버튼
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
        
    def _create_log_panel(self) -> QGroupBox:
        """로그 패널 생성"""
        group = QGroupBox("Real-time System Logs")
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(40)  # 로그 영역 축소
        self.log_text.setFont(QFont("Consolas", Constants.LOG_FONT_SIZE))
        
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group
        
    def _setup_connections(self):
        """연결 설정"""
        bmw_ok = self.can_controller.setup_can_interfaces()
        self.signals.can_status_changed.emit(bmw_ok)
        
        if bmw_ok:
            self._start_bmw_monitoring()
            self._start_led_control()
        
        # 속도센서 시작
        self.speed_sensor.start()
            
    def _start_control_loops(self):
        """제어 루프 시작"""
        self._start_gamepad_control()
        
    def _start_bmw_monitoring(self):
        """BMW CAN 모니터링 시작"""
        def bmw_monitor_loop():
            while self.running and self.can_controller.bmw_bus:
                try:
                    msg = self.can_controller.bmw_bus.recv(timeout=Constants.BMW_CAN_TIMEOUT)
                    if msg:
                        self._bmw_message_handler(msg)
                except Exception as e:
                    if self.running:
                        self.logger.error(f"BMW CAN Error: {e}")
                        time.sleep(0.1)
        
        bmw_thread = threading.Thread(target=bmw_monitor_loop, daemon=True)
        bmw_thread.start()
    
    def _on_speed_updated(self, speed_kmh: float):
        """속도 업데이트 콜백"""
        self.piracer_state.current_speed = speed_kmh
        self.signals.speed_updated.emit(speed_kmh)
    
    def _start_gamepad_control(self):
        """게임패드 제어 시작"""
        self.logger.info("🚀 Starting gamepad control system...")
        
        # 라이브러리 상태 체크
        self.logger.info(f"📊 Checking library availability: PIRACER_AVAILABLE={PIRACER_AVAILABLE}, GAMEPAD_CLASS={GAMEPAD_CLASS is not None}")
        
        if not PIRACER_AVAILABLE:
            self.logger.warning("⚠️ PiRacer library not available - trying gamepad-only mode")
            # PiRacer 없어도 게임패드는 시도해볼 수 있음
            if GAMEPAD_CLASS:
                self.logger.info("🎮 Gamepad class available - attempting gamepad-only mode")
            else:
                self.logger.error("❌ Neither PiRacer nor Gamepad class available - control disabled")
                return
        
        if not GAMEPAD_CLASS:
            self.logger.error("❌ ShanWanGamepad class not available - gamepad control disabled")
            return
        
        # PiRacer 상태 체크
        if not self.piracer:
            self.logger.warning("⚠️ PiRacer hardware not available - gamepad will work in simulation mode")
            self.logger.info("📊 Gamepad inputs will be logged but not applied to hardware")
        else:
            self.logger.info("✅ PiRacer hardware available - full gamepad control enabled")
            
        # 게임패드 상태 체크 및 재연결 시도
        if not self.gamepad:
            self.logger.warning("⚠️ Gamepad not available - trying to reconnect...")
            reconnect_success = self._try_gamepad_reconnect()
            if not reconnect_success:
                self.logger.error("❌ Gamepad reconnection failed - starting control loop anyway for monitoring")
            else:
                self.logger.info("✅ Gamepad reconnection successful - control loop ready")
        else:
            self.logger.info("✅ Gamepad already available - starting control loop")
        
        def gamepad_loop():
            last_l2 = last_r2 = False
            update_interval = 1.0 / Constants.GAMEPAD_UPDATE_RATE
            gamepad_error_count = 0
            max_errors = 5
            loop_count = 0
            successful_reads = 0
            
            self.logger.info(f"🎮 Gamepad control loop started (update rate: {Constants.GAMEPAD_UPDATE_RATE}Hz)")
            self.logger.info(f"📊 Loop interval: {update_interval:.3f}s, Max errors: {max_errors}")
            
            while self.running:
                loop_count += 1
                
                # 매 100회마다 상태 로그
                if loop_count % 100 == 0:
                    self.logger.info(f"🔄 Gamepad loop #{loop_count}, successful reads: {successful_reads}, errors: {gamepad_error_count}")
                
                try:
                    # 게임패드 연결 체크
                    if not self.gamepad:
                        self.logger.warning(f"🎮 Gamepad disconnected at loop #{loop_count} - attempting reconnect...")
                        reconnect_success = self._try_gamepad_reconnect()
                        if not reconnect_success:
                            self.logger.debug(f"🔄 Reconnection failed, waiting 1s before retry (loop #{loop_count})")
                            time.sleep(1)
                            continue
                        else:
                            self.logger.info(f"✅ Reconnection successful at loop #{loop_count}")
                    
                    # 게임패드 데이터 읽기
                    self.logger.debug(f"📖 Reading gamepad data (loop #{loop_count})...")
                    gamepad_input = self.gamepad.read_data()
                    successful_reads += 1
                    gamepad_error_count = 0  # 성공시 에러 카운트 리셋
                    
                    # 매 50회마다 입력 데이터 로깅
                    if loop_count % 50 == 0:
                        self.logger.info(f"🎮 Input data: throttle={gamepad_input.analog_stick_right.y:.3f}, steering={gamepad_input.analog_stick_left.x:.3f}")
                        self.logger.info(f"🎮 Buttons: A={gamepad_input.button_a}, B={gamepad_input.button_b}, X={gamepad_input.button_x}, Y={gamepad_input.button_y}")
                        self.logger.info(f"🎮 Triggers: L2={gamepad_input.button_l2}, R2={gamepad_input.button_r2}")
                    
                    # 속도 기어 조절 (L2/R2) - 상세 로깅
                    if gamepad_input.button_l2 and not last_l2:
                        old_gear = self.piracer_state.speed_gear
                        self.piracer_state.speed_gear = max(1, self.piracer_state.speed_gear - 1)
                        self.logger.info(f"🔽 Speed Gear DOWN: {old_gear} → {self.piracer_state.speed_gear} (L2 pressed)")
                    if gamepad_input.button_r2 and not last_r2:
                        old_gear = self.piracer_state.speed_gear
                        self.piracer_state.speed_gear = min(Constants.SPEED_GEARS, self.piracer_state.speed_gear + 1)
                        self.logger.info(f"🔼 Speed Gear UP: {old_gear} → {self.piracer_state.speed_gear} (R2 pressed)")
                    
                    # 트리거 상태 업데이트
                    if gamepad_input.button_l2 != last_l2:
                        self.logger.debug(f"🎮 L2 trigger: {last_l2} → {gamepad_input.button_l2}")
                    if gamepad_input.button_r2 != last_r2:
                        self.logger.debug(f"🎮 R2 trigger: {last_r2} → {gamepad_input.button_r2}")
                        
                    last_l2 = gamepad_input.button_l2
                    last_r2 = gamepad_input.button_r2
                    
                    # 조이스틱 입력 with bounds checking
                    old_throttle = self.piracer_state.throttle_input
                    old_steering = self.piracer_state.steering_input
                    
                    self.piracer_state.throttle_input = -gamepad_input.analog_stick_right.y
                    self.piracer_state.steering_input = -gamepad_input.analog_stick_left.x
                    
                    # 큰 변화가 있을 때만 로깅
                    if abs(self.piracer_state.throttle_input - old_throttle) > 0.1:
                        self.logger.debug(f"🕹️ Throttle: {old_throttle:.3f} → {self.piracer_state.throttle_input:.3f}")
                    if abs(self.piracer_state.steering_input - old_steering) > 0.1:
                        self.logger.debug(f"🕹️ Steering: {old_steering:.3f} → {self.piracer_state.steering_input:.3f}")
                    
                    # 게임패드 버튼으로 기어 제어 (상세 로깅)
                    gear_changed = False
                    old_gear = self.bmw_state.current_gear
                    
                    if gamepad_input.button_b:  # B버튼 = Drive
                        if self.bmw_state.current_gear != 'D':
                            self.bmw_state.current_gear = 'D'
                            self.logger.info(f"🎮 Button B pressed: Gear {old_gear} → DRIVE")
                            gear_changed = True
                    elif gamepad_input.button_a:  # A버튼 = Neutral
                        if self.bmw_state.current_gear != 'N':
                            self.bmw_state.current_gear = 'N'
                            self.logger.info(f"🎮 Button A pressed: Gear {old_gear} → NEUTRAL")
                            gear_changed = True
                    elif gamepad_input.button_x:  # X버튼 = Reverse
                        if self.bmw_state.current_gear != 'R':
                            self.bmw_state.current_gear = 'R'
                            self.logger.info(f"🎮 Button X pressed: Gear {old_gear} → REVERSE")
                            gear_changed = True
                    elif gamepad_input.button_y:  # Y버튼 = Park
                        if self.bmw_state.current_gear != 'P':
                            self.bmw_state.current_gear = 'P'
                            self.logger.info(f"🎮 Button Y pressed: Gear {old_gear} → PARK")
                            gear_changed = True
                    
                    # 기어에 따른 스로틀 제어
                    throttle = self._calculate_throttle()
                    
                    # PiRacer 제어 (하드웨어 사용 가능할 때만)
                    if self.piracer:
                        try:
                            self.logger.debug(f"🏎️ Applying to PiRacer: throttle={throttle:.3f}, steering={self.piracer_state.steering_input:.3f}")
                            self.piracer.set_throttle_percent(throttle)
                            self.piracer.set_steering_percent(self.piracer_state.steering_input)
                        except Exception as piracer_error:
                            self.logger.error(f"❌ PiRacer control error: {piracer_error}")
                    else:
                        # 시뮬레이션 모드 로깅
                        if loop_count % 100 == 0:  # 100번마다 로깅
                            self.logger.info(f"🖥️ SIMULATION: throttle={throttle:.3f}, steering={self.piracer_state.steering_input:.3f}, gear={self.bmw_state.current_gear}")
                    
                    # 기어 상태 UI 업데이트 (변경시에만)
                    if gear_changed:
                        self.logger.debug(f"🔄 Updating UI for gear change: {self.bmw_state.current_gear}")
                        self.signals.gear_changed.emit(self.bmw_state.current_gear)
                    
                    # UI 업데이트
                    try:
                        self.throttle_bar.setValue(int(throttle * 100))
                        self.steering_bar.setValue(int(self.piracer_state.steering_input * 100))
                    except Exception as ui_error:
                        self.logger.error(f"❌ UI update error: {ui_error}")
                    
                    time.sleep(update_interval)
                    
                except Exception as e:
                    gamepad_error_count += 1
                    self.logger.error(f"🎮 Gamepad Error #{gamepad_error_count} at loop #{loop_count}: {e}")
                    self.logger.error(f"🔍 Error type: {type(e).__name__}")
                    
                    # 상세한 에러 정보
                    if gamepad_error_count <= 3:  # 처음 3번 에러만 상세 로깅
                        import traceback
                        self.logger.error(f"📋 Error traceback:\n{traceback.format_exc()}")
                    
                    if gamepad_error_count >= max_errors:
                        self.logger.critical(f"🎮 CRITICAL: Too many gamepad errors ({gamepad_error_count}), disconnecting and trying reconnect...")
                        self.logger.critical(f"📊 Success rate before disconnect: {successful_reads}/{loop_count} ({100*successful_reads/loop_count:.1f}%)")
                        self.gamepad = None
                        gamepad_error_count = 0
                        # 재연결 시도 전 잠시 대기
                        self.logger.info("⏳ Waiting 2 seconds before reconnection attempt...")
                        time.sleep(2)
                    else:
                        time.sleep(1)
        
        gamepad_thread = threading.Thread(target=gamepad_loop, daemon=True)
        gamepad_thread.start()
    
    def _initialize_gamepad_with_debug(self):
        """상세한 디버깅을 포함한 게임패드 초기화"""
        self.logger.info("🔍 Starting detailed gamepad initialization...")
        
        # USB 디바이스 검사
        try:
            import subprocess
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            self.logger.info(f"📱 USB devices detected:\n{result.stdout}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not check USB devices: {e}")
        
        # 게임패드 디바이스 파일 검사
        import os
        js_devices = []
        for i in range(10):  # /dev/input/js0 ~ js9 검사
            js_path = f"/dev/input/js{i}"
            if os.path.exists(js_path):
                js_devices.append(js_path)
        
        if js_devices:
            self.logger.info(f"🎮 Joystick devices found: {js_devices}")
        else:
            self.logger.warning("⚠️ No joystick devices found in /dev/input/")
        
        # 이벤트 디바이스 검사
        event_devices = []
        for i in range(20):  # /dev/input/event0 ~ event19 검사
            event_path = f"/dev/input/event{i}"
            if os.path.exists(event_path):
                event_devices.append(event_path)
        
        if event_devices:
            self.logger.info(f"📡 Input event devices found: {event_devices}")
        else:
            self.logger.warning("⚠️ No input event devices found")
        
        # ShanWanGamepad 초기화 시도
        try:
            if not GAMEPAD_CLASS:
                raise ImportError("ShanWanGamepad class not available - PiRacer library not imported")
                
            self.logger.info("🎮 Attempting ShanWanGamepad initialization...")
            self.gamepad = GAMEPAD_CLASS()
            self.logger.info("✅ ShanWanGamepad initialized successfully!")
            
            # 게임패드 테스트 읽기
            try:
                self.logger.info("🧪 Testing gamepad input reading...")
                test_data = self.gamepad.read_data()
                self.logger.info(f"📊 Gamepad test data: {test_data}")
                self.logger.info("✅ Gamepad input reading test successful")
                self.signals.piracer_status_changed.emit("Gamepad Connected & Tested")
            except Exception as read_error:
                self.logger.error(f"❌ Gamepad read test failed: {read_error}")
                self.logger.error(f"🔍 Read error type: {type(read_error).__name__}")
                self.signals.piracer_status_changed.emit(f"Gamepad Connected, Read Error: {read_error}")
                
        except Exception as e:
            self.logger.critical(f"❌ CRITICAL: ShanWanGamepad initialization failed: {e}")
            self.logger.error(f"🔍 Error type: {type(e).__name__}")
            self.logger.error(f"🔍 Error args: {e.args}")
            
            # 상세한 예외 정보
            import traceback
            self.logger.critical(f"📋 Full initialization traceback:\n{traceback.format_exc()}")
            
            self.gamepad = None
            self.signals.piracer_status_changed.emit(f"Gamepad Error: {e}")
    
    def _try_gamepad_reconnect(self):
        """게임패드 재연결 시도"""
        self.logger.info("🔄 Starting gamepad reconnection attempt...")
        
        if not PIRACER_AVAILABLE:
            self.logger.warning("⚠️ PiRacer library not available for reconnection")
            # PiRacer 없어도 게임패드는 시도
        
        try:
            self.logger.info("🎮 Attempting gamepad reconnection...")
            
            # 연결 가능성 검사
            if not PIRACER_AVAILABLE or not GAMEPAD_CLASS:
                raise ImportError("PiRacer library or ShanWanGamepad class not available")
            
            # 기존 게임패드 정리
            if self.gamepad:
                self.logger.info("🧹 Cleaning up existing gamepad connection...")
                self.gamepad = None
            
            # 새로운 연결 시도
            self.gamepad = GAMEPAD_CLASS()
            self.logger.info("✅ Gamepad reconnected successfully")
            
            # 재연결 테스트
            try:
                test_data = self.gamepad.read_data()
                self.logger.info(f"🧪 Reconnection test successful: {test_data}")
                self.signals.piracer_status_changed.emit("Gamepad Reconnected & Tested")
                return True
            except Exception as test_error:
                self.logger.error(f"❌ Reconnection test failed: {test_error}")
                self.signals.piracer_status_changed.emit(f"Reconnected, Test Failed: {test_error}")
                return False
                
        except Exception as e:
            self.logger.critical(f"❌ CRITICAL: Gamepad reconnection failed: {e}")
            self.logger.error(f"🔍 Reconnection error type: {type(e).__name__}")
            import traceback
            self.logger.critical(f"📋 Reconnection traceback:\n{traceback.format_exc()}")
            
            self.gamepad = None
            self.signals.piracer_status_changed.emit(f"Reconnection Failed: {e}")
            return False
    
    def _manual_gamepad_reconnect(self):
        """수동 게임패드 재연결"""
        self.logger.info("🔄 Manual gamepad reconnection requested...")
        if self._try_gamepad_reconnect():
            self.logger.info("✅ Manual gamepad reconnection successful")
        else:
            self.logger.error("❌ Manual gamepad reconnection failed")
    
    def _calculate_throttle(self) -> float:
        """스로틀 계산"""
        speed_limit = self.piracer_state.speed_gear * 0.25
        
        if self.bmw_state.current_gear == 'D':
            throttle = min(0.0, self.piracer_state.throttle_input)  # 전진만
        elif self.bmw_state.current_gear == 'R':
            throttle = max(0.0, self.piracer_state.throttle_input)  # 후진만
        else:
            throttle = 0.0  # P, N에서는 정지
        
        return throttle * speed_limit
    
    def _start_led_control(self):
        """LED 제어 시작"""
        def led_control_loop():
            update_interval = 1.0 / Constants.LED_UPDATE_RATE
            
            while self.running and self.can_controller.bmw_bus:
                if self.bmw_state.current_gear != 'Unknown':
                    self.can_controller.send_gear_led(self.bmw_state.current_gear, flash=False)
                time.sleep(update_interval)
        
        if self.can_controller.bmw_bus:
            led_thread = threading.Thread(target=led_control_loop, daemon=True)
            led_thread.start()
    
    def _bmw_message_handler(self, msg: can.Message):
        """BMW CAN 메시지 핸들러"""
        self.message_count += 1
        self.signals.stats_updated.emit(self.message_count)
        
        if msg.arbitration_id == Constants.LEVER_MESSAGE_ID:
            # BMW 기어 레버 메시지
            if self.lever_controller.decode_lever_message(msg, self.bmw_state):
                # UI 업데이트 시그널 방출
                self.signals.lever_changed.emit(self.bmw_state.lever_position)
                self.signals.button_changed.emit(self.bmw_state.park_button, self.bmw_state.unlock_button)
                self.signals.gear_changed.emit(self.bmw_state.current_gear)
                
                # 기어 변경시 LED 업데이트
                if self.bmw_state.current_gear != 'Unknown':
                    self.can_controller.send_gear_led(self.bmw_state.current_gear, flash=False)
    
    # UI 업데이트 메서드들
    def _update_time(self):
        """시간 업데이트"""
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
    
    def update_gear_display(self, gear: str):
        """기어 표시 업데이트"""
        self.gear_widget.set_gear(gear, self.bmw_state.manual_gear)
        if self.bmw_state.last_update:
            self.last_update_label.setText(f"Last Update: {self.bmw_state.last_update}")
    
    def update_lever_display(self, lever_pos: str):
        """레버 위치 업데이트"""
        self.lever_pos_value.setText(lever_pos)
    
    def update_button_display(self, park_btn: str, unlock_btn: str):
        """버튼 상태 업데이트"""
        self.park_btn_value.setText(park_btn)
        self.unlock_btn_value.setText(unlock_btn)
        
        park_color = "#ff4444" if park_btn == "Pressed" else "#44ff44"
        unlock_color = "#ff4444" if unlock_btn == "Pressed" else "#44ff44"
        
        self.park_btn_value.setStyleSheet(f"color: {park_color};")
        self.unlock_btn_value.setStyleSheet(f"color: {unlock_color};")
    
    def update_can_status(self, connected: bool):
        """CAN 상태 업데이트"""
        if connected:
            self.can_status_value.setText("Connected")
            self.can_status_value.setStyleSheet(f"color: {Constants.SUCCESS_GREEN};")
        else:
            self.can_status_value.setText("Disconnected")
            self.can_status_value.setStyleSheet(f"color: {Constants.ERROR_RED};")
    
    def update_speed_display(self, speed: float):
        """속도 표시 업데이트"""
        self.speedometer_widget.set_speed(speed)
        self.speed_gear_label.setText(f"Speed Gear: {self.piracer_state.speed_gear}")
    
    def update_piracer_status(self, status: str):
        """PiRacer 상태 업데이트"""
        self.piracer_status_label.setText(f"Status: {status}")
    
    def update_stats(self, count: int):
        """통계 업데이트"""
        self.msg_count_value.setText(str(count))
    
    def add_log_message(self, message: str):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_text.append(f"{timestamp} {message}")
        
        # 로그가 너무 많아지면 상단 제거
        if self.log_text.document().blockCount() > Constants.MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def add_debug_info(self, debug_msg: str):
        """디버그 정보 추가"""
        self.add_log_message(debug_msg)
    
    def _clear_logs(self):
        """로그 지우기"""
        self.log_text.clear()
        self.logger.info("🧹 Logs cleared")
    
    def _toggle_can_connection(self):
        """CAN 연결 토글"""
        self._clear_logs()
        self.logger.info("🔄 Reconnecting CAN interfaces...")
        self._setup_connections()
    
    def closeEvent(self, event):
        """프로그램 종료 시"""
        self.logger.info("🛑 BMW PiRacer Controller shutting down...")
        self.logger.critical("🔴 SESSION END - Application closed by user")
        
        self.running = False
        self.can_controller.shutdown()
        self.speed_sensor.cleanup()
        
        # 로그 파일 위치 안내
        log_filename = self.logger.get_log_filename()
        if log_filename:
            print(f"📝 Complete log saved to: {log_filename}")
        
        event.accept()

def setup_can_interfaces():
    """CAN 인터페이스 설정 (BMW CAN만)"""
    print("🔧 Setting up BMW CAN interface...")
    
    # BMW CAN (can0) 설정
    result_down = os.system(f"sudo ip link set {Constants.BMW_CAN_CHANNEL} down 2>/dev/null")
    result_up = os.system(f"sudo ip link set {Constants.BMW_CAN_CHANNEL} up type can bitrate {Constants.CAN_BITRATE} 2>/dev/null")
    
    if result_up == 0:
        print(f"✓ BMW CAN interface ({Constants.BMW_CAN_CHANNEL}) configured successfully")
    else:
        print(f"⚠ Failed to configure BMW CAN interface ({Constants.BMW_CAN_CHANNEL})")

def main():
    """메인 함수"""
    # 실행 시작 로깅
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"🚀 BMW PiRacer Controller starting at {start_time}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"📝 Logs will be saved to: logs/bmw_controller_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    # DISPLAY 환경변수 자동 설정
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
        print("🖥️ DISPLAY 환경변수를 자동으로 설정했습니다: :0")
    
    # 시작 메시지
    features = [
        "- BMW Gear Lever Control (P/R/N/D/M1-M8)",
        "- Gamepad Throttle/Steering Control", 
        "- Real-time Speed Display via GPIO16",
        "- BMW CAN Bus + GPIO16 Speed Sensor",
        "- Optimized Performance & Code Quality"
    ]
    
    print("🚀 BMW PiRacer Integrated Control System Started - GPIO Speed Optimized")
    print("Features:")
    for feature in features:
        print(feature)
    
    # 디스플레이 체크 (자동 설정 후)
    display_available = os.environ.get('DISPLAY') is not None
    
    if PYQT5_AVAILABLE and display_available:
        features.append("- Integrated PyQt5 Dashboard")
        print("🎨 Launching PyQt5 GUI...")
        try:
            # QApplication 안전 초기화
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            # 플랫폼 확인
            print(f"🔍 Qt platform: {app.platformName()}")
            
            # CAN 인터페이스 자동 설정
            setup_can_interfaces()
            
            # 메인 윈도우 생성
            print("🏗️ Creating main window...")
            window = BMWPiRacerIntegratedControl()
            
            # 안전한 윈도우 표시
            print("🌟 Showing GUI window...")
            window.show()
            
            # Qt 이벤트 처리 대기
            app.processEvents()
            
            print("✅ GUI launched successfully!")
            
            # 안전한 이벤트 루프
            exit_code = app.exec_()
            sys.exit(exit_code)
        except Exception as e:
            print(f"❌ GUI launch failed: {e}")
            print(f"🔍 Error type: {type(e).__name__}")
            import traceback
            print(f"📋 GUI Error traceback:\n{traceback.format_exc()}")
            print("💡 Running in headless mode instead...")
    elif PYQT5_AVAILABLE and not display_available:
        print("⚠️ PyQt5 available but no display detected (DISPLAY environment variable not set)")
        print("💡 To run with GUI:")
        print("   - Connect a monitor and run: DISPLAY=:0 python3 bmw_piracer_integrated_control_optimized.py")
        print("   - Or use VNC/X11 forwarding")
        print("💡 Running in headless mode...")
    else:
        print("⚠️ Running in headless mode without GUI")
        print("⚠️ Install PyQt5 to enable the dashboard: pip install PyQt5")
        
        # CAN 인터페이스 자동 설정
        setup_can_interfaces()
        
        # 헤드리스 모드로 실행
        try:
            # 간단한 CAN 모니터링만 실행
            import can
            bus = can.interface.Bus(channel='can0', interface='socketcan')
            print("🚀 Headless mode: Monitoring CAN messages... (Press Ctrl+C to exit)")
            
            while True:
                msg = bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == 0x197:  # BMW lever message
                    print(f"📨 BMW Lever Message: {msg}")
                    
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        except Exception as e:
            print(f"❌ Error in headless mode: {e}")
            print(f"🔍 Error type: {type(e).__name__}")
            import traceback
            print(f"📋 Headless Error traceback:\n{traceback.format_exc()}")
            print("💡 Make sure CAN interface is properly configured")
        
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user (Ctrl+C)")
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🔴 Session ended at {end_time}")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in main(): {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        import traceback
        print(f"📋 Critical traceback:\n{traceback.format_exc()}")
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🛑 Session crashed at {end_time}")
        sys.exit(1)