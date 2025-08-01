#!/usr/bin/env python3
"""
BMW PiRacer GUI Widgets Module
GUI 위젯들을 분리한 모듈
"""

import sys
import os
from typing import Optional

# PyQt5 import with fallback
try:
    from PyQt5.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QLabel, QFrame, QTextEdit, QGridLayout, QGroupBox)
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont
    PYQT5_AVAILABLE = True
except ImportError:
    # Mock classes for fallback
    print("⚠️ PyQt5 not available, using mock classes")
    
    class QWidget:
        def __init__(self): pass
        def setLayout(self, layout): pass
        def setFixedSize(self, w, h): pass
        def update(self): pass
        def width(self): return 200
        def height(self): return 200
        def rect(self): return type('MockRect', (), {
            'adjusted': lambda *args: self,
            'width': lambda: 200,
            'height': lambda: 200
        })()
        def paintEvent(self, event): pass
        
    class QMainWindow(QWidget):
        def setWindowTitle(self, title): pass
        def setGeometry(self, x, y, w, h): pass
        def setCentralWidget(self, widget): pass
        def show(self): pass
        def closeEvent(self, event): pass
        
    class QVBoxLayout:
        def addWidget(self, widget): pass
        def addLayout(self, layout): pass
        
    class QHBoxLayout:
        def addWidget(self, widget): pass
        
    class QLabel:
        def __init__(self, text=""): self.text = text
        def setText(self, text): self.text = text
        def setFont(self, font): pass
        def setStyleSheet(self, style): pass
        
    class QPainter:
        def __init__(self, widget): pass
        def isActive(self): return True
        def setRenderHint(self, hint): pass
        def fillRect(self, rect, color): pass
        def setPen(self, pen): pass
        def setFont(self, font): pass
        def drawText(self, rect, align, text): pass
        def drawEllipse(self, x, y, w, h): pass
        def drawRoundedRect(self, rect, rx, ry): pass
        def end(self): pass
        Antialiasing = 1
        
    class QPen:
        def __init__(self, color, width=1): pass
        
    class QColor:
        def __init__(self, r, g, b): pass
        
    class QFont:
        def __init__(self, name, size=10, weight=50): pass
        Bold = 75
        
    class QTimer:
        def __init__(self): pass
        @staticmethod
        def singleShot(ms, func): pass
        def timeout(self): return type('MockSignal', (), {'connect': lambda func: None})()
        def start(self, ms): pass
        def stop(self): pass
        
    class Qt:
        AlignCenter = 0x0004
        
    PYQT5_AVAILABLE = False

class SpeedometerWidget(QWidget):
    """속도계 위젯 - 원본과 동일한 기능"""
    
    def __init__(self):
        super().__init__()
        self.current_speed = 0.0
        self.max_speed = 30.0
        
        # 원본과 동일한 크기 설정
        self.setFixedSize(200, 200)
        
        # 색상 설정 (원본과 동일)
        self.bg_color = QColor(30, 30, 30)
        self.border_color = QColor(100, 100, 100)
        self.speed_color = QColor(0, 255, 100)
        self.text_color = QColor(255, 255, 255)
        self.circle_color = QColor(100, 100, 100)
        
        # 업데이트 제어
        self.update_pending = False
        
    def set_speed(self, speed: float):
        """속도 설정"""
        new_speed = max(0, min(speed, self.max_speed))
        if abs(self.current_speed - new_speed) > 0.1 and not self.update_pending:
            self.current_speed = new_speed
            self.update_pending = True
            # 안전한 업데이트 (50ms 지연)
            if PYQT5_AVAILABLE:
                QTimer.singleShot(50, self._safe_update)
                
    def _safe_update(self):
        """안전한 업데이트"""
        self.update_pending = False
        self.update()
        
    def paintEvent(self, event):
        """원본과 동일한 그리기 로직 (안전하게 수정)"""
        painter = None
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
            
        except Exception as e:
            print(f"❌ Speedometer paint error: {e}")
        finally:
            if painter and painter.isActive():
                painter.end()

