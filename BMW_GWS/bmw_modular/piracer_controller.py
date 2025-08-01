#!/usr/bin/env python3
"""
PiRacer Controller Module
PiRacer 하드웨어 제어 및 게임패드 입력 처리
"""

import sys
import time
import threading
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

# PiRacer import with fallback
try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
    print("✅ PiRacer library available")
except ImportError as e:
    print(f"⚠️ PiRacer library not available: {e}")
    
    # Mock classes for development/testing
    class PiRacerStandard:
        def __init__(self):
            print("🔄 Mock PiRacerStandard initialized")
            
        def set_throttle_percent(self, throttle: float):
            print(f"🚗 Mock throttle: {throttle:.3f}")
            
        def set_steering_percent(self, steering: float):
            print(f"🎯 Mock steering: {steering:.3f}")
            
    class ShanWanGamepad:
        def __init__(self):
            print("🎮 Mock ShanWanGamepad initialized")
            
        def read_data(self):
            # 모든 값을 0으로 반환하는 mock 데이터
            return type('MockGamepadData', (), {
                'analog_stick_right': type('MockStick', (), {'y': 0.0})(),
                'analog_stick_left': type('MockStick', (), {'x': 0.0})()
            })()
            
    PIRACER_AVAILABLE = False

@dataclass 
class PiRacerState:
    """PiRacer 상태 데이터"""
    throttle: float = 0.0
    steering: float = 0.0
    is_active: bool = False
    last_update: float = 0.0
    error_count: int = 0

@dataclass
class GamepadInput:
    """게임패드 입력 데이터"""
    throttle_raw: float = 0.0
    steering_raw: float = 0.0
    throttle_processed: float = 0.0
    steering_processed: float = 0.0
    is_connected: bool = False

