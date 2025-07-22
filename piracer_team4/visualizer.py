# visualizer.py
import pygame
from multiprocessing import Value
import time

def run_visualizer(shared_velocity, shared_gear_mode, shared_drive_mode):
    pygame.init()
    screen = pygame.display.set_mode((400, 1280))
    pygame.display.set_caption("PiRacer Visualizer")

    font = pygame.font.SysFont(None, 48)
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        screen.fill((30, 30, 30))  # 배경

        # 값 가져오기
        with shared_velocity.get_lock():
            velocity = shared_velocity.value
        with shared_gear_mode.get_lock():
            gear = shared_gear_mode.value.decode()
        with shared_drive_mode.get_lock():
            drive = shared_drive_mode.value.decode()

        # 텍스트 렌더링
        velocity_text = font.render(f"Speed: {velocity:.2f} km/h", True, (255, 255, 255))
        gear_text = font.render(f"Gear: {gear}", True, (0, 255, 255))
        drive_text = font.render(f"Mode: {drive}", True, (255, 200, 0))

        screen.blit(velocity_text, (50, 40))
        screen.blit(gear_text, (50, 100))
        screen.blit(drive_text, (50, 160))

        pygame.display.flip()
        clock.tick(20)
