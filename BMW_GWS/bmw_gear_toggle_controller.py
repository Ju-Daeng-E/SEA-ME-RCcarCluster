#!/usr/bin/env python3
"""
BMW F-Series Gear Lever Toggle Controller
토글 방식으로 작동하는 기어 레버 제어 시스템

Features:
- 기본 상태: 파킹 모드, 백라이트 최대 밝기
- 파킹 해제: 파킹 버튼 한 번 더 눌러서 해제
- 토글 방식 기어 전환: 레버를 위/아래로 움직였다가 돌아오면 기어 전환
- LED 제어: 각 기어 상태에 맞는 LED 표시
- 수동 기어: 토글 방식으로 업/다운 시프트
"""

import can
import time
import threading
import crccheck
from datetime import datetime
from enum import Enum

class GearState(Enum):
    PARK = "P"
    REVERSE = "R"
    NEUTRAL = "N"
    DRIVE = "D"
    SPORT = "S"
    MANUAL = "M"

class LeverPosition(Enum):
    CENTER = 0x0E      # Centre middle
    UP_ONE = 0x1E      # Pushed "up" (towards front of car)
    UP_TWO = 0x2E      # Pushed "up" two notches
    DOWN_ONE = 0x3E    # Pushed "down" (towards back of car)
    DOWN_TWO = 0x4E    # Pushed "down" two notches
    SIDE_CENTER = 0x7E # Centre side
    SIDE_UP = 0x5E     # Pushed "side and up"
    SIDE_DOWN = 0x6E   # Pushed "side and down"

class BMW3FDCRC(crccheck.crc.Crc8Base):
    """BMW 0x3FD 메시지용 CRC8 계산"""
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x70

class BMW197CRC(crccheck.crc.Crc8Base):
    """BMW 0x197 메시지용 CRC8 계산"""
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x53

def bmw_3fd_crc(message):
    return BMW3FDCRC.calc(message) & 0xFF

def bmw_197_crc(message):
    return BMW197CRC.calc(message) & 0xFF

