from piracer.vehicles import PiRacerStandard
from piracer.gamepads import ShanWanGamepad

import can
import threading
import struct
import time

# ---------------------------
# CAN 속도 수신용 글로벌 변수
latest_velocity = 0.0  # km/h

# ---------------------------
# CAN 수신 쓰레드
def can_receive_velocity():
    global latest_velocity
    bus = can.Bus(interface='socketcan', channel='can1')  # can0 또는 can1 사용
    print("📡 CAN 수신 시작 (ID 0x100)...")

    while True:
        msg = bus.recv(timeout=1.0)
        if msg and msg.arbitration_id == 0x100 and len(msg.data) >= 2:
            # 앞 2바이트는 속도값 (unsigned int, 단위: km/h * 100)
            raw_speed = (msg.data[0] << 8) | msg.data[1]
            latest_velocity = raw_speed / 100.0  # 예: 503 → 5.03 km/h

# ---------------------------
# 주 실행 루프
if __name__ == '__main__':
    shanwan_gamepad = ShanWanGamepad()
    piracer = PiRacerStandard()

    gear_mode = 'N'
    speed_gear = 1  # 1단 시작
    last_l2 = False
    last_r2 = False

    print("기어 조작: B=D, A=N, X=R, Y=P | L2: 다운, R2: 업")

    # CAN 수신 쓰레드 시작
    can_thread = threading.Thread(target=can_receive_velocity, daemon=True)
    can_thread.start()

    while True:
        gamepad_input = shanwan_gamepad.read_data()

        # 기어 상태 업데이트
        if gamepad_input.button_b:
            gear_mode = 'D'
            print("🚗 기어: D (전진)")
        elif gamepad_input.button_a:
            gear_mode = 'N'
            print("🅽 기어: N (중립)")
        elif gamepad_input.button_x:
            gear_mode = 'R'
            print("🔙 기어: R (후진)")
        elif gamepad_input.button_y:
            gear_mode = 'P'
            print("🅿️ 기어: P (주차)")

        # 속도 기어 조절 (토글 방식)
        if gamepad_input.button_l2 and not last_l2:
            speed_gear = max(1, speed_gear - 1)
            print(f"⬇️ 속도 기어 ↓ {speed_gear}단 ({speed_gear * 25}%)")
        if gamepad_input.button_r2 and not last_r2:
            speed_gear = min(4, speed_gear + 1)
            print(f"⬆️ 속도 기어 ↑ {speed_gear}단 ({speed_gear * 25}%)")

        last_l2 = gamepad_input.button_l2
        last_r2 = gamepad_input.button_r2

        speed_limit = speed_gear * 0.25

        throttle_input = -gamepad_input.analog_stick_right.y
        steering = -gamepad_input.analog_stick_left.x

        if gear_mode == 'D':
            throttle = min(0.0, throttle_input)
        elif gear_mode == 'R':
            throttle = max(0.0, throttle_input)
        else:
            throttle = 0.0

        throttle *= speed_limit

        piracer.set_throttle_percent(throttle)
        piracer.set_steering_percent(steering)

        # 현재 속도 출력
        print(f"📈 현재 속도: {latest_velocity:.2f} km/h", end='\r')
        time.sleep(0.1)