class GearDisplayWidget(QWidget):
    """기어 표시 위젯 - 원본과 동일한 기능"""
    
    def __init__(self):
        super().__init__()
        self.current_gear = "P"
        self.manual_gear = 1
        
        # 원본과 동일한 크기
        self.setFixedSize(150, 120)
        
        # 기어별 색상 (원본과 동일)
        self.gear_colors = {
            'P': QColor(255, 255, 0),   # 노란색
            'R': QColor(255, 0, 0),     # 빨간색
            'N': QColor(255, 255, 255), # 흰색
            'D': QColor(0, 255, 0),     # 초록색
            'M': QColor(0, 120, 215),   # 파란색
            'Unknown': QColor(128, 128, 128)  # 회색
        }
        
        # 상태 텍스트 (원본과 동일)
        self.status_texts = {
            'P': "PARK",
            'R': "REVERSE", 
            'N': "NEUTRAL",
            'D': "DRIVE",
            'M': lambda gear: f"MANUAL {gear}",
            'Unknown': "UNKNOWN"
        }
        
        # 업데이트 제어
        self.update_pending = False
        
    def set_gear(self, gear: str, manual_gear: int = 1):
        """기어 상태 업데이트"""
        if (self.current_gear != gear or self.manual_gear != manual_gear) and not self.update_pending:
            self.current_gear = gear
            self.manual_gear = manual_gear
            self.update_pending = True
            # 안전한 업데이트 (50ms 지연)
            if PYQT5_AVAILABLE:
                QTimer.singleShot(50, self._safe_update)
                
    def _safe_update(self):
        """안전한 업데이트"""
        self.update_pending = False
        self.update()
        
    def paintEvent(self, event):
        """원본과 동일한 그리기 로직 (안전하게 수정)"""
        painter = None
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
            
        except Exception as e:
            print(f"❌ Gear display paint error: {e}")
        finally:
            if painter and painter.isActive():
                painter.end()

class BMWMainWindow(QMainWindow):
    """메인 윈도우 - 원본과 동일한 기능"""
    
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        
        # 원본과 동일한 윈도우 설정
        self.setWindowTitle("BMW PiRacer Integrated Control System - GPIO Speed Optimized")
        self.setGeometry(100, 100, 800, 600)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 상단 정보 레이아웃
        top_layout = QHBoxLayout()
        
        # 속도계
        self.speedometer = SpeedometerWidget()
        top_layout.addWidget(self.speedometer)
        
        # 기어 표시
        self.gear_display = GearDisplayWidget()
        top_layout.addWidget(self.gear_display)
        
        main_layout.addLayout(top_layout)
        
        # 상태 라벨
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #2b2b2b;
                padding: 10px;
                border: 1px solid #555;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        # 로그 표시 영역 (원본과 동일)
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.log_text)
        
        # 업데이트 타이머 (원본과 동일한 주기)
        if PYQT5_AVAILABLE:
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_display)
            self.update_timer.start(100)  # 100ms 주기 (10Hz)
        
        print("✅ BMW Main Window initialized")
        
    def update_display(self):
        """디스플레이 업데이트 (원본과 동일한 로직)"""
        if not self.controller:
            return
            
        try:
            state = self.controller.get_state()
            
            # 속도 업데이트
            self.speedometer.set_speed(state.get('speed', 0.0))
            
            # 기어 업데이트
            gear = state.get('gear', 'P')
            manual_gear = state.get('manual_gear', 1)
            self.gear_display.set_gear(gear, manual_gear)
            
            # 상태 라벨 업데이트
            throttle = state.get('throttle', 0.0)
            steering = state.get('steering', 0.0)
            
            status_text = (f"Speed: {state.get('speed', 0.0):.1f} km/h | "
                          f"Gear: {gear} | "
                          f"Throttle: {throttle:+.2f} | "
                          f"Steering: {steering:+.2f}")
            
            self.status_label.setText(status_text)
            
        except Exception as e:
            print(f"❌ Display update error: {e}")
            
    def add_log_message(self, message: str):
        """로그 메시지 추가"""
        if PYQT5_AVAILABLE:
            self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            
            # 로그 개수 제한 (성능 최적화)
            if self.log_text.document().blockCount() > 100:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.select(cursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()  # 줄바꿈 문자 제거
                
    def closeEvent(self, event):
        """창 종료 이벤트 (원본과 동일)"""
        print("🛑 Main window closing...")
        if self.controller:
            self.controller.shutdown()
        event.accept()

# 모듈 테스트
if __name__ == "__main__":
    print("🧪 Testing GUI widgets...")
    
    if PYQT5_AVAILABLE:
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication([])
        
        # 테스트 윈도우
        window = BMWMainWindow()
        window.show()
        
        # 속도 테스트
        import threading
        import time
        
        def test_updates():
            for i in range(20):
                window.speedometer.set_speed(i * 1.5)
                window.gear_display.set_gear(['P', 'R', 'N', 'D', 'M'][i % 5], (i % 8) + 1)
                time.sleep(0.5)
                
        test_thread = threading.Thread(target=test_updates, daemon=True)
        test_thread.start()
        
        app.exec_()
    else:
        print("GUI test completed (mock mode)")