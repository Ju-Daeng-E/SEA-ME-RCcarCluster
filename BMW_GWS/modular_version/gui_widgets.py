"""
Custom GUI widgets for BMW PiRacer Integrated Control System
"""

# Try to import PyQt5, fallback to mock if not available
try:
    from PyQt5.QtWidgets import QWidget
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont
    PYQT5_AVAILABLE = True
    BaseWidget = QWidget
except ImportError:
    print("⚠️ PyQt5 library not found. Using mock widgets for testing.")
    PYQT5_AVAILABLE = False
    BaseWidget = object

from constants import Constants

class SpeedometerWidget(BaseWidget):
    """Speedometer display widget - optimized"""
    
    def __init__(self):
        self.current_speed = 0.0
        self.max_speed = Constants.MAX_SPEED
        
        if PYQT5_AVAILABLE:
            super().__init__()
            self.setMinimumSize(*Constants.SPEEDOMETER_SIZE)
            
            # Color caching
            self.bg_color = QColor(20, 20, 20)
            self.border_color = QColor(0, 120, 215)
            self.speed_color = QColor(0, 255, 100)
            self.text_color = QColor(255, 255, 255)
            self.circle_color = QColor(100, 100, 100)
        
    def set_speed(self, speed: float):
        """Set speed"""
        new_speed = max(0, min(speed, self.max_speed))
        if abs(self.current_speed - new_speed) > 0.1:  # Ignore small changes
            self.current_speed = new_speed
            if PYQT5_AVAILABLE:
                self.update()
        
    def paintEvent(self, event):
        if not PYQT5_AVAILABLE:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Border
        painter.setPen(QPen(self.border_color, 3))
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
        
        # Speedometer circle
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(self.width(), self.height()) // 2 - 20
        
        painter.setPen(QPen(self.circle_color, 2))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Speed text
        painter.setPen(QPen(self.speed_color))
        font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(font)
        
        speed_text = f"{self.current_speed:.1f}"
        text_rect = self.rect().adjusted(0, -20, 0, 0)
        painter.drawText(text_rect, Qt.AlignCenter, speed_text)
        
        # Unit
        painter.setPen(QPen(self.text_color))
        font = QFont("Arial", 12)
        painter.setFont(font)
        unit_rect = self.rect().adjusted(0, 25, 0, 0)
        painter.drawText(unit_rect, Qt.AlignCenter, "km/h")

class GearDisplayWidget(BaseWidget):
    """Current gear status display widget - optimized"""
    
    def __init__(self):
        self.current_gear = 'Unknown'
        self.manual_gear = 1
        
        if PYQT5_AVAILABLE:
            super().__init__()
            self.setMinimumSize(*Constants.GEAR_DISPLAY_SIZE)
            
            # Color mapping caching
            self.gear_colors = {
                'P': QColor(255, 100, 100),    # Red
                'R': QColor(255, 140, 0),      # Orange
                'N': QColor(255, 255, 100),    # Yellow
                'D': QColor(100, 255, 100),    # Green
                'M': QColor(100, 150, 255),    # Blue
                'Unknown': QColor(150, 150, 150)  # Gray
            }
            
            self.status_texts = {
                'P': "PARK",
                'R': "REVERSE", 
                'N': "NEUTRAL",
                'D': "DRIVE",
                'M': lambda gear: f"MANUAL {gear}",
                'Unknown': "UNKNOWN"
            }
        
    def set_gear(self, gear: str, manual_gear: int = 1):
        """Update gear status"""
        if self.current_gear != gear or self.manual_gear != manual_gear:
            self.current_gear = gear
            self.manual_gear = manual_gear
            if PYQT5_AVAILABLE:
                self.update()
        
    def paintEvent(self, event):
        if not PYQT5_AVAILABLE:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        
        # Border
        painter.setPen(QPen(QColor(0, 120, 215), 3))
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 15, 15)
        
        # Gear-specific color and status text
        gear_key = self.current_gear[0] if self.current_gear.startswith('M') else self.current_gear
        color = self.gear_colors.get(gear_key, self.gear_colors['Unknown'])
        
        if self.current_gear.startswith('M'):
            status_text = self.status_texts['M'](self.manual_gear)
        else:
            status_text = self.status_texts.get(self.current_gear, "UNKNOWN")
        
        # Gear display
        painter.setPen(QPen(color))
        font = QFont("Arial", 36, QFont.Bold)
        painter.setFont(font)
        
        gear_rect = self.rect().adjusted(0, -20, 0, 0)
        painter.drawText(gear_rect, Qt.AlignCenter, self.current_gear)
        
        # Status text
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 10)
        painter.setFont(font)
        status_rect = self.rect().adjusted(0, 30, 0, 0)
        painter.drawText(status_rect, Qt.AlignCenter, status_text) 