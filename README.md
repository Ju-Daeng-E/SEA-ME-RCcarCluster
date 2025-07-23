# **TEAM 4 (Jackie&Shayan)**

# 🏎️ PiRacer Smart Dashboard & Control System

This project is a **wireless control and real-time digital dashboard system** for the PiRacer (Raspberry Pi-based RC car). It supports wireless gamepad input for driving and gear control, and receives vehicle velocity via **CAN bus** for display in a graphical dashboard using `pygame`(for version 1.0).

---

## 🚀 Features

### 🎮 Wireless Gamepad Control
- Supports **ShanWan Gamepad** (via USB wireless dongle)
- **Gear Selection**:
  - B → Drive (D)
  - A → Neutral (N)
  - X → Reverse (R)
  - Y → Park (P)
- **Speed Gear Shifting**:
  - R2 → Upshift (1 to 4)
  - L2 → Downshift (4 to 1)
- **Analog Control**:
  - Right joystick (Y-axis) → throttle
  - Left joystick (X-axis) → steering
- Throttle input is automatically scaled by current speed gear (25% per level)

### 📡 CAN Bus Velocity Monitoring
- Reads real-time speed data over CAN bus (`can1`, 500kbps)
- CAN messages with ID `0x100` are interpreted as velocity (first 2 bytes)
- Velocity is stored in a shared memory variable for cross-process access

### 📊 Graphical Dashboard
- Built with `pygame`, supports:
  - Speed (km/h)
  - Gear level (1 to 4)
  - Drive mode (D / N / R / P)
- Refreshes at ~20Hz

---

## 🧠 System Architecture

![PiRacer System Diagram](Piracer.png)

## 🔧 Component Overview
### 🎮 GamePad + USB Dongle
- Wireless controller paired via 2.4GHz USB dongle.

- Plugs into a USB port on the Raspberry Pi.

- Provides user input for:

    - Throttle

    - Steering

    - Gear selection (P/N/R/D)

### 💻 Raspberry Pi 4B
- Central processing unit of the system.

- Handles:

    - CAN Communication via SPI with a CAN FD Controller.

    - UI Rendering via a 7.9" DSI Capacitive Touch Screen.

    - Motor Control via I2C to the periphery board.

    - Gamepad Input via USB dongle.

- Runs two multiprocessing components:

    - Drive Control: Reads gamepad input and commands motors.

    - CAN Receiver: Listens for velocity data and shares it through IPC (multiprocessing.Value).

### 🔁 CAN Bus Subsystem
- Consists of an Arduino Uno with a CAN BUS Shield.

- A  Speed Sensor (rotary encoder) measures wheel RPM.

- Sends RPM data as a CAN frame with ID 0x100 to Raspberry Pi.

- Baudrate: 500 kbps

### 🔌 Waveshare Periphery Board (I2C)
- Connected to Raspberry Pi via /dev/i2c-1.

- Handles:

    - PWM output to steering and throttle motors.

    - Battery voltage & current monitoring (INA219 at 0x41).

    - OLED display output (SSD1306 at 0x3C).
```
Address	|| Component  || Description
----------------------------------------------
0x40	|| PCA9685    || Steering motor PWM
0x60	|| PCA9685    || Throttle motor PWM
0x41	|| INA219     || Battery monitoring
0x3C	|| SSD1306    || OLED display (optional)
```
### 📺 UI Dashboard (via Pygame)
- Continuously shows:

    - 🔁 Current velocity (converted from RPM to km/h)

    - ⚙️ Gear state (P, N, R, D)

    - 🔄 Drive mode (NORMAL, REVERSE, etc.)

- Runs at 20 FPS (updated every 50ms).

- Displayed on the 7.9" touch screen connected via DSI.


## How we control motors, and get sensor data from Arduino?
### The package from piracer contains vehicles.py
- Take a look inside of this code.
```
/venv/lib/python3.11/site-packages/piracer/vehicles.py

from adafruit_pca9685 import PCA9685
from adafruit_ina219 import INA219
from adafruit_ssd1306 import SSD1306_I2C

class PiRacerBase:
    def __init__(self) -> None:
        self.i2c_bus = busio.I2C(SCL, SDA)
        self.display = SSD1306_I2C(128, 32, self.i2c_bus, addr=0x3c)

class PiRacerStandard(PiRacerBase):
    def __init__(self) -> None:
        super().__init__()
        self.steering_pwm_controller = PCA9685(self.i2c_bus, address=0x40)
        self.steering_pwm_controller.frequency = self.PWM_FREQ_50HZ

        self.throttle_pwm_controller = PCA9685(self.i2c_bus, address=0x60)
        self.throttle_pwm_controller.frequency = self.PWM_FREQ_50HZ

        self.battery_monitor = INA219(self.i2c_bus, addr=0x41)
```
  ### PWM Controller for steering motor and throttle motor use class name "PCA9685", which is name of chip name for controller that commuicate with I2C channel 0x40 and 0x60. 
      - Every I2C frequency is 50HZ
      - You can see code for PCA9685 in this directory
        - /venv/lib/python3.11/site-packages/adafruit_pca9685.py
      
  ### In similar case, Battery Monitor use class name "INA219", which is name of chip name that communicate with I2C.
      - /venv/lib/python3.11/site-packages/adafruit_ina219.py
  ### Display use busio to use SSD1306 chip with I2C address 0x3c.
      - /venv/lib/python3.11/site-packages/adafruit_ssd1306.py

