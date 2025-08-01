#!/usr/bin/env python3
"""
BMW PiRacer Integrated Control System
BMW F-Series 기어 레버 + PiRacer 제어 + PyQt5 GUI 통합 시스템

기능:
- BMW 기어봉으로 기어 제어 (P/R/N/D/M1-M8)
- 게임패드로 스로틀/스티어링 제어
- 실시간 속도 표시 (CAN ID 0x100)
- PyQt5 GUI 대시보드
"""

import sys
import os
import can
import time
import threading
import crccheck
from datetime import datetime
from multiprocessing import Process, Value, Array
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QFrame, QTextEdit, QGridLayout,
                           QGroupBox, QPushButton, QProgressBar)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap

# PiRacer 및 게임패드 import (선택적)
try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
except ImportError:
    print("⚠️ PiRacer 라이브러리를 찾을 수 없습니다. 시뮬레이션 모드로 실행됩니다.")
    PIRACER_AVAILABLE = False

# BMW CRC 클래스들
class BMW3FDCRC(crccheck.crc.Crc8Base):
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x70

class BMW197CRC(crccheck.crc.Crc8Base):
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x53

def bmw_3fd_crc(message):
    return BMW3FDCRC.calc(message) & 0xFF

def bmw_197_crc(message):
    return BMW197CRC.calc(message) & 0xFF

class SignalEmitter(QObject):
    """시그널 방출용 클래스"""
    gear_changed = pyqtSignal(str)
    lever_changed = pyqtSignal(str)
    button_changed = pyqtSignal(str, str)  # park_button, unlock_button
    can_status_changed = pyqtSignal(bool)
    message_received = pyqtSignal(str)
    debug_info = pyqtSignal(str)
    stats_updated = pyqtSignal(int)  # message_count
    speed_updated = pyqtSignal(float)  # 속도 업데이트
    piracer_status_changed = pyqtSignal(str)  # PiRacer 상태

class SpeedometerWidget(QWidget):
    """속도계 표시 위젯"""
    
    def __init__(self):
        super().__init__()
        self.current_speed = 0.0
        self.max_speed = 50.0  # 최대 50km/h
        self.setMinimumSize(200, 200)
        
    def set_speed(self, speed):
        """속도 설정"""
        self.current_speed = max(0, min(speed, self.max_speed))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 배경
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        
        # 테두리
        painter.setPen(QPen(QColor(0, 120, 215), 3))
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
        
        # 속도계 원
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(self.width(), self.height()) // 2 - 20
        
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # 속도 텍스트
        painter.setPen(QPen(QColor(0, 255, 100)))
        font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(font)
        
        speed_text = f"{self.current_speed:.1f}"
        text_rect = self.rect().adjusted(0, -20, 0, 0)
        painter.drawText(text_rect, Qt.AlignCenter, speed_text)
        
        # 단위
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 12)
        painter.setFont(font)
        unit_rect = self.rect().adjusted(0, 25, 0, 0)
        painter.drawText(unit_rect, Qt.AlignCenter, "km/h")

class GearDisplayWidget(QWidget):
    """현재 기어 상태 표시 위젯"""
    
    def __init__(self):
        super().__init__()
        self.current_gear = 'Unknown'
        self.manual_gear = 1
        self.setMinimumSize(200, 150)
        
    def set_gear(self, gear, manual_gear=1):
        """기어 상태 업데이트"""
        self.current_gear = gear
        self.manual_gear = manual_gear
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 배경
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        
        # 테두리
        painter.setPen(QPen(QColor(0, 120, 215), 3))
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
        
        # 기어별 색상
        if self.current_gear == 'P':
            color = QColor(255, 100, 100)  # 빨간색
            status_text = "PARK"
        elif self.current_gear == 'R':
            color = QColor(255, 140, 0)    # 주황색
            status_text = "REVERSE"
        elif self.current_gear == 'N':
            color = QColor(255, 255, 100)  # 노란색
            status_text = "NEUTRAL"
        elif self.current_gear == 'D':
            color = QColor(100, 255, 100)  # 녹색
            status_text = "DRIVE"
        elif self.current_gear.startswith('M'):
            color = QColor(100, 150, 255)  # 파란색
            status_text = f"MANUAL {self.manual_gear}"
        else:
            color = QColor(150, 150, 150)  # 회색
            status_text = "UNKNOWN"
        
        # 기어 표시
        painter.setPen(QPen(color))
        font = QFont("Arial", 36, QFont.Bold)
        painter.setFont(font)
        
        # 중앙에 기어 표시
        gear_rect = self.rect().adjusted(0, -20, 0, 0)
        painter.drawText(gear_rect, Qt.AlignCenter, self.current_gear)
        
        # 상태 텍스트
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 10)
        painter.setFont(font)
        status_rect = self.rect().adjusted(0, 30, 0, 0)
        painter.drawText(status_rect, Qt.AlignCenter, status_text)

