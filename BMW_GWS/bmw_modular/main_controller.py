#!/usr/bin/env python3
"""
BMW PiRacer Main Controller Module
모든 모듈을 통합하는 메인 컨트롤러
원본과 동일한 기능을 유지하면서 모듈화된 아키텍처
"""

import sys
import os
import time
import threading
import logging
import signal
from typing import Optional, Dict, Any
from datetime import datetime

# 환경 변수 설정 (원본과 동일)
if not os.environ.get('DISPLAY'):
    os.environ['DISPLAY'] = ':0'

# 모듈화된 컴포넌트 import
try:
    from gui_widgets import BMWMainWindow, PYQT5_AVAILABLE
    from piracer_controller import SafePiRacerController, GamepadControlLoop, PIRACER_AVAILABLE
    from bmw_can_controller import BMWCANController, CAN_AVAILABLE
    
    if PYQT5_AVAILABLE:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QTimer
        
    print("✅ All modular components imported successfully")
    
except ImportError as e:
    print(f"❌ Failed to import modular components: {e}")
    sys.exit(1)

# GPIO import (원본과 동일)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("✅ GPIO library available")
except ImportError:
    print("⚠️ GPIO library not available, using mock")
    GPIO_AVAILABLE = False
    
    # Mock GPIO
    class MockGPIO:
        BCM = 11
        IN = 1
        
        @staticmethod
        def setmode(mode): pass
        
        @staticmethod
        def setup(pin, mode): pass
        
        @staticmethod
        def input(pin): return 0
        
        @staticmethod
        def cleanup(): pass
        
    GPIO = MockGPIO()

