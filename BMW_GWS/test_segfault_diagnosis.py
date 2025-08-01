#!/usr/bin/env python3
"""
Segmentation Fault 진단 도구
실제 움직임 제어 시 발생하는 segfault 원인 분석
"""

import sys
import time
import signal
import traceback
import RPi.GPIO as GPIO
from piracer.vehicles import PiRacerStandard
from piracer.gamepads import ShanWanGamepad

class SegfaultDiagnostics:
    def __init__(self):
        self.piracer = None
        self.gamepad = None
        self.test_results = {}
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGSEGV, self.segfault_handler)
        signal.signal(signal.SIGABRT, self.abort_handler)
        
    def segfault_handler(self, sig, frame):
        """Segmentation fault 핸들러"""
        print("\n🚨 SEGMENTATION FAULT DETECTED!")
        print("Stack trace:")
        traceback.print_stack(frame)
        
        # 현재 상태 출력
        print(f"Signal: {sig}")
        print(f"Frame: {frame}")
        
        # 안전 정지
        try:
            if self.piracer:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
        except:
            pass
            
        GPIO.cleanup()
        sys.exit(1)
        
    def abort_handler(self, sig, frame):
        """Abort 시그널 핸들러"""
        print("\n🚨 ABORT SIGNAL DETECTED!")
        traceback.print_stack(frame)
        sys.exit(1)
        
    def test_1_basic_initialization(self):
        """기본 초기화 테스트"""
        print("🔍 Test 1: Basic Initialization")
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(18, GPIO.IN)
            
            self.piracer = PiRacerStandard()
            print("✅ PiRacer initialized")
            
            self.gamepad = ShanWanGamepad()
            print("✅ Gamepad initialized")
            
            self.test_results['init'] = True
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            self.test_results['init'] = False
            return False
            
    def test_2_static_control(self):
        """정적 제어 테스트 (움직임 없음)"""
        print("\n🔍 Test 2: Static Control (No Movement)")
        try:
            # 0% 스로틀로 여러 번 설정
            for i in range(10):
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
                time.sleep(0.1)
                print(f"  Static test {i+1}/10: OK")
                
            self.test_results['static'] = True
            return True
            
        except Exception as e:
            print(f"❌ Static control failed: {e}")
            self.test_results['static'] = False
            return False
            
    def test_3_minimal_movement(self):
        """최소 움직임 테스트"""
        print("\n🔍 Test 3: Minimal Movement")
        try:
            # 매우 작은 스로틀 값으로 테스트
            throttle_values = [0.01, 0.02, 0.05, 0.1]
            
            for throttle in throttle_values:
                print(f"  Testing throttle: {throttle}")
                
                # 앞으로 이동
                self.piracer.set_throttle_percent(throttle)
                time.sleep(0.5)  # 0.5초간 유지
                
                # 정지
                self.piracer.set_throttle_percent(0.0)
                time.sleep(0.5)  # 0.5초간 정지
                
                print(f"  ✅ Throttle {throttle} completed")
                
            self.test_results['minimal_movement'] = True
            return True
            
        except Exception as e:
            print(f"❌ Minimal movement failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['minimal_movement'] = False
            return False
            
    def test_4_gamepad_input(self):
        """게임패드 입력 테스트"""
        print("\n🔍 Test 4: Gamepad Input")
        try:
            for i in range(20):  # 2초간 테스트
                data = self.gamepad.read_data()
                
                if data:
                    throttle = data.analog_stick_right.y * 0.1  # 10%로 제한
                    steering = data.analog_stick_left.x * 0.1
                    
                    # 실제 제어 적용
                    self.piracer.set_throttle_percent(throttle)
                    self.piracer.set_steering_percent(steering)
                    
                    if abs(throttle) > 0.01 or abs(steering) > 0.01:
                        print(f"  Input: T={throttle:+.3f}, S={steering:+.3f}")
                        
                time.sleep(0.1)
                
            # 정지
            self.piracer.set_throttle_percent(0.0)
            self.piracer.set_steering_percent(0.0)
            
            self.test_results['gamepad'] = True
            return True
            
        except Exception as e:
            print(f"❌ Gamepad input test failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['gamepad'] = False
            return False
            
    def test_5_continuous_operation(self):
        """연속 작동 테스트"""
        print("\n🔍 Test 5: Continuous Operation (30 seconds)")
        try:
            start_time = time.time()
            
            while time.time() - start_time < 30:
                data = self.gamepad.read_data()
                
                if data:
                    throttle = data.analog_stick_right.y * 0.2  # 20%로 제한
                    steering = data.analog_stick_left.x * 0.3
                    
                    self.piracer.set_throttle_percent(throttle)
                    self.piracer.set_steering_percent(steering)
                    
                    # 5초마다 상태 출력
                    elapsed = time.time() - start_time
                    if int(elapsed) % 5 == 0 and int(elapsed * 10) % 50 == 0:
                        print(f"  Continuous test: {elapsed:.1f}s, T={throttle:+.2f}, S={steering:+.2f}")
                        
                time.sleep(0.05)  # 20Hz
                
            # 정지
            self.piracer.set_throttle_percent(0.0)
            self.piracer.set_steering_percent(0.0)
            
            self.test_results['continuous'] = True
            return True
            
        except Exception as e:
            print(f"❌ Continuous operation failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['continuous'] = False
            return False
            
    def cleanup(self):
        """정리"""
        print("\n🔧 Cleanup...")
        try:
            if self.piracer:
                self.piracer.set_throttle_percent(0.0)
                self.piracer.set_steering_percent(0.0)
        except:
            pass
            
        GPIO.cleanup()
        
    def run_diagnostics(self):
        """전체 진단 실행"""
        print("🚨 BMW PiRacer Segmentation Fault Diagnostics")
        print("=" * 50)
        
        tests = [
            self.test_1_basic_initialization,
            self.test_2_static_control,
            self.test_3_minimal_movement,
            self.test_4_gamepad_input,
            self.test_5_continuous_operation
        ]
        
        try:
            for test in tests:
                if not test():
                    print(f"\n❌ Test failed: {test.__name__}")
                    break
                    
            # 결과 출력
            print("\n📊 Test Results:")
            for test_name, result in self.test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"  {test_name}: {status}")
                
        except Exception as e:
            print(f"\n🚨 CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.cleanup()

if __name__ == "__main__":
    diagnostics = SegfaultDiagnostics()
    diagnostics.run_diagnostics()