class BMWPiRacerIntegratedControl(QMainWindow):
    """BMW PiRacer 통합 제어 시스템 GUI"""
    
    def __init__(self):
        super().__init__()
        self.init_system()
        self.init_ui()
        self.setup_can_connections()
        self.start_gamepad_control()
        
    def init_system(self):
        """시스템 초기화"""
        self.signals = SignalEmitter()
        
        # BMW 기어 모니터 상태
        self.current_gear = 'N'  # 기본 N으로 시작
        self.current_lever_pos = 'Unknown'
        self.park_button = 'Released'
        self.unlock_button = 'Released'
        self.last_update = None
        self.message_count = 0
        self.manual_gear = 1
        self.running = True
        
        # PiRacer 상태
        self.current_speed = 0.0
        self.throttle_input = 0.0
        self.steering_input = 0.0
        self.speed_gear = 1  # 1-4단 속도 기어
        
        # CAN 관련
        self.bmw_bus = None
        self.speed_bus = None
        
        # PiRacer 및 게임패드
        self.piracer = None
        self.gamepad = None
        
        if PIRACER_AVAILABLE:
            try:
                self.piracer = PiRacerStandard()
                self.gamepad = ShanWanGamepad()
                self.signals.piracer_status_changed.emit("Connected")
            except Exception as e:
                self.signals.piracer_status_changed.emit(f"Error: {e}")
        else:
            self.signals.piracer_status_changed.emit("Not Available")
        
        # BMW 매핑 테이블들
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
        self.lever_returned_to_Manual_center = True
        self.toggle_timeout = 0.5
        self.last_toggle_time = 0
        self.gws_counter = 0x01
        
        # 시그널 연결
        self.signals.gear_changed.connect(self.update_gear_display)
        self.signals.lever_changed.connect(self.update_lever_display)
        self.signals.button_changed.connect(self.update_button_display)
        self.signals.can_status_changed.connect(self.update_can_status)
        self.signals.message_received.connect(self.add_log_message)
        self.signals.debug_info.connect(self.add_debug_info)
        self.signals.stats_updated.connect(self.update_stats)
        self.signals.speed_updated.connect(self.update_speed_display)
        self.signals.piracer_status_changed.connect(self.update_piracer_status)
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("BMW PiRacer Integrated Control System")
        self.setGeometry(0, 0, 1280, 400)
        
        # 전체화면 설정
        self.showFullScreen()
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QGroupBox {
                color: white;
                border: 2px solid #0078d4;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTextEdit {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        
        # 헤더
        header_layout = self.create_header()
        main_layout.addLayout(header_layout)
        
        # 상단 대시보드 영역
        dashboard_layout = QHBoxLayout()
        
        # 기어 표시 패널
        gear_panel = self.create_gear_panel()
        dashboard_layout.addWidget(gear_panel, 1)
        
        # 속도계 패널
        speed_panel = self.create_speed_panel()
        dashboard_layout.addWidget(speed_panel, 1)
        
        # PiRacer 제어 패널
        piracer_panel = self.create_piracer_panel()
        dashboard_layout.addWidget(piracer_panel, 1)
        
        main_layout.addLayout(dashboard_layout, 2)
        
        # 중간 상태 패널
        status_layout = QHBoxLayout()
        
        # BMW 상태 패널
        bmw_panel = self.create_bmw_status_panel()
        status_layout.addWidget(bmw_panel, 1)
        
        # 시스템 상태 패널
        system_panel = self.create_system_status_panel()
        status_layout.addWidget(system_panel, 1)
        
        main_layout.addLayout(status_layout, 1)
        
        # 하단 로그 영역
        log_panel = self.create_log_panel()
        main_layout.addWidget(log_panel, 1)
        
        central_widget.setLayout(main_layout)
        
    def create_header(self):
        """헤더 생성"""
        header_layout = QHBoxLayout()
        
        # BMW 로고 영역
        logo_label = QLabel("🚗 BMW")
        logo_label.setFont(QFont("Arial", 24, QFont.Bold))
        logo_label.setStyleSheet("color: #0078d4;")
        
        # 타이틀
        title_label = QLabel("PiRacer Integrated Control System")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        
        # 시간
        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.time_label.setFont(QFont("Arial", 12))
        self.time_label.setAlignment(Qt.AlignRight)
        
        # 시간 업데이트 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(self.time_label)
        
        return header_layout
        
    def create_gear_panel(self):
        """기어 표시 패널 생성"""
        group = QGroupBox("Current Gear")
        layout = QVBoxLayout()
        
        # 기어 표시 위젯 (작은 크기로)
        self.gear_widget = GearDisplayWidget()
        self.gear_widget.setMinimumSize(120, 100)
        self.gear_widget.setMaximumSize(150, 120)
        layout.addWidget(self.gear_widget)
        
        # 마지막 업데이트 시간
        self.last_update_label = QLabel("Last Update: Never")
        self.last_update_label.setAlignment(Qt.AlignCenter)
        self.last_update_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.last_update_label)
        
        group.setLayout(layout)
        return group
        
    def create_speed_panel(self):
        """속도계 패널 생성"""
        group = QGroupBox("Speedometer")
        layout = QVBoxLayout()
        
        # 속도계 위젯 (작은 크기로)
        self.speedometer_widget = SpeedometerWidget()
        self.speedometer_widget.setMinimumSize(120, 120)
        self.speedometer_widget.setMaximumSize(150, 150)
        layout.addWidget(self.speedometer_widget)
        
        # 속도 기어 표시
        self.speed_gear_label = QLabel("Speed Gear: 1")
        self.speed_gear_label.setAlignment(Qt.AlignCenter)
        self.speed_gear_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.speed_gear_label)
        
        group.setLayout(layout)
        return group
        
    def create_piracer_panel(self):
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
        
        layout.addWidget(throttle_label)
        layout.addWidget(self.throttle_bar)
        layout.addWidget(steering_label)
        layout.addWidget(self.steering_bar)
        layout.addWidget(self.piracer_status_label)
        
        group.setLayout(layout)
        return group
        
    def create_bmw_status_panel(self):
        """BMW 상태 패널 생성"""
        group = QGroupBox("BMW Lever Status")
        layout = QVBoxLayout()
        
        # 레버 위치
        self.lever_pos_label = QLabel("Lever Position:")
        self.lever_pos_value = QLabel("Unknown")
        self.lever_pos_value.setFont(QFont("Arial", 12, QFont.Bold))
        self.lever_pos_value.setStyleSheet("color: #00ff00;")
        
        # 버튼 상태
        self.park_btn_label = QLabel("Park Button:")
        self.park_btn_value = QLabel("Released")
        self.unlock_btn_label = QLabel("Unlock Button:")
        self.unlock_btn_value = QLabel("Released")
        
        layout.addWidget(self.lever_pos_label)
        layout.addWidget(self.lever_pos_value)
        layout.addWidget(self.park_btn_label)
        layout.addWidget(self.park_btn_value)
        layout.addWidget(self.unlock_btn_label)
        layout.addWidget(self.unlock_btn_value)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
        
    def create_system_status_panel(self):
        """시스템 상태 패널 생성"""
        group = QGroupBox("System Status")
        layout = QVBoxLayout()
        
        # CAN 상태
        self.can_status_label = QLabel("BMW CAN:")
        self.can_status_value = QLabel("Disconnected")
        self.can_status_value.setStyleSheet("color: #ff0000;")
        
        self.speed_can_label = QLabel("Speed CAN:")
        self.speed_can_value = QLabel("Disconnected")
        self.speed_can_value.setStyleSheet("color: #ff0000;")
        
        # 메시지 카운터
        self.msg_count_label = QLabel("Messages:")
        self.msg_count_value = QLabel("0")
        
        # 제어 버튼
        self.connect_btn = QPushButton("Connect CAN")
        self.connect_btn.clicked.connect(self.toggle_can_connection)
        
        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.clicked.connect(self.clear_logs)
        
        layout.addWidget(self.can_status_label)
        layout.addWidget(self.can_status_value)
        layout.addWidget(self.speed_can_label)
        layout.addWidget(self.speed_can_value)
        layout.addWidget(self.msg_count_label)
        layout.addWidget(self.msg_count_value)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.clear_btn)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
        
    def create_log_panel(self):
        """로그 패널 생성"""
        group = QGroupBox("Real-time System Logs")
        layout = QVBoxLayout()
        
        # 로그 텍스트 (높이 줄임)
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(80)
        self.log_text.setFont(QFont("Consolas", 8))
        
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group
        
    def setup_can_connections(self):
        """CAN 연결 설정"""
        # BMW CAN (can0)
        try:
            self.bmw_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            self.signals.can_status_changed.emit(True)
            self.signals.message_received.emit("✓ BMW CAN connected (can0)")
            self.start_bmw_monitoring()
            self.start_led_control()
        except Exception as e:
            self.bmw_bus = None
            self.signals.message_received.emit(f"⚠ BMW CAN not available: {e}")
        
        # Speed CAN (can1)
        try:
            self.speed_bus = can.interface.Bus(channel='can1', bustype='socketcan')
            self.signals.message_received.emit("✓ Speed CAN connected (can1)")
            self.start_speed_monitoring()
        except Exception as e:
            self.speed_bus = None
            self.signals.message_received.emit(f"⚠ Speed CAN not available: {e}")
    
    def start_bmw_monitoring(self):
        """BMW CAN 모니터링 시작"""
        if not self.bmw_bus:
            return
        
        def bmw_monitor_loop():
            while self.running and self.bmw_bus:
                try:
                    msg = self.bmw_bus.recv(timeout=1.0)
                    if msg:
                        self.bmw_message_handler(msg)
                except Exception as e:
                    if self.running:
                        self.signals.message_received.emit(f"❌ BMW CAN Error: {e}")
                        time.sleep(0.1)
        
        bmw_thread = threading.Thread(target=bmw_monitor_loop, daemon=True)
        bmw_thread.start()
    
    def start_speed_monitoring(self):
        """속도 CAN 모니터링 시작"""
        if not self.speed_bus:
            return
        
        def speed_monitor_loop():
            while self.running and self.speed_bus:
                try:
                    msg = self.speed_bus.recv(timeout=1.0)
                    if msg and msg.arbitration_id == 0x100 and len(msg.data) >= 2:
                        raw_speed = (msg.data[0] << 8) | msg.data[1]
                        speed_kmh = raw_speed / 100.0
                        self.current_speed = speed_kmh
                        self.signals.speed_updated.emit(speed_kmh)
                except Exception as e:
                    if self.running:
                        self.signals.message_received.emit(f"❌ Speed CAN Error: {e}")
                        time.sleep(0.1)
        
        speed_thread = threading.Thread(target=speed_monitor_loop, daemon=True)
        speed_thread.start()
    
    def start_gamepad_control(self):
        """게임패드 제어 시작"""
        if not self.gamepad or not self.piracer:
            return
        
        def gamepad_loop():
            last_l2 = last_r2 = False
            
            while self.running:
                try:
                    gamepad_input = self.gamepad.read_data()
                    
                    # 속도 기어 조절 (L2/R2)
                    if gamepad_input.button_l2 and not last_l2:
                        self.speed_gear = max(1, self.speed_gear - 1)
                        self.signals.message_received.emit(f"🔽 Speed Gear: {self.speed_gear}")
                    if gamepad_input.button_r2 and not last_r2:
                        self.speed_gear = min(4, self.speed_gear + 1)
                        self.signals.message_received.emit(f"🔼 Speed Gear: {self.speed_gear}")
                    
                    last_l2 = gamepad_input.button_l2
                    last_r2 = gamepad_input.button_r2
                    
                    # 조이스틱 입력
                    self.throttle_input = -gamepad_input.analog_stick_right.y
                    self.steering_input = -gamepad_input.analog_stick_left.x
                    
                    # 기어에 따른 스로틀 제어
                    speed_limit = self.speed_gear * 0.25
                    
                    if self.current_gear == 'D':
                        throttle = max(0.0, self.throttle_input)  # 전진만
                    elif self.current_gear == 'R':
                        throttle = min(0.0, self.throttle_input)  # 후진만
                    else:
                        throttle = 0.0  # P, N에서는 정지
                    
                    throttle *= speed_limit
                    
                    # PiRacer 제어
                    self.piracer.set_throttle_percent(throttle)
                    self.piracer.set_steering_percent(self.steering_input)
                    
                    # UI 업데이트를 위한 시그널 (값을 100배해서 진행바에 표시)
                    self.throttle_bar.setValue(int(throttle * 100))
                    self.steering_bar.setValue(int(self.steering_input * 100))
                    
                    time.sleep(0.05)  # 20Hz
                    
                except Exception as e:
                    self.signals.message_received.emit(f"❌ Gamepad Error: {e}")
                    time.sleep(1)
        
        gamepad_thread = threading.Thread(target=gamepad_loop, daemon=True)
        gamepad_thread.start()
        self.signals.message_received.emit("🎮 Gamepad control started")
    
    def bmw_message_handler(self, msg):
        """BMW CAN 메시지 핸들러"""
        self.message_count += 1
        self.signals.stats_updated.emit(self.message_count)
        
        if msg.arbitration_id == 0x197:
            # BMW 기어 레버 메시지
            if self.decode_lever_message(msg):
                # 기어 변경시 LED 업데이트
                if self.current_gear != 'Unknown':
                    self.send_gear_led(self.current_gear, flash=False)
        
        elif msg.arbitration_id == 0x3FD:
            # 기어 디스플레이 메시지
            pass
        
        elif msg.arbitration_id == 0x55e:
            # 하트비트 메시지
            pass
    
    def decode_lever_message(self, msg):
        """레버 메시지 디코딩 (원본과 동일한 로직)"""
        if len(msg.data) >= 4:
            crc = msg.data[0]
            counter = msg.data[1]
            lever_pos = msg.data[2]
            park_btn = msg.data[3]
            
            # 레버 위치 매핑
            if lever_pos in self.lever_position_map:
                self.current_lever_pos = self.lever_position_map[lever_pos]
            else:
                self.current_lever_pos = f'Unknown (0x{lever_pos:02X})'
            
            # 버튼 상태
            self.park_button = 'Pressed' if (park_btn & 0x01) != 0 else 'Released'
            self.unlock_button = 'Pressed' if (park_btn & 0x02) != 0 else 'Released'
            
            # 토글 처리
            self.previous_lever_position = self.current_lever_position
            self.current_lever_position = lever_pos
            self.handle_toggle_action(lever_pos, park_btn)
            
            # UI 업데이트
            self.signals.lever_changed.emit(self.current_lever_pos)
            self.signals.button_changed.emit(self.park_button, self.unlock_button)
            self.signals.gear_changed.emit(self.current_gear)
            
            self.last_update = datetime.now().strftime("%H:%M:%S")
            return True
        return False
    
    # BMW 기어 토글 처리 메서드들 (원본과 동일)
    def handle_toggle_action(self, lever_pos, park_btn):
        """토글 방식 기어 전환 처리"""
        current_time = time.time()
        unlock_pressed = (park_btn & 0x02) != 0
        
        if unlock_pressed:
            if self.current_gear == 'P' and lever_pos == 0x0E:
                self.current_gear = 'N'
                self.signals.message_received.emit("🔓 Unlock: PARK → NEUTRAL")
                return
        
        if (park_btn & 0x01) != 0:
            if lever_pos == 0x0E:
                self.current_gear = 'P'
                self.signals.message_received.emit("🅿️ Park Button → PARK")
                return
        
        if current_time - self.last_toggle_time < self.toggle_timeout:
            return
        
        if lever_pos == 0x0E and not self.lever_returned_to_center:
            self.lever_returned_to_center = True
            self.process_toggle_transition()
            self.last_toggle_time = current_time
        elif lever_pos != 0x0E:
            self.lever_returned_to_center = False

        if lever_pos == 0x7E and not self.lever_returned_to_Manual_center:
            self.lever_returned_to_Manual_center = True
            self.process_toggle_Manual_transition()
            self.last_toggle_time = current_time
        elif lever_pos != 0x7E:
            self.lever_returned_to_Manual_center = False
    
    def process_toggle_transition(self):
        """토글 전환 처리"""
        if self.previous_lever_position == 0x1E:  # UP
            self.handle_up_toggle()
        elif self.previous_lever_position == 0x2E:  # UP+
            self.current_gear = 'P'
            self.signals.message_received.emit("🎯 UP+ → PARK")
        elif self.previous_lever_position == 0x3E:  # DOWN
            self.handle_down_toggle()
        elif self.previous_lever_position == 0x7E:  # SIDE
            self.handle_side_toggle()
    
    def process_toggle_Manual_transition(self):
        """수동 토글 전환 처리"""
        if self.previous_lever_position == 0x5E:  # Manual Down
            self.handle_manual_down_toggle()
        elif self.previous_lever_position == 0x6E:  # Manual Up
            self.handle_manual_up_toggle()
        elif self.previous_lever_position == 0x0E:  # Center → Side
            self.handle_side_toggle()
    
    def handle_up_toggle(self):
        """위 토글 처리"""
        if self.current_gear == 'N':
            self.current_gear = 'R'
            self.signals.message_received.emit("🎯 N → REVERSE")
        elif self.current_gear == 'D':
            self.current_gear = 'N'
            self.signals.message_received.emit("🎯 D → NEUTRAL")
        else:
            self.current_gear = 'N'
            self.signals.message_received.emit("🎯 UP → NEUTRAL")
    
    def handle_down_toggle(self):
        """아래 토글 처리"""
        if self.current_gear == 'N':
            self.current_gear = 'D'
            self.signals.message_received.emit("🎯 N → DRIVE")
        elif self.current_gear == 'R':
            self.current_gear = 'N'
            self.signals.message_received.emit("🎯 R → NEUTRAL")
        else:
            self.current_gear = 'D'
            self.signals.message_received.emit("🎯 DOWN → DRIVE")
    
    def handle_side_toggle(self):
        """사이드 토글 처리"""
        if self.current_gear == 'D':
            self.manual_gear = 1
            self.current_gear = f'M{self.manual_gear}'
            self.signals.message_received.emit(f"🎯 D → MANUAL M{self.manual_gear}")
        elif self.current_gear.startswith('M'):
            self.current_gear = 'D'
            self.signals.message_received.emit("🎯 Manual → DRIVE")
        else:
            self.current_gear = 'D'
            self.signals.message_received.emit("🎯 SIDE → DRIVE")
    
    def handle_manual_up_toggle(self):
        """수동 업 토글 처리"""
        if self.current_gear.startswith('M') and self.manual_gear < 8:
            self.manual_gear += 1
            self.current_gear = f'M{self.manual_gear}'
            self.signals.message_received.emit(f"🔼 Manual → M{self.manual_gear}")
    
    def handle_manual_down_toggle(self):
        """수동 다운 토글 처리"""
        if self.current_gear.startswith('M') and self.manual_gear > 1:
            self.manual_gear -= 1
            self.current_gear = f'M{self.manual_gear}'
            self.signals.message_received.emit(f"🔽 Manual → M{self.manual_gear}")
    
    def send_gear_led(self, gear, flash=False):
        """기어 LED 전송"""
        if not self.bmw_bus:
            return
        
        gear_led_codes = {
            'P': 0x20, 'R': 0x40, 'N': 0x60, 'D': 0x80, 'S': 0x81,
        }
        
        if gear.startswith('M'):
            led_code = 0x81
        elif gear in gear_led_codes:
            led_code = gear_led_codes[gear]
        else:
            return
        
        try:
            self.gws_counter = (self.gws_counter + 1) if self.gws_counter < 0x0E else 0x01
            payload_without_crc = [self.gws_counter, led_code, 0x00, 0x00]
            crc = bmw_3fd_crc(payload_without_crc)
            payload = [crc] + payload_without_crc
            
            message = can.Message(
                arbitration_id=0x3FD,
                data=payload,
                is_extended_id=False
            )
            
            self.bmw_bus.send(message)
        except Exception as e:
            pass
    
    def start_led_control(self):
        """LED 제어 시작"""
        def led_control_loop():
            while self.running and self.bmw_bus:
                if self.current_gear != 'Unknown':
                    self.send_gear_led(self.current_gear, flash=False)
                time.sleep(0.1)
        
        if self.bmw_bus:
            led_thread = threading.Thread(target=led_control_loop, daemon=True)
            led_thread.start()
    
    # UI 업데이트 슬롯들
    def update_time(self):
        """시간 업데이트"""
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
    
    def update_gear_display(self, gear):
        """기어 표시 업데이트"""
        self.gear_widget.set_gear(gear, self.manual_gear)
        self.last_update_label.setText(f"Last Update: {self.last_update}")
    
    def update_lever_display(self, lever_pos):
        """레버 위치 업데이트"""
        self.lever_pos_value.setText(lever_pos)
    
    def update_button_display(self, park_btn, unlock_btn):
        """버튼 상태 업데이트"""
        self.park_btn_value.setText(park_btn)
        self.unlock_btn_value.setText(unlock_btn)
        
        park_color = "#ff4444" if park_btn == "Pressed" else "#44ff44"
        unlock_color = "#ff4444" if unlock_btn == "Pressed" else "#44ff44"
        
        self.park_btn_value.setStyleSheet(f"color: {park_color};")
        self.unlock_btn_value.setStyleSheet(f"color: {unlock_color};")
    
    def update_can_status(self, connected):
        """CAN 상태 업데이트"""
        if connected:
            self.can_status_value.setText("Connected")
            self.can_status_value.setStyleSheet("color: #00ff00;")
        else:
            self.can_status_value.setText("Disconnected")
            self.can_status_value.setStyleSheet("color: #ff0000;")
    
    def update_speed_display(self, speed):
        """속도 표시 업데이트"""
        self.speedometer_widget.set_speed(speed)
        self.speed_gear_label.setText(f"Speed Gear: {self.speed_gear}")
    
    def update_piracer_status(self, status):
        """PiRacer 상태 업데이트"""
        self.piracer_status_label.setText(f"Status: {status}")
    
    def update_stats(self, count):
        """통계 업데이트"""
        self.msg_count_value.setText(str(count))
    
    def add_log_message(self, message):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_text.append(f"{timestamp} {message}")
        
        # 로그가 너무 많아지면 상단 제거
        if self.log_text.document().blockCount() > 50:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def add_debug_info(self, debug_msg):
        """디버그 정보 추가"""
        self.add_log_message(debug_msg)
    
    def clear_logs(self):
        """로그 지우기"""
        self.log_text.clear()
        self.add_log_message("🧹 Logs cleared")
    
    def toggle_can_connection(self):
        """CAN 연결 토글"""
        # 재연결 로직은 단순화
        self.clear_logs()
        self.add_log_message("🔄 Reconnecting CAN interfaces...")
    
    def closeEvent(self, event):
        """프로그램 종료 시"""
        self.running = False
        if self.bmw_bus:
            self.bmw_bus.shutdown()
        if self.speed_bus:
            self.speed_bus.shutdown()
        event.accept()

