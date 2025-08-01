#!/usr/bin/env python3
"""
BMW CAN Controller Module
BMW 기어 레버 CAN 통신 및 기어 상태 관리
"""

import sys
import time
import threading
import logging
import crccheck
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# CAN import with fallback
try:
    import can
    CAN_AVAILABLE = True
    print("✅ CAN library available")
except ImportError as e:
    print(f"⚠️ CAN library not available: {e}")
    
    # Mock CAN for development/testing
    class MockMessage:
        def __init__(self, arbitration_id=0x12F, data=b'\x01\x40\x0e\xc0'):
            self.arbitration_id = arbitration_id
            self.data = data
            self.timestamp = time.time()
            
    class MockBus:
        def __init__(self, channel='can0', interface='socketcan'):
            print(f"🔄 Mock CAN bus initialized ({channel})")
            self._counter = 0
            
        def recv(self, timeout=1.0):
            time.sleep(0.1)  # 시뮬레이트 딜레이
            self._counter += 1
            
            # 기어 시뮬레이션 (P -> R -> N -> D -> M1 -> M2 -> ...)
            gear_states = [
                b'\x01\x10\x0e\xc0',  # P
                b'\x01\x20\x0e\xc0',  # R  
                b'\x01\x30\x0e\xc0',  # N
                b'\x01\x40\x0e\xc0',  # D
                b'\x01\x50\x0e\xc0',  # M1
                b'\x02\x50\x0e\xc0',  # M2
                b'\x03\x50\x0e\xc0',  # M3
            ]
            
            data = gear_states[self._counter % len(gear_states)]
            return MockMessage(0x12F, data)
            
        def shutdown(self):
            print("🔄 Mock CAN bus shutdown")
            
    can = type('MockCAN', (), {
        'interface': type('MockInterface', (), {
            'Bus': MockBus
        })()
    })()
    
    CAN_AVAILABLE = False

class BMWGear(Enum):
    """BMW 기어 상태"""
    PARK = "P"
    REVERSE = "R"
    NEUTRAL = "N" 
    DRIVE = "D"
    MANUAL = "M"
    UNKNOWN = "Unknown"

@dataclass
class BMWGearState:
    """BMW 기어 상태 데이터"""
    gear: str = "P"
    manual_gear: int = 1
    last_update: float = 0.0
    message_count: int = 0
    crc_valid: bool = True

