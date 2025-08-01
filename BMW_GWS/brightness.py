import can
import time
import crccheck
# 최대 밝기 값
brightness = 0xFF
bus = can.interface.Bus(channel='can0', bustype='socketcan')  # 예: Linux 기준
# CAN 메시지 생성 및 전송
msg = can.Message(arbitration_id=0x202,
                  data=[brightness, 0x00],
                  is_extended_id=False)

class BMW3FDCRC(crccheck.crc.Crc8Base):
    _poly = 0x1D
    _initvalue = 0x0
    _xor_output = 0x70


def bmw_3fd_crc(message):
    return BMW3FDCRC.calc(message) & 0xFF

def confirm_working_checksum(bus, message):
    """Simple function to use the DTCs to check if bmw_3fd_crc() returns correct values"""
    return verify_checksum(bus, [bmw_3fd_crc(message)] + message)


def send_gws_status(bus, status_bytes, tx_seconds=3):
    counter = 0
    t0 = time.time()

    while time.time() < t0 + tx_seconds:
        payload = [counter & 0xFF] + status_bytes
        payload = [bmw_3fd_crc(payload)] + payload
        message = can.Message(arbitration_id=0x3FD,
                              data=payload, is_extended_id=False)
        message.channel = 0
        bus.send(message)

        time.sleep(0.1)
        counter += 1
 
while(1):       
    send_gws_status(bus, [0x80, 0x00, 0x00])
    send_gws_status(bus, [0x40, 0x40, 0x40])
    send_gws_status(bus, [0x20, 0xff, 0xff])
    send_gws_status(bus, [0xa0, 0x00, 0x00])
    #bus.send(msg)
