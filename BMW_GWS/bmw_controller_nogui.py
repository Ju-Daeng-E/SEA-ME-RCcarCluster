#!/usr/bin/env python3
"""
BMW PiRacer Controller - No GUI Version
GUI 없는 간단한 콘솔 버전으로 segmentation fault 문제 회피
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
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

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

class BMWControllerNoGUI:
    def __init__(self):
        self.running = False
        self.state = VehicleState()
        
        # CAN 설정
        self.can_bus = None
        self.gear_channel = None
        self.speed_pin = 18
        
        # PiRacer 설정
        if PIRACER_AVAILABLE:
            self.piracer = PiRacerStandard()
            self.gamepad = ShanWanGamepad()
        
        # GPIO 설정
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.speed_pin, GPIO.IN)
        
        self.setup_can()
        self.setup_logging()
        
    def setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f'logs/bmw_nogui_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_can(self):
        """CAN 인터페이스 설정"""
        try:
            # BMW CAN (기어 제어용)
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            self.logger.info("✅ BMW CAN bus initialized")
            
            # 기어 상태 수신을 위한 스레드
            gear_thread = threading.Thread(target=self.gear_listener, daemon=True)
            gear_thread.start()
            
        except Exception as e:
            self.logger.error(f"❌ CAN setup failed: {e}")
            
    def gear_listener(self):
        """기어 상태 수신"""
        while self.running:
            try:
                message = self.can_bus.recv(timeout=1.0)
                if message and message.arbitration_id == 0x12F:
                    gear_data = self.parse_gear_data(message.data)
                    if gear_data:
                        self.state.gear = gear_data['gear']
                        self.state.manual_gear = gear_data.get('manual_gear', 1)
                        
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Gear listener error: {e}")
                    
    def parse_gear_data(self, data: bytes) -> Optional[Dict]:
        """기어 데이터 파싱"""
        if len(data) >= 2:
            gear_byte = data[1]
            gear_map = {0x10: 'P', 0x20: 'R', 0x30: 'N', 0x40: 'D', 0x50: 'M'}
            gear = gear_map.get(gear_byte & 0xF0, 'Unknown')
            manual_gear = data[0] if gear == 'M' else 1
            return {'gear': gear, 'manual_gear': manual_gear}
        return None
        
    def control_loop(self):
        """메인 제어 루프"""
        self.logger.info("🚗 BMW Controller Started (No GUI)")
        self.running = True
        
        try:
            while self.running:
                # 게임패드 입력 읽기
                if PIRACER_AVAILABLE:
                    gamepad_data = self.gamepad.read_data()
                    
                    if gamepad_data:
                        # 스로틀과 스티어링 계산
                        throttle = gamepad_data.analog_stick_right.y * 0.5  # 50% 제한
                        steering = gamepad_data.analog_stick_left.x
                        
                        # 기어에 따른 제어
                        if self.state.gear in ['D', 'R', 'M']:
                            if self.state.gear == 'R':
                                throttle = -abs(throttle)  # 후진
                                
                            self.piracer.set_throttle_percent(throttle)
                            self.piracer.set_steering_percent(steering)
                            
                            self.state.throttle = throttle
                            self.state.steering = steering
                        else:
                            # P 또는 N에서는 정지
                            self.piracer.set_throttle_percent(0.0)
                            self.piracer.set_steering_percent(0.0)
                            self.state.throttle = 0.0
                            self.state.steering = 0.0
                
                # 상태 출력 (5초마다)
                if int(time.time()) % 5 == 0:
                    self.print_status()
                
                time.sleep(0.1)  # 100ms 주기
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Controller stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Control loop error: {e}")
        finally:
            self.cleanup()
            
    def print_status(self):
        """상태 출력"""
        gear_text = f"{self.state.gear}"
        if self.state.gear == 'M':
            gear_text += f"{self.state.manual_gear}"
            
        print(f"\r🚗 Speed: {self.state.speed:5.1f} km/h | "
              f"Gear: {gear_text:3s} | "
              f"Throttle: {self.state.throttle:+5.1f} | "
              f"Steering: {self.state.steering:+5.1f}", end="")
              
    def cleanup(self):
        """정리"""
        self.running = False
        
        if PIRACER_AVAILABLE:
            self.piracer.set_throttle_percent(0.0)
            self.piracer.set_steering_percent(0.0)
            
        if self.can_bus:
            self.can_bus.shutdown()
            
        GPIO.cleanup()
        self.logger.info("✅ Cleanup completed")

if __name__ == "__main__":
    # 로그 디렉터리 생성
    os.makedirs("logs", exist_ok=True)
    
    controller = BMWControllerNoGUI()
    controller.control_loop()