class BMWCANController:
    """BMW CAN 통신 컨트롤러"""
    
    def __init__(self, can_interface: str = 'can0'):
        """
        초기화
        Args:
            can_interface: CAN 인터페이스 이름 (기본값: can0)
        """
        self.can_interface = can_interface
        self.can_bus = None
        self.running = False
        
        # 상태 관리
        self.gear_state = BMWGearState()
        self.state_lock = threading.Lock()
        
        # BMW 기어 메시지 매핑 (원본과 동일)
        self.gear_map = {
            0x10: BMWGear.PARK.value,
            0x20: BMWGear.REVERSE.value,
            0x30: BMWGear.NEUTRAL.value,
            0x40: BMWGear.DRIVE.value,
            0x50: BMWGear.MANUAL.value
        }
        
        # 메시지 통계
        self.message_stats = {
            'total_messages': 0,
            'valid_messages': 0,
            'invalid_messages': 0,
            'crc_errors': 0,
            'last_message_time': 0.0
        }
        
        # 콜백 함수들
        self.on_gear_change = None  # 기어 변경 콜백
        self.on_message_received = None  # 메시지 수신 콜백
        
        # 로깅
        self.logger = logging.getLogger(__name__)
        
        # CAN 리스너 스레드
        self.listener_thread = None
        
    def initialize(self) -> bool:
        """CAN 버스 초기화"""
        try:
            self.logger.info(f"🔧 Initializing BMW CAN bus ({self.can_interface})...")
            
            self.can_bus = can.interface.Bus(
                channel=self.can_interface,
                interface='socketcan'
            )
            
            self.logger.info("✅ BMW CAN bus initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ BMW CAN initialization failed: {e}")
            return False
            
    def start_listening(self):
        """CAN 메시지 수신 시작"""
        if not self.can_bus:
            self.logger.error("❌ CAN bus not initialized")
            return False
            
        if self.listener_thread and self.listener_thread.is_alive():
            self.logger.warning("⚠️ CAN listener already running")
            return True
            
        self.running = True
        self.listener_thread = threading.Thread(target=self._message_listener, daemon=True)
        self.listener_thread.start()
        
        self.logger.info("🔍 BMW CAN message listener started")
        return True
        
    def stop_listening(self):
        """CAN 메시지 수신 중지"""
        self.running = False
        
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
            
        self.logger.info("🛑 BMW CAN message listener stopped")
        
    def _message_listener(self):
        """CAN 메시지 리스너 (별도 스레드에서 실행)"""
        self.logger.info("🎧 CAN message listener thread started")
        
        while self.running:
            try:
                # CAN 메시지 수신 (타임아웃 1초)
                message = self.can_bus.recv(timeout=1.0)
                
                if message and self.running:
                    self._process_message(message)
                    
            except Exception as e:
                if self.running:  # 정상 종료가 아닌 경우만 에러 로그
                    self.logger.error(f"❌ CAN message receive error: {e}")
                    time.sleep(0.1)  # 에러 시 짧은 대기
                    
        self.logger.info("🔚 CAN message listener thread ended")
        
    def _process_message(self, message):
        """CAN 메시지 처리"""
        try:
            # 통계 업데이트
            self.message_stats['total_messages'] += 1
            self.message_stats['last_message_time'] = time.time()
            
            # BMW 기어 레버 메시지 확인 (ID: 0x12F = 303)
            if message.arbitration_id == 0x12F:
                gear_data = self._parse_gear_message(message.data)
                
                if gear_data:
                    self.message_stats['valid_messages'] += 1
                    self._update_gear_state(gear_data)
                else:
                    self.message_stats['invalid_messages'] += 1
                    
            # 메시지 수신 콜백 호출
            if self.on_message_received:
                self.on_message_received(message)
                
        except Exception as e:
            self.logger.error(f"❌ Message processing error: {e}")
            self.message_stats['invalid_messages'] += 1
            
    def _parse_gear_message(self, data: bytes) -> Optional[Dict[str, Any]]:
        """
        BMW 기어 메시지 파싱 (원본과 동일한 로직)
        
        메시지 구조:
        - Byte 0: Manual gear number (M모드에서만 사용)
        - Byte 1: Gear status (0x10=P, 0x20=R, 0x30=N, 0x40=D, 0x50=M)
        - Byte 2-3: CRC 및 기타 데이터
        """
        if len(data) < 4:
            return None
            
        try:
            manual_gear_byte = data[0]
            gear_byte = data[1]
            
            # CRC 검증 (선택적)
            if self._verify_crc(data):
                self.gear_state.crc_valid = True
            else:
                self.gear_state.crc_valid = False
                self.message_stats['crc_errors'] += 1
                # CRC 에러가 있어도 데이터는 처리 (원본 동작과 동일)
                
            # 기어 상태 매핑
            gear_code = gear_byte & 0xF0  # 상위 4비트만 사용
            gear = self.gear_map.get(gear_code, BMWGear.UNKNOWN.value)
            
            # Manual 기어 번호 (M모드에서만 유효)
            if gear == BMWGear.MANUAL.value:
                manual_gear = max(1, min(8, manual_gear_byte))  # 1-8 범위로 제한
            else:
                manual_gear = 1
                
            return {
                'gear': gear,
                'manual_gear': manual_gear,
                'raw_data': data.hex(),
                'timestamp': time.time()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Gear message parsing error: {e}")
            return None
            
    def _verify_crc(self, data: bytes) -> bool:
        """CRC 검증 (간단한 체크섬 방식)"""
        try:
            # 간단한 CRC 검증 (원본과 유사)
            calculated_crc = sum(data[:2]) & 0xFF
            received_crc = data[2]
            
            return calculated_crc == received_crc
            
        except Exception:
            return False
            
    def _update_gear_state(self, gear_data: Dict[str, Any]):
        """기어 상태 업데이트"""
        with self.state_lock:
            old_gear = self.gear_state.gear
            old_manual_gear = self.gear_state.manual_gear
            
            # 상태 업데이트
            self.gear_state.gear = gear_data['gear']
            self.gear_state.manual_gear = gear_data['manual_gear']
            self.gear_state.last_update = gear_data['timestamp']
            self.gear_state.message_count += 1
            
            # 기어 변경 감지 및 콜백 호출
            if (old_gear != self.gear_state.gear or 
                old_manual_gear != self.gear_state.manual_gear):
                
                if old_gear != self.gear_state.gear:
                    self.logger.info(f"🔧 Gear change: {old_gear} → {self.gear_state.gear}")
                    
                if (self.gear_state.gear == BMWGear.MANUAL.value and 
                    old_manual_gear != self.gear_state.manual_gear):
                    self.logger.info(f"🔧 Manual gear: M{old_manual_gear} → M{self.gear_state.manual_gear}")
                
                # 기어 변경 콜백 호출
                if self.on_gear_change:
                    self.on_gear_change(self.gear_state.gear, self.gear_state.manual_gear)
                    
    def get_current_gear(self) -> Tuple[str, int]:
        """현재 기어 상태 반환"""
        with self.state_lock:
            return self.gear_state.gear, self.gear_state.manual_gear
            
    def get_gear_state(self) -> Dict[str, Any]:
        """전체 기어 상태 정보 반환"""
        with self.state_lock:
            return {
                'gear': self.gear_state.gear,
                'manual_gear': self.gear_state.manual_gear,
                'last_update': self.gear_state.last_update,
                'message_count': self.gear_state.message_count,
                'crc_valid': self.gear_state.crc_valid,
                'stats': self.message_stats.copy()
            }
            
    def is_connected(self) -> bool:
        """CAN 연결 상태 확인"""
        current_time = time.time()
        last_message_time = self.message_stats['last_message_time']
        
        # 5초 이내에 메시지를 받았으면 연결된 것으로 판단
        return (last_message_time > 0 and 
                current_time - last_message_time < 5.0)
                
    def get_connection_info(self) -> Dict[str, Any]:
        """연결 정보 반환"""
        return {
            'interface': self.can_interface,
            'connected': self.is_connected(),
            'running': self.running,
            'bus_available': self.can_bus is not None,
            'stats': self.message_stats.copy()
        }
        
    def shutdown(self):
        """안전한 종료"""
        self.logger.info("🔧 Shutting down BMW CAN controller...")
        
        # 메시지 수신 중지
        self.stop_listening()
        
        # CAN 버스 종료
        if self.can_bus:
            try:
                self.can_bus.shutdown()
                self.logger.info("✅ CAN bus shutdown complete")
            except Exception as e:
                self.logger.error(f"❌ CAN bus shutdown error: {e}")
                
        self.can_bus = None
        self.logger.info("🏁 BMW CAN controller shutdown complete")

# BMW CAN 인터페이스 설정 유틸리티 (원본과 동일)
def setup_can_interface(interface: str = 'can0', bitrate: int = 500000) -> bool:
    """CAN 인터페이스 설정"""
    import subprocess
    
    try:
        print(f"🔧 Setting up CAN interface {interface}...")
        
        # CAN 인터페이스 다운
        subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'down'], 
                      check=False, capture_output=True)
        
        # CAN 인터페이스 구성
        result = subprocess.run([
            'sudo', 'ip', 'link', 'set', interface, 'up', 
            'type', 'can', 'bitrate', str(bitrate)
        ], check=True, capture_output=True, text=True)
        
        print(f"✅ CAN interface {interface} configured successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ CAN interface setup failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ CAN interface setup error: {e}")
        return False