class BMWIntegratedController:
    """
    BMW PiRacer 통합 컨트롤러
    원본의 모든 기능을 모듈화된 아키텍처로 구현
    """
    
    def __init__(self):
        """초기화"""
        self.running = False
        self.initialization_complete = False
        
        # 로깅 설정 (원본과 동일)
        self.setup_logging()
        
        # 상태 관리
        self.current_state = {
            'speed': 0.0,
            'gear': 'P',
            'manual_gear': 1,
            'throttle': 0.0,
            'steering': 0.0,
            'can_connected': False,
            'piracer_active': False,
            'gamepad_connected': False
        }
        self.state_lock = threading.Lock()
        
        # 컴포넌트 객체들
        self.can_controller = None
        self.piracer_controller = None
        self.gamepad_loop = None
        self.gui_app = None
        self.main_window = None
        
        # 스레드들
        self.speed_thread = None
        self.integration_thread = None
        
        # GPIO 설정 (원본과 동일)
        self.speed_pin = 18
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.speed_pin, GPIO.IN)
            
        # 신호 처리 설정
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("🔧 BMW Integrated Controller initialized")
        
    def setup_logging(self):
        """로깅 시스템 설정 (원본과 동일)"""
        os.makedirs("logs", exist_ok=True)
        log_file = f'logs/bmw_modular_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
        
    def signal_handler(self, signum, frame):
        """시그널 핸들러 (안전한 종료)"""
        self.logger.info(f"🛑 Received signal {signum}, initiating shutdown...")
        self.shutdown()
        
    def initialize_components(self) -> bool:
        """모든 컴포넌트 초기화"""
        self.logger.info("🔧 Initializing components...")
        
        # 1. BMW CAN 컨트롤러 초기화
        if CAN_AVAILABLE:
            self.can_controller = BMWCANController('can0')
            
            # CAN 콜백 설정
            self.can_controller.on_gear_change = self.on_gear_change
            self.can_controller.on_message_received = self.on_can_message
            
            if self.can_controller.initialize():
                self.can_controller.start_listening()
                self.current_state['can_connected'] = True
                self.logger.info("✅ CAN controller initialized")
            else:
                self.logger.warning("⚠️ CAN controller initialization failed")
        else:
            self.logger.warning("⚠️ CAN not available, using mock data")
            
        # 2. PiRacer 컨트롤러 초기화
        if PIRACER_AVAILABLE:
            self.piracer_controller = SafePiRacerController(
                max_throttle=0.5,  # 원본과 동일한 제한
                max_steering=0.7
            )
            
            if self.piracer_controller.initialize():
                self.current_state['piracer_active'] = True
                self.logger.info("✅ PiRacer controller initialized")
                
                # 게임패드 제어 루프 설정
                self.gamepad_loop = GamepadControlLoop(self.piracer_controller)
                self.gamepad_loop.on_input_update = self.on_gamepad_input
                
            else:
                self.logger.warning("⚠️ PiRacer controller initialization failed")
        else:
            self.logger.warning("⚠️ PiRacer not available, using simulation mode")
            
        # 3. GUI 초기화
        if PYQT5_AVAILABLE:
            try:
                self.gui_app = QApplication.instance()
                if self.gui_app is None:
                    self.gui_app = QApplication([])
                    
                self.main_window = BMWMainWindow(self)
                self.logger.info("✅ GUI initialized")
                
            except Exception as e:
                self.logger.error(f"❌ GUI initialization failed: {e}")
                return False
        else:
            self.logger.warning("⚠️ GUI not available, running in console mode")
            
        self.initialization_complete = True
        self.logger.info("🎯 All components initialized successfully")
        return True
        
    def on_gear_change(self, gear: str, manual_gear: int):
        """기어 변경 콜백 (CAN에서 호출)"""
        with self.state_lock:
            old_gear = self.current_state['gear']
            self.current_state['gear'] = gear
            self.current_state['manual_gear'] = manual_gear
            
        self.logger.info(f"🔧 Gear change: {old_gear} → {gear}" + 
                        (f"{manual_gear}" if gear == "M" else ""))
        
        # GUI 로그 메시지 추가
        if self.main_window:
            gear_text = f"{gear}{manual_gear}" if gear == "M" else gear
            self.main_window.add_log_message(f"Gear changed to {gear_text}")
            
    def on_can_message(self, message):
        """CAN 메시지 수신 콜백"""
        # 연결 상태 업데이트
        with self.state_lock:
            self.current_state['can_connected'] = True
            
    def on_gamepad_input(self, gamepad_input):
        """게임패드 입력 콜백"""
        with self.state_lock:
            self.current_state['gamepad_connected'] = gamepad_input.is_connected
            
            # 현재 기어에 따른 제어 로직 (원본과 동일)
            current_gear = self.current_state['gear']
            
            if current_gear in ['D', 'R', 'M']:
                throttle = gamepad_input.throttle_processed
                steering = gamepad_input.steering_processed
                
                # 기어에 따른 스로틀 조정
                if current_gear == 'R':
                    throttle = -abs(throttle)  # 후진은 항상 음수
                elif current_gear == 'P' or current_gear == 'N':
                    throttle = 0.0  # 주차/중립에서는 움직임 없음
                    
                # PiRacer 제어 적용
                if self.piracer_controller:
                    success = self.piracer_controller.set_control(throttle, steering, current_gear)
                    if success:
                        self.current_state['throttle'] = throttle
                        self.current_state['steering'] = steering
                        
            else:
                # P 또는 N에서는 정지
                if self.piracer_controller:
                    self.piracer_controller.set_control(0.0, 0.0, current_gear)
                    self.current_state['throttle'] = 0.0
                    self.current_state['steering'] = 0.0
                    
    def speed_monitoring_loop(self):
        """속도 모니터링 루프 (원본과 동일한 로직)"""
        self.logger.info("📊 Speed monitoring started")
        
        pulse_count = 0
        last_time = time.time()
        
        while self.running:
            try:
                if GPIO_AVAILABLE:
                    # GPIO 펄스 기반 속도 계산 (원본과 동일)
                    current_time = time.time()
                    time_diff = current_time - last_time
                    
                    if time_diff >= 1.0:  # 1초마다 계산
                        # 간단한 속도 계산 (실제 구현에서는 홀 센서 등 사용)
                        speed_kmh = pulse_count * 0.1  # 예시 계산
                        
                        with self.state_lock:
                            self.current_state['speed'] = speed_kmh
                            
                        pulse_count = 0
                        last_time = current_time
                else:
                    # Mock 속도 데이터 (스로틀 기반)
                    with self.state_lock:
                        throttle = abs(self.current_state['throttle'])
                        mock_speed = throttle * 25.0  # 최대 25km/h
                        self.current_state['speed'] = mock_speed
                        
                time.sleep(0.1)  # 100ms 주기
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Speed monitoring error: {e}")
                    time.sleep(1.0)
                    
        self.logger.info("📊 Speed monitoring stopped")
        
    def integration_loop(self):
        """통합 모니터링 루프"""
        self.logger.info("🔄 Integration monitoring started")
        
        while self.running:
            try:
                # 에러 복구 체크
                if self.piracer_controller:
                    self.piracer_controller.reset_errors()
                    
                # 연결 상태 체크
                with self.state_lock:
                    if self.can_controller:
                        self.current_state['can_connected'] = self.can_controller.is_connected()
                        
                    if self.piracer_controller:
                        piracer_state = self.piracer_controller.get_state()
                        self.current_state['piracer_active'] = piracer_state['is_active']
                        
                time.sleep(1.0)  # 1초 주기
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Integration monitoring error: {e}")
                    time.sleep(1.0)
                    
        self.logger.info("🔄 Integration monitoring stopped")
        
    def get_state(self) -> Dict[str, Any]:
        """현재 상태 반환 (GUI에서 사용)"""
        with self.state_lock:
            return self.current_state.copy()
            
    def start_background_threads(self):
        """백그라운드 스레드들 시작"""
        self.logger.info("🚀 Starting background threads...")
        
        # 속도 모니터링 스레드
        self.speed_thread = threading.Thread(target=self.speed_monitoring_loop, daemon=True)
        self.speed_thread.start()
        
        # 통합 모니터링 스레드
        self.integration_thread = threading.Thread(target=self.integration_loop, daemon=True)
        self.integration_thread.start()
        
        # 게임패드 제어 시작
        if self.gamepad_loop:
            self.gamepad_loop.start()
            
        self.logger.info("✅ All background threads started")
        
    def run(self):
        """메인 실행 함수"""
        self.logger.info("🚗 BMW Modular Controller Starting...")
        
        # 컴포넌트 초기화
        if not self.initialize_components():
            self.logger.error("❌ Component initialization failed")
            return False
            
        self.running = True
        
        try:
            # 백그라운드 스레드 시작
            self.start_background_threads()
            
            if PYQT5_AVAILABLE and self.main_window:
                # GUI 모드
                self.logger.info("🖥️ Starting GUI mode...")
                self.main_window.show()
                
                # GUI 이벤트 루프 실행
                self.gui_app.exec_()
                
            else:
                # 콘솔 모드
                self.logger.info("💻 Starting console mode...")
                self.console_mode()
                
        except Exception as e:
            self.logger.error(f"❌ Runtime error: {e}")
            return False
        finally:
            self.shutdown()
            
        return True
        
    def console_mode(self):
        """콘솔 모드 실행"""
        self.logger.info("Running in console mode - Press Ctrl+C to exit")
        
        try:
            while self.running:
                # 상태 정보 출력 (5초마다)
                time.sleep(5.0)
                
                state = self.get_state()
                self.logger.info(
                    f"Status: Speed={state['speed']:.1f}km/h, "
                    f"Gear={state['gear']}, "
                    f"Throttle={state['throttle']:+.2f}, "
                    f"Steering={state['steering']:+.2f}, "
                    f"CAN={state['can_connected']}, "
                    f"PiRacer={state['piracer_active']}"
                )
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Console mode interrupted by user")
            
    def shutdown(self):
        """안전한 종료"""
        if not self.running:
            return
            
        self.logger.info("🔧 Starting shutdown sequence...")
        self.running = False
        
        # 1. 게임패드 제어 중지
        if self.gamepad_loop:
            self.gamepad_loop.stop()
            self.logger.info("✅ Gamepad control stopped")
            
        # 2. PiRacer 안전 정지
        if self.piracer_controller:
            self.piracer_controller.shutdown()
            self.logger.info("✅ PiRacer controller shutdown")
            
        # 3. CAN 컨트롤러 종료
        if self.can_controller:
            self.can_controller.shutdown()
            self.logger.info("✅ CAN controller shutdown")
            
        # 4. GPIO 정리
        if GPIO_AVAILABLE:
            GPIO.cleanup()
            self.logger.info("✅ GPIO cleaned up")
            
        # 5. 스레드 정리
        if self.speed_thread and self.speed_thread.is_alive():
            self.speed_thread.join(timeout=2.0)
            
        if self.integration_thread and self.integration_thread.is_alive():
            self.integration_thread.join(timeout=2.0)
            
        self.logger.info("🏁 BMW Modular Controller shutdown complete")

# 메인 실행
if __name__ == "__main__":
    print("🚗 BMW PiRacer Modular Controller")
    print("=" * 50)
    
    controller = BMWIntegratedController()
    
    try:
        success = controller.run()
        exit_code = 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        controller.shutdown()
        exit_code = 0
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        controller.shutdown()
        exit_code = 1
        
    print("🏁 Controller terminated")
    sys.exit(exit_code)