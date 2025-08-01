import can
import time
import threading
import crccheck
from datetime import datetime

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

class BMWGearLeverMonitor:
    def __init__(self):
        try:
            self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("✓ CAN bus connected")
        except Exception as e:
            self.bus = None
            print(f"⚠  CAN bus not available: {e}")
            return
        
        self.running = True
        self.current_gear = 'Unknown'
        self.current_lever_pos = 'Unknown'
        self.park_button = 'Released'
        self.unlock_button = 'Released'
        self.last_update = None
        
        
        # 레버 위치 매핑 (0x197 메시지의 byte 2) - BMW F-Series 위키 기준
        self.lever_position_map = {
            0x0E: 'Center',
            0x1E: 'Up (R)', 
            0x2E: 'Up+ (Beyond R)',
            0x3E: 'Down (D)',
            0x7E: 'Side (S)',
            0x5E: 'Manual Down (-)',
            0x6E: 'Manual Up (+)'
        }
        
        # 기어 코드 역매핑 (0x3FD 메시지에서 추정)
        self.gear_code_map = {
            0x20: 'P',
            0x40: 'R',
            0x60: 'N', 
            0x80: 'D'
        }
        
        self.message_count = 0
        self.manual_gear = 1  # 수동 기어 단수
        self.last_manual_position = None  # 마지막 수동 레버 위치
        self.last_manual_time = 0  # 마지막 수동 기어 조작 시간
        self.manual_timeout = 0.3  # 300ms 간격으로 기어 변경 허용
        self.gws_counter = 0x01  # GWS 메시지 카운터 (0x01-0x0E)
        
        # 토글 방식으로 레버 상태 추적
        self.current_lever_position = 0x0E  # 현재 레버 위치
        self.previous_lever_position = 0x0E  # 이전 레버 위치
        self.lever_returned_to_center = True  # 레버가 중앙으로 돌아왔는지
        self.lever_returned_to_Manual_center = True  # 레버가 중앙으로 돌아왔는지
        self.toggle_timeout = 0.5  # 토글 동작 간격
        self.last_toggle_time = 0  # 마지막 토글 시간
        
        # LED 제어를 위한 백라이트 및 기어 디스플레이 전송
        self.start_led_control()
        self.start_monitoring()
    
    def clear_screen(self):
        print("\033[2J\033[H", end="")
    
    def display_status(self):
        self.clear_screen()
        print("="*60)
        print("🚗 BMW F-Series Gear Lever Monitor")
        print("="*60)
        print(f"Current Gear Position: [{self.current_gear}]")
        print(f"Lever Position: {self.current_lever_pos}")
        
        # 기어 상태별 시각적 표시
        if self.current_gear == 'R':
            print(f"🚗 REVERSE GEAR ACTIVE - 후진 기어 활성!")
        elif self.current_gear == 'D':
            print(f"🚗 DRIVE GEAR ACTIVE - 전진 기어 활성!")
        elif self.current_gear == 'N':
            print(f"🚗 NEUTRAL GEAR - 중립 상태")
        elif self.current_gear == 'P':
            print(f"🅿️  PARK MODE - 주차 모드")
        print(f"Park Button: {self.park_button}")
        print(f"Unlock Button: {self.unlock_button}")
        if self.current_gear.startswith('M'):
            print(f"Manual Gear: {self.manual_gear}단")
            print(f"Last Manual Position: {hex(self.last_manual_position) if self.last_manual_position else 'None'}")
        print(f"Last Update: {self.last_update if self.last_update else 'Never'}")
        print(f"Messages Received: {self.message_count}")
        print(f"CAN Status: {'✓ Connected' if self.bus else '✗ Disconnected'}")
        print("="*60)
        print("💡 Move the gear lever to see position changes")
        print("🔓 To exit Park: Press unlock button + move lever")
        print("⚙️  Manual gear: 500ms timeout to prevent rapid changes")
        print("Press Ctrl+C to exit")
        print("="*60)
    
    def decode_lever_message(self, msg):
        """0x197 메시지 디코딩 - 실제 레버 위치"""
        if len(msg.data) >= 4:
            crc = msg.data[0]
            counter = msg.data[1]  # 전체 카운터 값 (0x0F 마스크 제거)
            lever_pos = msg.data[2]
            park_btn = msg.data[3]
            
            # 🔍 REAL-TIME CAN MESSAGE DEBUGGING
            print(f"🔍 RAW CAN: [0x{crc:02X}, 0x{counter:02X}, 0x{lever_pos:02X}, 0x{park_btn:02X}]")
            print(f"🔍 LEVER_POS: 0x{lever_pos:02X} = {lever_pos} (decimal)")
            print(f"🔍 PARK_BTN: 0x{park_btn:02X} (park={park_btn&0x01}, unlock={park_btn&0x02})")
            print(f"🔍 COUNTER: 0x{counter:02X} = {counter} (decimal)")
            
            # CRC 검증 (BMW 197 CRC 체크)
            payload_for_crc = [counter, lever_pos, park_btn]
            expected_crc = bmw_197_crc(payload_for_crc)
            crc_valid = (crc == expected_crc)
            print(f"🔍 CRC: 계산값=0x{expected_crc:02X}, 실제값=0x{crc:02X}, 유효={crc_valid}")

            # 레버 위치 매핑 업데이트 (핵심 수정!)
            if lever_pos in self.lever_position_map:
                self.current_lever_pos = self.lever_position_map[lever_pos]
                print(f"✅ 레버 위치 매핑: 0x{lever_pos:02X} → {self.current_lever_pos}")
            else:
                self.current_lever_pos = f'Unknown (0x{lever_pos:02X})'
                print(f"⚠️  알려지지 않은 레버 위치: 0x{lever_pos:02X}")
            
            # 파크 버튼과 언락 버튼 상태 (byte 3 분석)
            self.park_button = 'Pressed' if (park_btn & 0x01) != 0 else 'Released'
            self.unlock_button = 'Pressed' if (park_btn & 0x02) != 0 else 'Released'
            
            # 현재 시간
            current_time = time.time()
            
            # 토글 방식 기어 전환 로직 - 레버를 올렸다가 떼면 기어 전환
            
            # 레버 위치 추적 업데이트
            self.previous_lever_position = self.current_lever_position
            self.current_lever_position = lever_pos
            
            # 토글 동작 처리
            self.handle_toggle_action(lever_pos, park_btn)
            # 수동 기어 모드는 handle_toggle_action에서 처리
            # 알려지지 않은 레버 위치는 매핑에만 추가하고 기어 상태 유지
            
            self.last_update = datetime.now().strftime("%H:%M:%S")
            return True
        return False
    
    def handle_toggle_action(self, lever_pos, park_btn):
        """토글 방식 기어 전환 처리"""
        current_time = time.time()
        unlock_pressed = (park_btn & 0x02) != 0
        
        # unlock 버튼 처리 - P모드 해제 전용
        if unlock_pressed:
            if self.current_gear == 'P' and lever_pos == 0x0E:
                self.current_gear = 'N'
                print(f"🔓 Unlock Button: PARK 잠금해제 → NEUTRAL mode")
                return
            else:
                print(f"🔒 Unlock Button: P모드가 아니므로 무시됨 (현재: {self.current_gear})")
                return
        
        # 파크 버튼 처리
        if (park_btn & 0x01) != 0:  # 파크 버튼 눌림
            if lever_pos == 0x0E:  # 센터 + 파크 버튼
                self.current_gear = 'P'
                print(f"🅿️  Park Button → PARK mode")
                return
        
        # 토글 타임아웃 체크
        if current_time - self.last_toggle_time < self.toggle_timeout:
            return
        
        # 레버가 중앙으로 돌아왔을 때 토글 전환 수행
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
        """이전 레버 위치에 따른 토글 전환 처리"""
        if self.previous_lever_position == 0x1E:  # UP → CENTER
            self.handle_up_toggle()
        elif self.previous_lever_position == 0x2E:  # UP+ → CENTER
            self.current_gear = 'P'
            print(f"🎯 UP+ Toggle → PARK mode")
        elif self.previous_lever_position == 0x3E:  # DOWN → CENTER
            self.handle_down_toggle()
        elif self.previous_lever_position == 0x4E:  # DOWN+ → CENTER
            print(f"🎯 DOWN+ Toggle → Nothing")
        elif self.previous_lever_position == 0x7E:  # SIDE → CENTER
            self.handle_side_toggle()
                
            
    def process_toggle_Manual_transition(self):   
        # if self.previous_lever_position == 0x7E:  # SIDE → CENTER
        #     self.handle_side_toggle()
        if self.previous_lever_position == 0x5E:  # Manual Down → CENTER
            self.handle_manual_down_toggle()
        elif self.previous_lever_position == 0x6E:  # Manual Up → CENTER
            self.handle_manual_up_toggle()
        elif self.previous_lever_position == 0x0E:  # Manual Center → Side
             self.handle_side_toggle()
                
    
    def handle_up_toggle(self):
        """위로 올렸다가 떼 때 처리"""
        if self.current_gear == 'N':
            self.current_gear = 'R'
            print(f"🎯 N에서 UP Toggle → REVERSE mode")
        elif self.current_gear == 'D':
            self.current_gear = 'N'
            print(f"🎯 D에서 UP Toggle → NEUTRAL mode")
        elif self.current_gear == 'R':
            #self.current_gear = 'P'
            print(f"🎯 R에서 UP Toggle → Nothing")
        elif self.current_gear == 'P':
            self.current_gear == 'N'
            print(f"🔒 P모드에서 UP Toggle -> N")
        else:
            self.current_gear = 'N'
            print(f"🎯 UP Toggle → NEUTRAL mode (default)")
    
    def handle_down_toggle(self):
        """아래로 내렸다가 떼 때 처리"""
        if self.current_gear == 'N':
            self.current_gear = 'D'
            print(f"🎯 N에서 DOWN Toggle → DRIVE mode")
        elif self.current_gear == 'R':
            self.current_gear = 'N'
            print(f"🎯 R에서 DOWN Toggle → NEUTRAL mode")
        elif self.current_gear == 'P':
            self.current_gear = 'N'
            print(f"🎯 R에서 DOWN Toggle → NEUTRAL mode")
        elif self.current_gear == 'D':
            print(f"🎯 D에서 DOWN Toggle → Nothing")
        else:
            self.current_gear = 'D'
            print(f"🎯 DOWN Toggle → DRIVE mode (default)")
    
    def handle_side_toggle(self):
        """사이드로 밀었다가 떼 때 처리"""
        # if self.current_gear == 'D':
        #     self.current_gear = 'S'
        #     print(f"🎯 D에서 SIDE Toggle → SPORT mode")
        if self.current_gear == 'D':
            # S모드에서 매뉴얼로 갈 때 1단으로 초기화
            self.manual_gear = 1
            self.current_gear = f'M{self.manual_gear}'
            print(f"🎯 S에서 SIDE Toggle → MANUAL M{self.manual_gear}")
        elif self.current_gear.startswith('M'):
            self.current_gear = 'D'
            print(f"🎯 Manual에서 SIDE Toggle → DRIVE mode")
        else:
            self.current_gear = 'D'
            print(f"🎯 SIDE Toggle → SPORT mode (default)")
    
    def handle_manual_up_toggle(self):
        """수동 모드에서 위로 올렸다가 뗜 때"""
        if self.current_gear.startswith('M') and self.manual_gear < 8:
            self.manual_gear += 1
            self.current_gear = f'M{self.manual_gear}'
            print(f"🔼 Manual UP Toggle → M{self.manual_gear}")
        else:
            print("⚠️  Manual UP: Already at max or not in manual mode")
    
    def handle_manual_down_toggle(self):
        """수동 모드에서 아래로 내렸다가 뗜 때"""
        if self.current_gear.startswith('M') and self.manual_gear > 1:
            self.manual_gear -= 1
            self.current_gear = f'M{self.manual_gear}'
            print(f"🔽 Manual DOWN Toggle → M{self.manual_gear}")
        else:
            print("⚠️  Manual DOWN: Already at min or not in manual mode")
    
    def decode_gear_display_message(self, msg):
        """0x3FD 메시지 디코딩 - 기어 디스플레이 상태"""
        if len(msg.data) >= 4:
            crc = msg.data[0]
            counter = msg.data[1]
            gear_code = msg.data[2]
            
            # CRC 검증 (선택사항)
            payload = msg.data[1:]
            expected_crc = bmw_3fd_crc(payload)
            crc_valid = (crc == expected_crc)
            
            # 기어 코드 디코딩
            if gear_code in self.gear_code_map:
                display_gear = self.gear_code_map[gear_code]
                # 디스플레이 기어와 실제 기어가 다를 수 있음
                print(f"📺 Display shows: {display_gear} (CRC: {'✓' if crc_valid else '✗'})")
            
            return True
        return False
    
    def message_handler(self, msg):
        """CAN 메시지 핸들러"""
        self.message_count += 1
        
        if msg.arbitration_id == 0x197:
            # 레버 상태 메시지
            print(f"📥 0x197 메시지 수신! (lever_pos=0x{msg.data[2]:02X})")
            if self.decode_lever_message(msg):
                self.display_status()
                # 기어 변경시 즉시 LED 업데이트 (한 번만)
                if self.current_gear != 'Unknown':
                    print(f"💡 기어 '{self.current_gear}' LED 전송!")
                    # LED 지속 켜짐 (깜빡임 없이)
                    self.send_gear_led(self.current_gear, flash=False)
        
        elif msg.arbitration_id == 0x3FD:
            # 기어 디스플레이 메시지
            self.decode_gear_display_message(msg)
        
        elif msg.arbitration_id == 0x55e:
            # 하트비트 메시지
            print(f"💓 Heartbeat received at {datetime.now().strftime('%H:%M:%S')}")
        
        elif msg.arbitration_id == 0x202:
            # 백라이트 메시지
            if len(msg.data) >= 2:
                brightness = msg.data[0]
                print(f"💡 Backlight: {brightness}/255 ({brightness/255*100:.1f}%)")
        
        elif msg.arbitration_id == 0x65e:
            # 진단 에러 메시지
            print(f"⚠️  Diagnostic message: {msg.data.hex()}")
    
    def start_monitoring(self):
        """CAN 메시지 모니터링 시작"""
        if not self.bus:
            print("❌ Cannot start monitoring - CAN bus not available")
            return
        
        def monitor_loop():
            print("🎯 Starting CAN message monitoring...")
            self.display_status()
            
            while self.running:
                try:
                    # CAN 메시지 수신 (타임아웃 1초)
                    msg = self.bus.recv(timeout=1.0)
                    if msg:
                        self.message_handler(msg)
                except Exception as e:
                    if self.running:  # 정상 종료가 아닌 경우만 에러 출력
                        print(f"❌ Error receiving message: {e}")
                        time.sleep(0.1)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def send_gear_led(self, gear, flash=False):
        """기어 변경시 LED 표시 (BMW F-Series GWS 올바른 구조)"""
        if not self.bus:
            return
        
        # 기어별 LED 코드
        gear_led_codes = {
            'P': 0x20,
            'R': 0x40,
            'N': 0x60,
            'D': 0x80,
            'S': 0x81,  # Sport mode는 M/S 가능한 LED
        }
        
        # 수동 기어는 M/S 가능한 D LED 사용 (0x81)
        if gear.startswith('M'):
            led_code = 0x81
        elif gear in gear_led_codes:
            led_code = gear_led_codes[gear]
        else:
            return
        
        # 깜빡임 기능: +0x08
        if flash:
            led_code |= 0x08
        
        try:
            # BMW F-Series GWS 올바른 메시지 구조
            # Byte 0: CRC8, Byte 1: Counter, Byte 2: LED Code, Byte 3-4: 0x00
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
            print(f"💡 LED sent for gear {gear} (code: 0x{led_code:02X}, counter: 0x{self.gws_counter:02X})")
        except Exception as e:
            print(f"❌ LED control error: {e}")
    
    def send_gear_led_continuous(self, gear, flash=False):
        """기어 LED 지속적 전송 (BMW F-Series GWS 올바른 구조) - 깜빡임 없이"""
        if not self.bus:
            return
        
        # 기어별 LED 코드
        gear_led_codes = {
            'P': 0x20,
            'R': 0x40,
            'N': 0x60,
            'D': 0x80,
            'S': 0x81,  # Sport mode는 M/S 가능한 LED
        }
        
        # 수동 기어는 M/S 가능한 D LED 사용 (0x81)
        if gear.startswith('M'):
            led_code = 0x81
        elif gear in gear_led_codes:
            led_code = gear_led_codes[gear]
        else:
            return
        
        # 깜빡임 기능 비활성화 - 지속적으로 켜짐
        # if flash:
        #     led_code |= 0x08
        
        try:
            # BMW F-Series GWS 올바른 메시지 구조  
            # Byte 0: CRC8, Byte 1: Counter, Byte 2: LED Code, Byte 3-4: 0x00
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
        except Exception as e:
            pass  # 에러 메시지 없이 조용히 실패
    
    def send_backlight(self):
        """백라이트 제어"""
        if not self.bus:
            return
        
        try:
            msg = can.Message(
                arbitration_id=0x202,
                data=[0xFF, 0x00],  # 최대 밝기
                is_extended_id=False
            )
            self.bus.send(msg)
        except Exception as e:
            pass
    
    def start_led_control(self):
        """LED 및 백라이트 제어 스레드 시작"""
        def led_control_loop():
            last_gear = None
            while self.running:
                # 백라이트 지속적 전송
                self.send_backlight()
                
                # 현재 기어 LED 지속적 전송 (LED 꼭 켜두기)
                if self.current_gear != 'Unknown':
                    self.send_gear_led_continuous(self.current_gear, flash=False)
                
                time.sleep(0.1)  # 100ms마다
        
        if self.bus:
            led_thread = threading.Thread(target=led_control_loop, daemon=True)
            led_thread.start()
            print("💡 LED control started")
    
    def run(self):
        """메인 실행 루프"""
        if not self.bus:
            print("❌ Cannot run - CAN bus not available")
            return
        
        print("🚀 BMW Gear Lever Monitor Started")
        print("Move the gear lever to see position changes...")
        print("\n📋 BMW Gear Lever Guide:")
        print("• P (Park): Center + Park button OR R에서 더 위로")
        print("• R (Reverse): N상태에서 UP 토글 (UP→CENTER)")
        print("• Toggle Mode: 레버를 올렸다가 뗼면 기어 전환")
        print("• Manual Mode: SIDE에서 UP/DOWN 토글로 기어 전환")
        print("• N (Neutral): Center position (Park button released)")
        print("• D (Drive): Down position")
        print("• S (Sport): Side position")
        print("• M1-M8 (Manual): Side에서 +/- 조작 (중복 방지: 500ms)")
        print("• 🔓 Unlock button: 기어 잠금 해제\n")
        
        try:
            while self.running:
                time.sleep(0.1)  # CPU 사용량 줄이기
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """프로그램 종료"""
        print("\n🛑 Shutting down...")
        self.running = False
        if self.bus:
            self.bus.shutdown()
        print("👋 Goodbye!")

if __name__ == "__main__":
    monitor = BMWGearLeverMonitor()
    monitor.run()