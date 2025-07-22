import os
import pathlib
import time
from piracer.vehicles import PiRacerBase, PiRacerStandard, PiRacerPro
import socket


FILE_DIR = pathlib.Path(os.path.abspath(os.path.dirname(__file__)))

def get_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No IP"
    
def print_battery_report(vehicle: PiRacerBase):
    battery_voltage = vehicle.get_battery_voltage()
    battery_current = vehicle.get_battery_current()
    power_consumption = vehicle.get_power_consumption()
    ip_address = get_ip_address()

    display = vehicle.get_display()

    output_text = 'U={0:0>6.2f}V\nI={1:0>7.0f}mA\nP={2:0>6.2f}W\nIP:{3}'.format(
        battery_voltage, battery_current, power_consumption, ip_address)

    display.fill(0)
    display.text(output_text, 0, 0, 'white', font_name=FILE_DIR / 'fonts/font5x8.bin')
    display.show()

if __name__ == '__main__':

    piracer = PiRacerPro()
    # piracer = PiRacerStandard()

    while True:
        print_battery_report(piracer)
        time.sleep(0.5)