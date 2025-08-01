#!/usr/bin/env python3
"""
BMW Controller - 최소한의 GUI 테스트
segfault 원인을 찾기 위한 매우 간단한 GUI 버전
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont

class MinimalGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 윈도우 설정
        self.setWindowTitle("BMW Controller - Minimal Test")
        self.setGeometry(100, 100, 400, 300)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 레이아웃
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 라벨들
        self.speed_label = QLabel("Speed: 0.0 km/h")
        self.speed_label.setFont(QFont("Arial", 24))
        
        self.gear_label = QLabel("Gear: P")
        self.gear_label.setFont(QFont("Arial", 20))
        
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFont(QFont("Arial", 16))
        
        # 레이아웃에 추가
        layout.addWidget(self.speed_label)
        layout.addWidget(self.gear_label)
        layout.addWidget(self.status_label)
        
        # 타이머로 업데이트 (안전한 방식)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # 1초마다 업데이트
        
        # 테스트 카운터
        self.counter = 0
        
        print("✅ Minimal GUI initialized")
        
    def update_display(self):
        """디스플레이 업데이트 (안전한 방식)"""
        try:
            self.counter += 1
            
            # 간단한 업데이트
            self.speed_label.setText(f"Speed: {self.counter * 0.5:.1f} km/h")
            
            gears = ['P', 'R', 'N', 'D', 'M1', 'M2']
            gear = gears[self.counter % len(gears)]
            self.gear_label.setText(f"Gear: {gear}")
            
            self.status_label.setText(f"Status: Running ({self.counter})")
            
            # 콘솔에도 출력
            if self.counter % 5 == 0:
                print(f"GUI Update {self.counter}: Speed={self.counter * 0.5:.1f}, Gear={gear}")
                
        except Exception as e:
            print(f"❌ Update error: {e}")
            
    def closeEvent(self, event):
        """종료 이벤트"""
        print("🛑 GUI closing...")
        self.update_timer.stop()
        event.accept()

def main():
    print("🔍 Starting minimal GUI test...")
    
    # QApplication 생성
    app = QApplication(sys.argv)
    
    # 메인 윈도우
    window = MinimalGUI()
    window.show()
    
    print("🚀 GUI shown, entering event loop...")
    
    try:
        # 이벤트 루프 실행
        sys.exit(app.exec_())
    except Exception as e:
        print(f"❌ GUI error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()