## For Sensor Data, we use CAN protocol. 
- Speed Sensor -> Arduino -> Arduino CAN hat -> Rasp Pi CAN hat-> Raspberry Pi
- Through this code below, arduino collects speed data(velocity) and sends data to raspberry pi through CAN protocol
  - CAN bit rate : 500Kbps
  - CAN ID : 0x100
```
#include <TimerOne.h>
#include <mcp_can.h>
#include <SPI.h>

#define ENCODER_PIN 3
#define CS_PIN 10

MCP_CAN CAN0(CS_PIN); 

int counter = 0;
unsigned long previousMicros = 0;
const int interval_sec = 1;
const int pulsesPerTurn = 40;  // encoder wheel: 20 slots × 2 (rising+falling)
const int wheel_diameter_mm = 64;  // mm
float velocity_kmh = 0;


byte data[8] = {0};

// Setup
void setup() {
  Serial.begin(115200);
  while (!Serial);

  pinMode(ENCODER_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(ENCODER_PIN), countPulses, CHANGE);


  Timer1.initialize(interval_sec * 1000000);
  Timer1.attachInterrupt(calculateSpeed);

  Serial.print("Initializing MCP2515... ");
  if (CAN0.begin(MCP_ANY, CAN_500KBPS, MCP_16MHZ) == CAN_OK) {
    Serial.println("✅ Success");
  } else {
    Serial.println("❌ Failed");
    while (1);
  }

  CAN0.setMode(MCP_NORMAL);
  Serial.println("Ready to transmit CAN speed data.");
}


void countPulses() {
  if (micros() - previousMicros >= 700) {
    counter++;
    previousMicros = micros();
  }
}


void calculateSpeed() {
  Timer1.detachInterrupt();

  int rpm = (60 * counter) / pulsesPerTurn;
  float wheel_circ_m = 3.1416 * (wheel_diameter_mm / 1000.0);
  velocity_kmh = (rpm * wheel_circ_m * 60) / 1000.0;

  Serial.print("[INFO] RPM: ");
  Serial.print(rpm);
  Serial.print(" | Speed: ");
  Serial.print(velocity_kmh);
  Serial.println(" km/h");

  int velocity_int = (int)(velocity_kmh * 100);
  data[0] = highByte(velocity_int);
  data[1] = lowByte(velocity_int);

  for (int i = 2; i < 8; i++) data[i] = 0;

  counter = 0;
  Timer1.attachInterrupt(calculateSpeed);
}


void loop() {
  Serial.print("[CAN] Sending velocity... ");
  byte sndStat = CAN0.sendMsgBuf(0x100, 0, 8, data);

  if (sndStat == CAN_OK) {
    Serial.println("✅ Sent");
  } else {
    Serial.println("❌ Failed");
  }

  delay(200);  
}

```

- You can just connect CAN_H -> CAN_H , CAN_L -> CAN_L between Arduino HAT and Raspberry pi HAT (SUPER EASY)
- Once you connect these pins and upload Speed_CAN.ino to Arduino, you can check CAN data using this command
```
//Setup CAN channel 1 bit rate as 500Kbps
//If it doesn't work, check channel 0 as well.

sudo ip link set can1 up type can bitrate 500000

candump can1
```

```
pi@team4:~ $ candump can1
  can1  100   [8]  00 00 00 00 00 00 00 00
  can1  100   [8]  00 00 00 00 00 00 00 00
  can1  100   [8]  00 00 00 00 00 00 00 00
  can1  100   [8]  00 50 00 00 00 00 00 00
  can1  100   [8]  00 50 00 00 00 00 00 00
  can1  100   [8]  00 50 00 00 00 00 00 00
  can1  100   [8]  00 50 00 00 00 00 00 00
  can1  100   [8]  00 50 00 00 00 00 00 00
  can1  100   [8]  00 75 00 00 00 00 00 00
  can1  100   [8]  00 75 00 00 00 00 00 00
  can1  100   [8]  00 75 00 00 00 00 00 00
  can1  100   [8]  00 75 00 00 00 00 00 00
```
### If you can see candump, it succeeded!

## CAN Verification in Python for Raspberry Pi
```
import can
bus = can.Bus(interface='socketcan', channel='can1')
msg = bus.recv()
print(msg.data)
```
- Try this code to verify CAN communication !
