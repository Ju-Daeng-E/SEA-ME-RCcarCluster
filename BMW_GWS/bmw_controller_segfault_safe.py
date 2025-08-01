#!/usr/bin/env python3
"""
BMW PiRacer Controller - Segfault Safe Version
전진 시 segmentation fault 방지를 위한 특별히 강화된 안전 버전
"""

import sys
import os
import can
import time
import threading
import logging
import RPi.GPIO as GPIO
import signal
import traceback
import gc
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# 메모리 관리 강화
import resource

# PiRacer import with safety checks
try:
    from piracer.vehicles import PiRacerStandard
    from piracer.gamepads import ShanWanGamepad
    PIRACER_AVAILABLE = True
    print("✅ PiRacer imports successful")
except ImportError as e:
    print(f"❌ PiRacer import failed: {e}")
    PIRACER_AVAILABLE = False
    sys.exit(1)

class BMWGear(Enum):
    PARK = "P"
    REVERSE = "R" 
    NEUTRAL = "N"
    DRIVE = "D"
    MANUAL = "M"

@dataclass
class SafeVehicleState:
    speed: float = 0.0
    gear: str = "P"
    manual_gear: int = 1
    throttle: float = 0.0
    steering: float = 0.0
    emergency_stop: bool = False
    control_active: bool = False

class SafePiRacerController:
    """Segmentation Fault 방지를 위한 안전한 PiRacer 제어"""
    
    def __init__(self, max_throttle=0.3, max_steering=0.5):
        self.max_throttle = max_throttle
        self.max_steering = max_steering
        self.piracer = None
        self.last_throttle = 0.0
        self.last_steering = 0.0
        self.control_lock = threading.Lock()
        self.emergency_stop = False
        
        # 메모리 사용량 모니터링
        self.max_memory_mb = 100  # 100MB 제한
        
    def initialize(self):
        """안전한 PiRacer 초기화"""
        try:
            print("🔧 Initializing PiRacer with safety checks...")
            
            # 메모리 확인
            memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB to MB
            if memory_usage > self.max_memory_mb:
                raise RuntimeError(f"Memory usage too high: {memory_usage:.1f}MB")
            
            self.piracer = PiRacerStandard()
            
            # 초기 안전 설정
            self.safe_stop()
            time.sleep(0.1)
            
            print("✅ Safe PiRacer initialized")
            return True
            
        except Exception as e:
            print(f"❌ PiRacer initialization failed: {e}")
            return False
            
    def safe_control(self, throttle: float, steering: float) -> bool:
        """안전한 제어 함수"""
        if self.emergency_stop or not self.piracer:
            return False
            
        with self.control_lock:
            try:
                # 입력값 검증
                throttle = max(-self.max_throttle, min(self.max_throttle, throttle))
                steering = max(-self.max_steering, min(self.max_steering, steering))
                
                # 급격한 변화 방지 (스무딩)
                throttle_diff = abs(throttle - self.last_throttle)
                steering_diff = abs(steering - self.last_steering)
                
                if throttle_diff > 0.1:  # 10% 이상 급변화 방지
                    if throttle > self.last_throttle:
                        throttle = self.last_throttle + 0.05
                    else:
                        throttle = self.last_throttle - 0.05
                        
                if steering_diff > 0.2:  # 20% 이상 급변화 방지
                    if steering > self.last_steering:
                        steering = self.last_steering + 0.1
                    else:
                        steering = self.last_steering - 0.1
                
                # 메모리 사용량 체크
                memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                if memory_usage > self.max_memory_mb:
                    print(f"⚠️ High memory usage: {memory_usage:.1f}MB, emergency stop")
                    self.emergency_stop = True
                    return False
                
                # 실제 제어 적용
                self.piracer.set_throttle_percent(throttle)
                self.piracer.set_steering_percent(steering)
                
                self.last_throttle = throttle
                self.last_steering = steering
                
                return True
                
            except Exception as e:
                print(f"❌ Safe control error: {e}")
                self.safe_stop()
                return False
                
    def safe_stop(self):
        """안전한 정지"""
        if self.piracer:
            try:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
                self.last_throttle = 0.0
                self.last_steering = 0.0
            except:
                pass
                
    def cleanup(self):
        """정리"""
        self.emergency_stop = True
        self.safe_stop()