class BMWToggleGearController:
    def __init__(self):
        """BMW 기어 레버 토글 컨트롤러 초기화"""
        try:
            self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("✅ CAN bus connected successfully")
        except Exception as e:
            self.bus = None
            print(f"⚠️  CAN bus connection failed: {e}")
            print("🔧 Running in simulation mode")
        
        # 시스템 상태
        self.running = True
        self.current_gear = GearState.PARK  # 기본값: 파킹 모드
        self.park_locked = True             # 파킹 잠금 상태
        self.manual_gear_level = 1          # 수동 기어 단수 (1-8)
        
        # 레버 상태 추적
        self.current_lever_position = LeverPosition.CENTER
        self.previous_lever_position = LeverPosition.CENTER
        self.lever_returned_to_center = True
        
        # 버튼 상태
        self.park_button_pressed = False
        self.unlock_button_pressed = False
        self.last_park_button_time = 0
        
        # 타이밍 제어
        self.toggle_timeout = 0.5          # 토글 동작 간격 (500ms)
        self.last_toggle_time = 0
        self.debounce_time = 0.1           # 버튼 디바운스 시간
        
        # 메시지 카운터
        self.gws_counter = 0x01
        self.message_count = 0
        
        # LED 매핑 (BMW 스펙에 따라 정확한 코드 사용)
        self.gear_led_codes = {
            GearState.PARK: 0x20,     # P
            GearState.REVERSE: 0x40,  # R
            GearState.NEUTRAL: 0x60,  # N
            GearState.DRIVE: 0x80,    # D
            GearState.SPORT: 0x81,    # D, can move to M/S
            GearState.MANUAL: 0x81    # M/S (if lever moved to side)
        }
        
        # 시작 시 초기화
        self.initialize_system()
        
        print("\n📋 BMW Lever Position Codes:")
        print("0x0E: Centre middle")
        print("0x1E: Pushed 'up' (towards front)")
        print("0x2E: Pushed 'up' two notches")
        print("0x3E: Pushed 'down' (towards back)")
        print("0x4E: Pushed 'down' two notches")
        print("0x7E: Centre side")
        print("0x5E: Pushed 'side and up'")
        print("0x6E: Pushed 'side and down'")
        print("\n💡 LED Display Codes:")
        print("0x20: P, 0x40: R, 0x60: N, 0x80: D, 0x81: D/M/S")
        
    def initialize_system(self):
        """시스템 초기화: 백라이트 최대, 파킹 모드 LED"""
        print("🔧 Initializing BMW Gear Controller...")
        print("💡 Setting backlight to maximum brightness")
        print("🅿️  Default mode: PARK (locked)")
        
        # 백라이트 최대 밝기 설정
        self.set_backlight_max()
        
        # 파킹 모드 LED 설정 (지속적으로 켜져 있음)
        self.update_gear_led()
        
        # 모니터링 및 제어 스레드 시작
        self.start_monitoring()
        self.start_led_control()
        
        print("✅ System initialized successfully")
        print("💡 LEDs remain steady (no periodic updates to prevent flashing)")
    
    def set_backlight_max(self):
        """백라이트를 최대 밝기로 설정"""
        if not self.bus:
            return
        
        try:
            msg = can.Message(
                arbitration_id=0x202,
                data=[0xFF, 0x00],  # 최대 밝기 (255)
                is_extended_id=False
            )
            self.bus.send(msg)
            print("💡 Backlight set to maximum (255/255)")
        except Exception as e:
            print(f"❌ Failed to set backlight: {e}")
    
    def update_gear_led(self):
        """현재 기어 상태에 맞는 LED 업데이트"""
        if not self.bus:
            return
        
        try:
            # BMW 스팩에 따른 정확한 LED 코드 사용 (깜빡임 없음)
            if self.current_gear == GearState.MANUAL:
                led_code = self.gear_led_codes[GearState.MANUAL]  # 0x81 (M/S)
                gear_display = f"M{self.manual_gear_level}"
            elif self.current_gear == GearState.SPORT:
                led_code = self.gear_led_codes[GearState.SPORT]   # 0x81 (D, can move to M/S)
                gear_display = "S"
            else:
                led_code = self.gear_led_codes[self.current_gear]
                gear_display = self.current_gear.value
            
            # 깜빡임 제거: 0x08 플래그를 추가하지 않음 (지속적으로 켜져 있음)
            
            # GWS 메시지 생성 (0x3FD)
            self.gws_counter = (self.gws_counter + 1) if self.gws_counter < 0x0E else 0x01
            payload_without_crc = [self.gws_counter, led_code, 0x00, 0x00]
            crc = bmw_3fd_crc(payload_without_crc)
            payload = [crc] + payload_without_crc
            
            message = can.Message(
                arbitration_id=0x3FD,
                data=payload,
                is_extended_id=False
            )
            
            self.bus.send(message)
            print(f"💡 LED SET for gear: {gear_display} (code: 0x{led_code:02X}, steady)")
            
        except Exception as e:
            print(f"❌ LED update failed: {e}")
    
    def handle_park_button_toggle(self):
        """파킹 버튼 토글 처리 - 파킹 잠금/해제"""
        current_time = time.time()
        
        # 디바운스 처리
        if current_time - self.last_park_button_time < self.debounce_time:
            return
        
        self.last_park_button_time = current_time
        
        if self.park_locked:
            # 파킹 해제 → 중립으로 전환
            self.park_locked = False
            self.current_gear = GearState.NEUTRAL
            print("🔓 Park UNLOCKED → Neutral mode")
        else:
            # 파킹 잠금
            self.park_locked = True
            self.current_gear = GearState.PARK
            print("🔒 Park LOCKED")
        
        self.update_gear_led()
        self.display_status()
    
    def handle_lever_toggle(self, lever_pos):
        """레버 토글 동작 처리"""
        current_time = time.time()
        
        # 토글 타임아웃 체크
        if current_time - self.last_toggle_time < self.toggle_timeout:
            return
        
        # 파킹 모드에서는 레버 동작 무시
        if self.park_locked:
            print("🔒 Park locked - lever movement ignored")
            return
        
        # 레버가 중앙으로 돌아왔을 때만 토글 동작 수행
        if (self.previous_lever_position != LeverPosition.CENTER and 
            lever_pos == LeverPosition.CENTER and 
            self.lever_returned_to_center):
            
            self.process_gear_change()
            self.last_toggle_time = current_time
    
    def process_gear_change(self):
        """이전 레버 위치에 따른 기어 변경 처리"""
        if self.previous_lever_position == LeverPosition.UP_ONE:
            # 위로 한 번 올렸다가 돌아옴
            if self.current_gear == GearState.NEUTRAL:
                self.current_gear = GearState.REVERSE
                print("🔄 Toggle UP → REVERSE")
            elif self.current_gear == GearState.DRIVE:
                self.current_gear = GearState.NEUTRAL
                print("🔄 Toggle UP → NEUTRAL (from DRIVE)")
            elif self.current_gear == GearState.REVERSE:
                self.current_gear = GearState.NEUTRAL
                print("🔄 Toggle UP → NEUTRAL (from REVERSE)")
                
        elif self.previous_lever_position == LeverPosition.DOWN_ONE:
            # 아래로 한 번 내렸다가 돌아옴
            if self.current_gear == GearState.NEUTRAL:
                self.current_gear = GearState.DRIVE
                print("🔄 Toggle DOWN → DRIVE")
            elif self.current_gear == GearState.REVERSE:
                self.current_gear = GearState.NEUTRAL
                print("🔄 Toggle DOWN → NEUTRAL (from REVERSE)")
                
        elif self.previous_lever_position == LeverPosition.SIDE_CENTER:
            # 사이드 중앙으로 밀었다가 돌아옴 → Manual/Sport 토글
            if self.current_gear == GearState.DRIVE:
                self.current_gear = GearState.SPORT
                print("🔄 Toggle SIDE → SPORT")
            elif self.current_gear == GearState.SPORT:
                self.current_gear = GearState.MANUAL
                self.manual_gear_level = 1
                print("🔄 Toggle SIDE → MANUAL M1")
            elif self.current_gear == GearState.MANUAL:
                self.current_gear = GearState.DRIVE
                print("🔄 Toggle SIDE → DRIVE")
            else:
                # 다른 기어에서 사이드로 이동하면 스포츠 모드
                self.current_gear = GearState.SPORT
                print("🔄 Toggle SIDE → SPORT")
        
        self.update_gear_led()
        self.display_status()
    
    def handle_manual_gear_toggle(self, lever_pos):
        """수동 기어 모드에서의 토글 처리"""
        if self.current_gear not in [GearState.MANUAL, GearState.SPORT]:
            return
        
        current_time = time.time()
        
        # 토글 타임아웃 체크
        if current_time - self.last_toggle_time < self.toggle_timeout:
            return
        
        if lever_pos == LeverPosition.SIDE_UP:
            # 사이드에서 위로 올렸다가 떼면 → 고단 (업시프트)
            if self.current_gear == GearState.MANUAL and self.manual_gear_level < 8:
                self.previous_lever_position = LeverPosition.SIDE_UP
            elif self.current_gear == GearState.SPORT:
                # 스포츠 모드에서는 Manual 모드로 전환
                self.current_gear = GearState.MANUAL
                self.manual_gear_level = 1
                print("🔄 Sport → Manual M1")
                self.update_gear_led()
                self.display_status()
                
        elif lever_pos == LeverPosition.SIDE_DOWN:
            # 사이드에서 아래로 내렸다가 떼면 → 저단 (다운시프트)
            if self.current_gear == GearState.MANUAL and self.manual_gear_level > 1:
                self.previous_lever_position = LeverPosition.SIDE_DOWN
            elif self.current_gear == GearState.SPORT:
                # 스포츠 모드에서는 Manual 모드로 전환
                self.current_gear = GearState.MANUAL
                self.manual_gear_level = 1
                print("🔄 Sport → Manual M1")
                self.update_gear_led()
                self.display_status()
                
        elif (lever_pos == LeverPosition.SIDE_CENTER and 
              self.previous_lever_position in [LeverPosition.SIDE_UP, LeverPosition.SIDE_DOWN]):
            # 레버가 사이드 중앙으로 돌아옴 → 실제 기어 변경
            if self.previous_lever_position == LeverPosition.SIDE_UP and self.current_gear == GearState.MANUAL:
                # 상한선 검사: 8단 초과 방지
                if self.manual_gear_level < 8:
                    self.manual_gear_level += 1
                    print(f"🔼 Manual UP → M{self.manual_gear_level}")
                    self.last_toggle_time = current_time
                    self.update_gear_led()
                    self.display_status()
                else:
                    print("⚠️  Already at maximum gear M8")
            elif self.previous_lever_position == LeverPosition.SIDE_DOWN and self.current_gear == GearState.MANUAL:
                # 하한선 검사: 1단 미만 방지
                if self.manual_gear_level > 1:
                    self.manual_gear_level -= 1
                    print(f"🔽 Manual DOWN → M{self.manual_gear_level}")
                    self.last_toggle_time = current_time
                    self.update_gear_led()
                    self.display_status()
                else:
                    print("⚠️  Already at minimum gear M1")
    
    def decode_can_message(self, msg):
        """CAN 메시지 디코딩 및 처리"""
        self.message_count += 1
        
        if msg.arbitration_id == 0x197:
            # 레버 상태 메시지
            if len(msg.data) >= 4:
                crc = msg.data[0]
                counter = msg.data[1] & 0x0F
                lever_pos_raw = msg.data[2]
                button_state = msg.data[3]
                
                # 레버 위치 매핑
                try:
                    lever_pos = LeverPosition(lever_pos_raw)
                    self.previous_lever_position = self.current_lever_position
                    self.current_lever_position = lever_pos
                    
                    # 레버가 중앙으로 돌아왔는지 체크
                    if lever_pos == LeverPosition.CENTER:
                        self.lever_returned_to_center = True
                    else:
                        self.lever_returned_to_center = False
                    
                    # 버튼 상태 처리
                    park_btn = (button_state & 0x01) != 0
                    unlock_btn = (button_state & 0x02) != 0
                    
                    # 파킹 버튼 토글 처리
                    if park_btn and not self.park_button_pressed:
                        self.handle_park_button_toggle()
                    
                    self.park_button_pressed = park_btn
                    self.unlock_button_pressed = unlock_btn
                    
                    # 레버 토글 처리
                    if self.current_gear in [GearState.MANUAL, GearState.SPORT]:
                        self.handle_manual_gear_toggle(lever_pos)
                    else:
                        self.handle_lever_toggle(lever_pos)
                        
                except ValueError:
                    # 알려지지 않은 레버 위치
                    print(f"🔍 Unknown lever position: 0x{lever_pos_raw:02X}")
        
        elif msg.arbitration_id == 0x55e:
            # 하트비트 메시지
            pass
        
        elif msg.arbitration_id == 0x3FD:
            # 기어 디스플레이 메시지 (송신한 메시지의 에코일 수 있음)
            pass
        
        elif msg.arbitration_id == 0x202:
            # 백라이트 메시지
            pass
    
    def start_monitoring(self):
        """CAN 메시지 모니터링 시작"""
        if not self.bus:
            print("⚠️  CAN monitoring disabled (simulation mode)")
            return
        
        def monitor_loop():
            print("🎯 Starting CAN message monitoring...")
            
            while self.running:
                try:
                    msg = self.bus.recv(timeout=1.0)
                    if msg:
                        self.decode_can_message(msg)
                except Exception as e:
                    if self.running:
                        print(f"❌ CAN monitoring error: {e}")
                        time.sleep(0.1)
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
    
    def start_led_control(self):
        """LED 및 백라이트 제어 스레드 시작 - 깜빡임 방지"""
        def led_control_loop():
            counter = 0
            while self.running:
                # 백라이트만 주기적으로 유지 (5초마다)
                if counter % 50 == 0:
                    self.set_backlight_max()
                
                # LED 주기적 업데이트 제거 (깜빡임 방지)
                # 기어 변경시에만 update_gear_led() 호출
                # if counter % 10 == 0:
                #     self.update_gear_led()  # 비활성화
                
                counter += 1
                time.sleep(0.1)
        
        if self.bus:
            thread = threading.Thread(target=led_control_loop, daemon=True)
            thread.start()
            print("💡 LED control thread started (no periodic LED updates)")
    
    def display_status(self):
        """현재 상태 표시"""
        print("\n" + "="*60)
        print("🚗 BMW F-Series Toggle Gear Controller")
        print("="*60)
        
        # 현재 기어 상태
        if self.current_gear == GearState.MANUAL:
            gear_display = f"M{self.manual_gear_level}"
        else:
            gear_display = self.current_gear.value
        
        print(f"Current Gear: [{gear_display}]")
        print(f"Park Status: {'🔒 LOCKED' if self.park_locked else '🔓 UNLOCKED'}")
        print(f"Lever Position: {self.current_lever_position.name}")
        print(f"Messages Received: {self.message_count}")
        print(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        
        print("\n📋 Toggle Controls:")
        print("🅿️  Park Button: Toggle lock/unlock")
        print("⬆️  UP → Center: N ↔ R toggle, D → N")
        print("⬇️  DOWN → Center: N ↔ D toggle, R → N")
        print("➡️  SIDE → Center: D ↔ Sport ↔ Manual toggle")
        print("📶 Manual Mode: SIDE UP/DOWN → SIDE CENTER for gear shift")
        
        print("="*60)
    
    def run(self):
        """메인 실행 루프"""
        print("🚀 BMW Toggle Gear Controller Started")
        self.display_status()
        
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """시스템 종료"""
        print("\n🛑 Shutting down BMW Toggle Gear Controller...")
        self.running = False
        
        if self.bus:
            # 시스템 종료 전 파킹 모드로 전환
            self.current_gear = GearState.PARK
            self.park_locked = True
            self.update_gear_led()
            time.sleep(0.1)
            self.bus.shutdown()
        
        print("👋 Controller stopped safely")

if __name__ == "__main__":
    controller = BMWToggleGearController()
    controller.run()