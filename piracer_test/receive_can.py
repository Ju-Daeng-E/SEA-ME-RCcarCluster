import can

def receive_velocity():
    # 소켓CAN 인터페이스 설정 (예: can0 또는 can1)
    bus = can.Bus(interface='socketcan', channel='can1')

    print("🚗 Listening for CAN messages with ID 0x100 (velocity)...")

    try:
        while True:
            msg = bus.recv(timeout=5.0)
            if msg is None:
                print("⏳ No message received.")
                continue

            if msg.arbitration_id == 0x100 and len(msg.data) >= 2:
                # 앞 2바이트는 velocity * 100 정수값
                velocity_raw = (msg.data[0] << 8) | msg.data[1]
                velocity_kmh = velocity_raw / 100.0
                print(f"✅ Received velocity: {velocity_kmh:.2f} km/h")

            else:
                print(f"ℹ️ Other CAN ID {hex(msg.arbitration_id)}: {msg.data.hex()}")

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")

if __name__ == "__main__":
    receive_velocity()
