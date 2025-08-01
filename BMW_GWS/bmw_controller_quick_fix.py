#!/usr/bin/env python3
"""
BMW PiRacer Controller - Quick Segfault Fix
QPainter 문제를 해결한 빠른 수정 버전
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

@dataclass
class VehicleState:
    speed: float = 0.0
    gear: str = "P"
    manual_gear: int = 1
    throttle: float = 0.0
    steering: float = 0.0

class QuickFixBMWController:
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
        
    def setup_logging(self):
        """로깅 설정"""
        os.makedirs("logs", exist_ok=True)
        log_file = f'logs/bmw_quick_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
        """메인 제어 루프 (GUI 없음)"""
        self.logger.info("🚗 BMW Quick Fix Controller Started (Console Only)")
        self.running = True
        
        # 기어 리스너 스레드 시작
        gear_thread = threading.Thread(target=self.gear_listener, daemon=True)
        gear_thread.start()
        
        last_status_time = time.time()
        
        try:
            while self.running:
                current_time = time.time()
                
                # 게임패드 제어
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
                
                # 5초마다 상태 출력
                if current_time - last_status_time >= 5.0:
                    self.print_status()
                    last_status_time = current_time
                
                time.sleep(0.05)  # 20Hz
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Controller stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Control loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def print_status(self):
        """상태 출력"""
        gear_text = f"{self.state.gear}"
        if self.state.gear == 'M':
            gear_text += f"{self.state.manual_gear}"
            
        status = (f"🚗 Speed: {self.state.speed:5.1f} km/h | "
                 f"Gear: {gear_text:3s} | "
                 f"Throttle: {self.state.throttle:+5.2f} | "
                 f"Steering: {self.state.steering:+5.2f}")
        
        print(status)
        self.logger.info(status)
              
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
        
        self.logger.info("🏁 BMW Quick Fix Controller shutdown complete")

if __name__ == "__main__":
    controller = QuickFixBMWController()
    controller.control_loop()