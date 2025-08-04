# BMW PiRacer Integrated Control System - Modular Version

A modular, well-structured BMW PiRacer control system with BMW gear lever integration, GPIO speed sensor, and PyQt5 dashboard.

## 🏗️ Modular Architecture

The system has been completely modularized for better maintainability and development:

### Core Modules

- **`constants.py`** - All system constants and configuration
- **`data_models.py`** - Data classes for BMW and PiRacer states
- **`logger.py`** - Custom logging system with multiple handlers
- **`crc_calculator.py`** - BMW-specific CRC calculations with caching
- **`speed_sensor.py`** - GPIO-based speed sensor with polling mode
- **`bmw_lever_controller.py`** - BMW gear lever logic and toggle handling
- **`can_controller.py`** - CAN bus communication and BMW message handling
- **`gamepad_controller.py`** - PiRacer gamepad input and vehicle control
- **`gui_widgets.py`** - Custom PyQt5 widgets (speedometer, gear display)
- **`main_gui.py`** - Main PyQt5 dashboard application
- **`main.py`** - Application entry point with fallback modes

## 🚀 Features

- **BMW Gear Lever Control**: P/R/N/D/M1-M8 gear switching with toggle logic
- **Gamepad Control**: Throttle and steering via ShanWan gamepad
- **GPIO Speed Sensor**: Real-time speed measurement via GPIO16
- **BMW CAN Integration**: Direct CAN bus communication for gear lever
- **Modular Design**: Easy to maintain and extend
- **PyQt5 Dashboard**: Beautiful real-time monitoring interface
- **Headless Mode**: Fallback operation without GUI
- **Error Handling**: Robust error handling and recovery

## 📋 Requirements

### Hardware
- Raspberry Pi (with GPIO access)
- BMW F-Series gear lever with CAN interface
- PiRacer vehicle
- ShanWan gamepad
- Speed sensor connected to GPIO16

### Software Dependencies
```bash
pip install python-can
pip install crccheck
pip install PyQt5  # Optional for GUI
pip install RPi.GPIO
```

### PiRacer Dependencies (Optional)
```bash
# PiRacer libraries (if available)
pip install piracer
```

## 🔧 Installation

1. **Clone the repository**:
   ```bash
   cd BMW_GWS
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup CAN interface**:
   ```bash
   sudo ip link set can0 down
   sudo ip link set can0 up type can bitrate 500000
   ```

4. **Run the application**:
   ```bash
   python3 main.py
   ```

## 🎮 Usage

### GUI Mode (Recommended)
- Run `python3 main.py` with a display connected
- Use ESC key or exit button to close
- Real-time monitoring of all systems

### Headless Mode
- Automatically falls back if no display is available
- Monitors CAN messages in console
- Press Ctrl+C to exit

### Gamepad Controls
- **Left Stick**: Steering
- **Right Stick**: Throttle
- **L2/R2**: Speed gear adjustment
- **Gear Lever**: BMW gear switching

## 🏗️ Module Details

### Constants (`constants.py`)
Centralized configuration for:
- CAN bus settings
- GPIO pin assignments
- Timing parameters
- UI dimensions
- Color schemes

### Data Models (`data_models.py`)
Clean data structures:
- `BMWState`: Gear lever and button states
- `PiRacerState`: Vehicle control states

### Logger (`logger.py`)
Custom logging with:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Multiple handlers support
- Timestamp formatting
- Emoji indicators

### Speed Sensor (`speed_sensor.py`)
GPIO-based speed measurement:
- Polling mode for reliability
- Debouncing for accuracy
- Real-time RPM calculation
- Speed conversion to km/h

### BMW Lever Controller (`bmw_lever_controller.py`)
Advanced gear lever logic:
- Toggle-based gear switching
- Button state handling
- Manual gear control
- State transitions

### CAN Controller (`can_controller.py`)
CAN bus management:
- BMW message handling
- LED control messages
- CRC calculation
- Error handling

### Gamepad Controller (`gamepad_controller.py`)
PiRacer control:
- Gamepad input processing
- Vehicle control commands
- Speed gear management
- Threading for responsiveness

### GUI Widgets (`gui_widgets.py`)
Custom PyQt5 components:
- `SpeedometerWidget`: Real-time speed display
- `GearDisplayWidget`: Current gear indicator

### Main GUI (`main_gui.py`)
Complete dashboard application:
- Modular UI construction
- Signal/slot connections
- Real-time updates
- Error handling

## 🔧 Configuration

### CAN Bus Settings
Edit `constants.py`:
```python
BMW_CAN_CHANNEL = 'can0'
CAN_BITRATE = 500000
```

### Speed Sensor Settings
```python
SPEED_SENSOR_PIN = 16  # GPIO pin
PULSES_PER_TURN = 40   # Encoder pulses per wheel turn
WHEEL_DIAMETER_MM = 64 # Wheel diameter in mm
```

### UI Settings
```python
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 400
```

## 🐛 Troubleshooting

### CAN Bus Issues
```bash
# Check CAN interface
ip link show can0

# Restart CAN interface
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 500000

# Monitor CAN messages
candump can0
```

### GPIO Issues
```bash
# Check GPIO permissions
sudo usermod -a -G gpio $USER

# Test GPIO access
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM)"
```

### GUI Issues
```bash
# Check display
echo $DISPLAY

# Install PyQt5
pip install PyQt5

# Run with explicit display
DISPLAY=:0 python3 main.py
```

## 📁 File Structure

```
BMW_GWS/
├── constants.py              # System constants
├── data_models.py           # Data structures
├── logger.py                # Logging system
├── crc_calculator.py        # CRC calculations
├── speed_sensor.py          # GPIO speed sensor
├── bmw_lever_controller.py  # BMW gear lever logic
├── can_controller.py        # CAN bus control
├── gamepad_controller.py    # Gamepad control
├── gui_widgets.py           # Custom GUI widgets
├── main_gui.py              # Main GUI application
├── main.py                  # Application entry point
├── README.md                # This file
└── requirements.txt         # Dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- BMW for the gear lever design
- PiRacer team for the vehicle platform
- PyQt5 community for the GUI framework
- Python-CAN team for CAN bus support 