class SegfaultSafeBMWController:
    def __init__(self):
        self.running = False
        self.state = SafeVehicleState()
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGSEGV, self.emergency_handler)
        signal.signal(signal.SIGABRT, self.emergency_handler)
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        
        # 로깅 설정
        self.setup_logging()
        
        # 안전한 PiRacer 컨트롤러
        self.safe_controller = SafePiRacerController(max_throttle=0.3, max_steering=0.5)
        
        # CAN 설정
        self.can_bus = None
        self.setup_can()
        
        # GPIO 설정
        self.speed_pin = 18
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.speed_pin, GPIO.IN)
        
        # 게임패드
        self.gamepad = None
        if PIRACER_AVAILABLE:
            try:
                self.gamepad = ShanWanGamepad()
                self.logger.info("✅ Gamepad initialized")
            except Exception as e:
                self.logger.error(f"❌ Gamepad init failed: {e}")
        
    def emergency_handler(self, sig, frame):
        """응급 상황 핸들러"""
        print(f"\n🚨 EMERGENCY SIGNAL {sig} DETECTED!")
        
        # 즉시 안전 정지
        try:
            self.safe_controller.safe_stop()
        except:
            pass
            
        try:
            GPIO.cleanup()
        except:
            pass
            
        print("🛑 Emergency stop completed")
        sys.exit(1)
        
    def graceful_shutdown(self, sig, frame):
        """정상 종료"""
        print("\n🛑 Graceful shutdown requested...")
        self.running = False
        
    def setup_logging(self):
        """로깅 설정"""
        os.makedirs("logs", exist_ok=True)
        log_file = f'logs/bmw_segfault_safe_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
        """CAN 인터페이스 설정"""
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
        
    def safe_control_loop(self):
        """안전한 제어 루프"""
        self.logger.info("🚗 Safe control loop started")
        
        error_count = 0
        max_errors = 3
        last_status_time = time.time()
        
        while self.running and error_count < max_errors:
            try:
                current_time = time.time()
                
                # 게임패드 제어
                if self.gamepad and not self.state.emergency_stop:
                    gamepad_data = self.gamepad.read_data()
                    
                    if gamepad_data:
                        raw_throttle = gamepad_data.analog_stick_right.y
                        raw_steering = gamepad_data.analog_stick_left.x
                        
                        # 기어에 따른 제어
                        if self.state.gear in ['D', 'R', 'M']:
                            throttle = raw_throttle * 0.3  # 30%로 제한
                            steering = raw_steering * 0.5  # 50%로 제한
                            
                            if self.state.gear == 'R':
                                throttle = -abs(throttle)  # 후진
                                
                            # 안전한 제어 적용
                            success = self.safe_controller.safe_control(throttle, steering)
                            
                            if success:
                                self.state.throttle = throttle
                                self.state.steering = steering
                                self.state.control_active = True
                                error_count = 0  # 성공 시 에러 카운트 리셋
                            else:
                                error_count += 1
                                self.logger.warning(f"⚠️ Control failed, error count: {error_count}")
                                
                        else:
                            # P 또는 N에서는 정지
                            self.safe_controller.safe_stop()
                            self.state.throttle = 0.0
                            self.state.steering = 0.0
                            self.state.control_active = False
                
                # 5초마다 상태 출력
                if current_time - last_status_time >= 5.0:
                    self.print_status()
                    last_status_time = current_time
                    
                    # 가비지 컬렉션
                    gc.collect()
                
                time.sleep(0.05)  # 20Hz
                
            except Exception as e:
                error_count += 1
                self.logger.error(f"❌ Control loop error {error_count}/{max_errors}: {e}")
                
                if error_count >= max_errors:
                    self.logger.critical("🚨 Too many errors, emergency stop")
                    self.state.emergency_stop = True
                    break
                    
                time.sleep(0.5)  # 에러 시 잠시 대기
                
        # 안전 정지
        self.safe_controller.safe_stop()
                
    def print_status(self):
        """상태 출력"""
        gear_text = f"{self.state.gear}"
        if self.state.gear == 'M':
            gear_text += f"{self.state.manual_gear}"
            
        # 메모리 사용량
        memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        
        status = (f"🚗 Speed: {self.state.speed:5.1f} km/h | "
                 f"Gear: {gear_text:3s} | "
                 f"T: {self.state.throttle:+5.2f} | "
                 f"S: {self.state.steering:+5.2f} | "
                 f"Mem: {memory_mb:4.1f}MB | "
                 f"Active: {'✅' if self.state.control_active else '❌'}")
        
        print(status)
        self.logger.info(status)
        
    def run(self):
        """메인 실행"""
        self.logger.info("🚗 BMW Segfault-Safe Controller Starting...")
        
        # PiRacer 초기화
        if not self.safe_controller.initialize():
            self.logger.error("❌ Failed to initialize PiRacer")
            return
        
        self.running = True
        
        # 기어 리스너 스레드 시작
        gear_thread = threading.Thread(target=self.gear_listener, daemon=True)
        gear_thread.start()
        
        try:
            self.safe_control_loop()
            
        except KeyboardInterrupt:
            self.logger.info("🛑 Controller stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Runtime error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def cleanup(self):
        """정리"""
        self.logger.info("🔧 Starting cleanup...")
        self.running = False
        
        self.safe_controller.cleanup()
        
        if self.can_bus:
            self.can_bus.shutdown()
            self.logger.info("✅ CAN bus closed")
            
        GPIO.cleanup()
        self.logger.info("✅ GPIO cleaned up")
        
        self.logger.info("🏁 BMW Segfault-Safe Controller shutdown complete")

if __name__ == "__main__":
    controller = SegfaultSafeBMWController()
    controller.run()