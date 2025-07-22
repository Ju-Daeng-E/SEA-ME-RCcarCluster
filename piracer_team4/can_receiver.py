# can_receiver.py
import can
import time
from multiprocessing import Value

def can_receive_velocity(shared_velocity):
    bus = can.Bus(interface='socketcan', channel='can1') 
    print("📡 CAN transeive start (ID 0x100)...")

    while True:
        msg = bus.recv(timeout=1.0)
        if msg and msg.arbitration_id == 0x100 and len(msg.data) >= 2:
            raw_speed = (msg.data[0] << 8) | msg.data[1]
            with shared_velocity.get_lock():
                shared_velocity.value = raw_speed / 100.0
        time.sleep(0.01)
