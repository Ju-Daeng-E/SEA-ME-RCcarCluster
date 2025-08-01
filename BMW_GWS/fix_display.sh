#!/bin/bash
# 디스플레이 문제 해결 스크립트

echo "🔍 Checking display configuration..."

# 현재 디스플레이 상태 확인
echo "Current DISPLAY: $DISPLAY"
echo "Current user: $USER"

# X11 서버 확인
if pgrep -x "Xorg" > /dev/null; then
    echo "✅ X11 server is running"
else
    echo "❌ X11 server is not running"
fi

# 디스플레이 권한 설정
echo "🔧 Setting up display permissions..."
export DISPLAY=:0

# xauth 설정 (필요시)
if command -v xauth &> /dev/null; then
    echo "🔑 Setting up xauth..."
    xauth generate :0 . trusted
    xauth add ${HOST}:0 . $(xxd -l 16 -p /dev/urandom)
fi

# 테스트 GUI 실행
echo "🧪 Testing GUI with different backends..."
echo "Testing with default backend..."
timeout 3s python3 -c "
import sys
from PyQt5.QtWidgets import QApplication, QLabel
try:
    app = QApplication(sys.argv)
    label = QLabel('Test')
    label.show()
    print('✅ Default backend works')
except Exception as e:
    print(f'❌ Default backend failed: {e}')
" 2>/dev/null && echo "GUI test passed" || echo "GUI test failed"

echo ""
echo "🔧 Try these solutions:"
echo "1. Run GUI on physical display: sudo systemctl start lightdm"
echo "2. Use VNC: vncserver :1 && export DISPLAY=:1"
echo "3. Use console-only version: python3 bmw_controller_safe.py"