class SafePiRacerController:
    """안전한 PiRacer 제어 클래스"""
    
    def __init__(self, max_throttle: float = 0.5, max_steering: float = 0.7):
        """
        초기화
        Args:
            max_throttle: 최대 스로틀 제한 (0.0 ~ 1.0)
            max_steering: 최대 스티어링 제한 (0.0 ~ 1.0)
        """
        self.max_throttle = max_throttle
        self.max_steering = max_steering
        
        # 상태 관리
        self.state = PiRacerState()
        self.running = False
        self.control_lock = threading.Lock()
        
        # 하드웨어 객체
        self.piracer = None
        self.gamepad = None
        
        # 에러 관리
        self.max_errors = 5
        self.error_reset_time = 10.0  # 10초
        self.last_error_time = 0.0
        
        # 스무딩 (급격한 변화 방지)
        self.smoothing_enabled = True
        self.max_throttle_change = 0.1  # 프레임당 최대 10% 변화
        self.max_steering_change = 0.2  # 프레임당 최대 20% 변화
        
        # 로깅
        self.logger = logging.getLogger(__name__)
        
    def initialize(self) -> bool:
        """PiRacer 하드웨어 초기화"""
        try:
            self.logger.info("🔧 Initializing PiRacer hardware...")
            
            # PiRacer 초기화
            self.piracer = PiRacerStandard()
            self.logger.info("✅ PiRacer hardware initialized")
            
            # 게임패드 초기화
            self.gamepad = ShanWanGamepad()
            self.logger.info("✅ Gamepad initialized")
            
            # 초기 안전 설정
            self.piracer.set_throttle_percent(0.0)
            self.piracer.set_steering_percent(0.0)
            
            self.state.is_active = True
            self.state.last_update = time.time()
            
            self.logger.info("🎯 PiRacer controller ready")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ PiRacer initialization failed: {e}")
            self.state.is_active = False
            return False
            
    def read_gamepad(self) -> Optional[GamepadInput]:
        """게임패드 입력 읽기"""
        if not self.gamepad:
            return None
            
        try:
            data = self.gamepad.read_data()
            if not data:
                return None
                
            # 원시 입력값
            throttle_raw = data.analog_stick_right.y
            steering_raw = data.analog_stick_left.x
            
            # 입력값 처리 (데드존, 제한)
            throttle_processed = self._apply_deadzone(throttle_raw, 0.05)
            steering_processed = self._apply_deadzone(steering_raw, 0.05)
            
            # 제한 적용
            throttle_processed = max(-self.max_throttle, min(self.max_throttle, throttle_processed))
            steering_processed = max(-self.max_steering, min(self.max_steering, steering_processed))
            
            return GamepadInput(
                throttle_raw=throttle_raw,
                steering_raw=steering_raw,
                throttle_processed=throttle_processed,
                steering_processed=steering_processed,
                is_connected=True
            )
            
        except Exception as e:
            self.logger.error(f"❌ Gamepad read error: {e}")
            return None
            
    def _apply_deadzone(self, value: float, deadzone: float) -> float:
        """데드존 적용"""
        if abs(value) < deadzone:
            return 0.0
        
        # 데드존 보정
        sign = 1 if value > 0 else -1
        adjusted = (abs(value) - deadzone) / (1.0 - deadzone)
        return sign * adjusted
        
    def _apply_smoothing(self, new_throttle: float, new_steering: float) -> Tuple[float, float]:
        """스무딩 적용 (급격한 변화 방지)"""
        if not self.smoothing_enabled:
            return new_throttle, new_steering
            
        current_throttle = self.state.throttle
        current_steering = self.state.steering
        
        # 스로틀 스무딩
        throttle_diff = new_throttle - current_throttle
        if abs(throttle_diff) > self.max_throttle_change:
            if throttle_diff > 0:
                new_throttle = current_throttle + self.max_throttle_change
            else:
                new_throttle = current_throttle - self.max_throttle_change
                
        # 스티어링 스무딩
        steering_diff = new_steering - current_steering
        if abs(steering_diff) > self.max_steering_change:
            if steering_diff > 0:
                new_steering = current_steering + self.max_steering_change
            else:
                new_steering = current_steering - self.max_steering_change
                
        return new_throttle, new_steering
        
    def set_control(self, throttle: float, steering: float, gear: str = "D") -> bool:
        """
        PiRacer 제어 명령 설정
        Args:
            throttle: 스로틀 값 (-1.0 ~ 1.0)
            steering: 스티어링 값 (-1.0 ~ 1.0) 
            gear: 현재 기어 (기어에 따른 제어 로직 적용)
        Returns:
            bool: 제어 성공 여부
        """
        if not self.state.is_active or not self.piracer:
            return False
            
        with self.control_lock:
            try:
                # 입력값 검증
                throttle = max(-self.max_throttle, min(self.max_throttle, throttle))
                steering = max(-self.max_steering, min(self.max_steering, steering))
                
                # 기어에 따른 제어 로직
                if gear == "P":  # 주차
                    throttle = 0.0
                    steering = 0.0
                elif gear == "N":  # 중립
                    throttle = 0.0
                elif gear == "R":  # 후진
                    throttle = -abs(throttle)  # 후진은 항상 음수
                    
                # 스무딩 적용
                throttle, steering = self._apply_smoothing(throttle, steering)
                
                # 하드웨어 제어 적용
                self.piracer.set_throttle_percent(throttle)
                self.piracer.set_steering_percent(steering)
                
                # 상태 업데이트
                self.state.throttle = throttle
                self.state.steering = steering
                self.state.last_update = time.time()
                self.state.error_count = 0  # 성공 시 에러 카운트 리셋
                
                return True
                
            except Exception as e:
                self.state.error_count += 1
                self.last_error_time = time.time()
                self.logger.error(f"❌ PiRacer control error: {e}")
                
                # 에러 시 안전 정지
                self._emergency_stop()
                
                # 너무 많은 에러가 발생하면 비활성화
                if self.state.error_count >= self.max_errors:
                    self.logger.critical(f"🚨 Too many errors ({self.state.error_count}), disabling PiRacer")
                    self.state.is_active = False
                    
                return False
                
    def _emergency_stop(self):
        """응급 정지"""
        try:
            if self.piracer:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
                self.state.throttle = 0.0
                self.state.steering = 0.0
                self.logger.warning("🛑 Emergency stop executed")
        except Exception as e:
            self.logger.error(f"❌ Emergency stop failed: {e}")
            
    def get_state(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        return {
            'throttle': self.state.throttle,
            'steering': self.state.steering,
            'is_active': self.state.is_active,
            'last_update': self.state.last_update,
            'error_count': self.state.error_count,
            'max_throttle': self.max_throttle,
            'max_steering': self.max_steering
        }
        
    def reset_errors(self):
        """에러 카운트 리셋 (일정 시간 후 자동 복구)"""
        current_time = time.time()
        if current_time - self.last_error_time > self.error_reset_time:
            if self.state.error_count > 0:
                self.logger.info(f"🔄 Resetting error count (was {self.state.error_count})")
                self.state.error_count = 0
                
            if not self.state.is_active and self.piracer:
                self.logger.info("🔄 Attempting to reactivate PiRacer...")
                self.state.is_active = True
                
    def shutdown(self):
        """안전한 종료"""
        self.logger.info("🔧 Shutting down PiRacer controller...")
        self.running = False
        
        # 안전 정지
        self._emergency_stop()
        
        self.state.is_active = False
        self.logger.info("✅ PiRacer controller shutdown complete")

class GamepadControlLoop:
    """게임패드 제어 루프 클래스"""
    
    def __init__(self, piracer_controller: SafePiRacerController):
        self.piracer_controller = piracer_controller
        self.running = False
        self.thread = None
        self.update_rate = 20  # 20Hz
        self.logger = logging.getLogger(__name__)
        
        # 콜백 함수들
        self.on_input_update = None  # 입력 업데이트 콜백
        
    def start(self):
        """제어 루프 시작"""
        if self.thread and self.thread.is_alive():
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._control_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"🎮 Gamepad control loop started ({self.update_rate}Hz)")
        
    def stop(self):
        """제어 루프 정지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.logger.info("🛑 Gamepad control loop stopped")
        
    def _control_loop(self):
        """제어 루프 (별도 스레드에서 실행)"""
        loop_interval = 1.0 / self.update_rate
        
        while self.running:
            try:
                start_time = time.time()
                
                # 게임패드 입력 읽기
                gamepad_input = self.piracer_controller.read_gamepad()
                
                if gamepad_input and gamepad_input.is_connected:
                    # 콜백 호출 (GUI 업데이트 등)
                    if self.on_input_update:
                        self.on_input_update(gamepad_input)
                        
                # 에러 자동 복구 체크
                self.piracer_controller.reset_errors()
                
                # 프레임 레이트 유지
                elapsed = time.time() - start_time
                sleep_time = max(0, loop_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"❌ Control loop error: {e}")
                time.sleep(0.1)  # 에러 시 짧은 대기
                
        self.logger.info("🔚 Control loop ended")

# 모듈 테스트
if __name__ == "__main__":
    print("🧪 Testing PiRacer controller...")
    
    logging.basicConfig(level=logging.INFO)
    
    # 컨트롤러 초기화
    controller = SafePiRacerController(max_throttle=0.3, max_steering=0.5)
    
    if controller.initialize():
        print("✅ Controller initialized successfully")
        
        # 제어 루프 시작
        control_loop = GamepadControlLoop(controller)
        
        def input_callback(gamepad_input):
            print(f"🎮 Throttle: {gamepad_input.throttle_processed:+.3f}, "
                  f"Steering: {gamepad_input.steering_processed:+.3f}")
            
            # 실제 제어 적용 (기어는 D로 고정)
            controller.set_control(
                gamepad_input.throttle_processed,
                gamepad_input.steering_processed,
                "D"
            )
            
        control_loop.on_input_update = input_callback
        control_loop.start()
        
        try:
            # 10초간 테스트
            print("🕐 Running test for 10 seconds...")
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Test interrupted by user")
        finally:
            control_loop.stop()
            controller.shutdown()
            
    else:
        print("❌ Controller initialization failed")
        
    print("🏁 PiRacer controller test completed")