def setup_can_interfaces():
    """CAN 인터페이스 설정"""
    print("🔧 Setting up CAN interfaces...")
    
    # can0 설정 시도
    result0 = os.system("sudo ip link set can0 down 2>/dev/null")
    result0 = os.system("sudo ip link set can0 up type can bitrate 500000 2>/dev/null")
    if result0 == 0:
        print("✓ CAN0 interface configured successfully")
    else:
        print("⚠ Failed to configure CAN0 interface")
    
    # can1 설정 시도
    result1 = os.system("sudo ip link set can1 down 2>/dev/null")
    result1 = os.system("sudo ip link set can1 up type can bitrate 500000 2>/dev/null")
    if result1 == 0:
        print("✓ CAN1 interface configured successfully")
    else:
        print("⚠ Failed to configure CAN1 interface")

def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    # CAN 인터페이스 자동 설정
    setup_can_interfaces()
    
    # 메인 윈도우 생성
    window = BMWPiRacerIntegratedControl()
    window.show()
    
    print("🚀 BMW PiRacer Integrated Control System Started")
    print("Features:")
    print("- BMW Gear Lever Control (P/R/N/D/M1-M8)")
    print("- Gamepad Throttle/Steering Control")
    print("- Real-time Speed Display")
    print("- Integrated PyQt5 Dashboard")
    print("- Dual CAN Bus Support (BMW + Speed)")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()