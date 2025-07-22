import time
import pygame
from multiprocessing import Process, Value, Array
from piracer.vehicles import PiRacerStandard
from piracer.gamepads import ShanWanGamepad
from can_receiver import can_receive_velocity

def init_display():
    pygame.init()
    screen = pygame.display.set_mode((400, 1280))
    pygame.display.set_caption("PiRacer Dashboard")
    return screen

def render_dashboard(screen, velocity, gear_mode, drive_mode):
    screen.fill((0, 0, 0))
    font = pygame.font.Font(None, 48)

    vel_text = font.render(f"Speed: {velocity:.2f} km/h", True, (0, 255, 0))
    gear_text = font.render(f"Gear: {gear_mode}", True, (255, 255, 0))
    mode_text = font.render(f"Drive Mode: {drive_mode}", True, (0, 128, 255))

    screen.blit(vel_text, (30, 30))
    screen.blit(gear_text, (30, 100))
    screen.blit(mode_text, (30, 170))
    pygame.display.flip()

if __name__ == '__main__':
    shared_velocity = Value('d', 0.0)
    shared_drive_mode = Array('c', b'NEUTRAL' + b'\x00'*1)  # max 8 byte

    can_proc = Process(target=can_receive_velocity, args=(shared_velocity,))
    can_proc.start()

    piracer = PiRacerStandard()
    shanwan_gamepad = ShanWanGamepad()
    screen = init_display()

    gear_mode = 'N'
    speed_gear = 1
    last_l2 = last_r2 = False

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt()

            gamepad_input = shanwan_gamepad.read_data()

            # 기어 입력
            if gamepad_input.button_b:
                gear_mode = 'D'
                shared_drive_mode.value = b'NORMAL' + b'\x00'*2
            elif gamepad_input.button_a:
                gear_mode = 'N'
                shared_drive_mode.value = b'NEUTRAL' + b'\x00'*1
            elif gamepad_input.button_x:
                gear_mode = 'R'
                shared_drive_mode.value = b'REVERSE' + b'\x00'
            elif gamepad_input.button_y:
                gear_mode = 'P'
                shared_drive_mode.value = b'PARK' + b'\x00'*4

            if gamepad_input.button_l2 and not last_l2:
                speed_gear = max(1, speed_gear - 1)
            if gamepad_input.button_r2 and not last_r2:
                speed_gear = min(4, speed_gear + 1)
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

            with shared_velocity.get_lock():
                velocity = shared_velocity.value

            render_dashboard(screen, velocity, gear_mode, shared_drive_mode.value.decode().strip('\x00'))
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Exit")
        can_proc.terminate()
        pygame.quit()