# 모듈 테스트
if __name__ == "__main__":
    print("🧪 Testing BMW CAN controller...")
    
    logging.basicConfig(level=logging.INFO)
    
    # CAN 인터페이스 설정
    if not setup_can_interface('can0'):
        print("⚠️ CAN interface setup failed, using mock mode")
        
    # CAN 컨트롤러 초기화
    can_controller = BMWCANController('can0')
    
    # 콜백 함수 설정
    def on_gear_change(gear: str, manual_gear: int):
        print(f"🔧 Gear changed: {gear}" + (f"{manual_gear}" if gear == "M" else ""))
        
    def on_message_received(message):
        if message.arbitration_id == 0x12F:
            print(f"📨 BMW message: ID={message.arbitration_id:03X}, Data={message.data.hex()}")
            
    can_controller.on_gear_change = on_gear_change
    can_controller.on_message_received = on_message_received
    
    if can_controller.initialize():
        print("✅ CAN controller initialized successfully")
        
        # 메시지 수신 시작
        can_controller.start_listening()
        
        try:
            # 30초간 테스트
            print("🕐 Running test for 30 seconds...")
            for i in range(30):
                time.sleep(1)
                
                # 상태 정보 출력 (5초마다)
                if i % 5 == 0:
                    state = can_controller.get_gear_state()
                    conn_info = can_controller.get_connection_info()
                    
                    print(f"📊 Status: Gear={state['gear']}, "
                          f"Messages={state['message_count']}, "
                          f"Connected={conn_info['connected']}")
                          
        except KeyboardInterrupt:
            print("\n🛑 Test interrupted by user")
        finally:
            can_controller.shutdown()
            
    else:
        print("❌ CAN controller initialization failed")
        
    print("🏁 BMW CAN controller test completed")