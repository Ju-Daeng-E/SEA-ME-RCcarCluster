#!/bin/bash
# BMW Controller 안전 실행 스크립트 - Segmentation Fault 방지

echo "🛡️ BMW PiRacer Safe Controller - Segfault Prevention"
echo "=" * 50

# 환경 설정
cd /home/pi/SEA-ME-RCcarCluster/piracer_team4
source venv/bin/activate
cd ../BMW_GWS

# 메모리 제한 설정 (100MB)
ulimit -v 102400  # 가상 메모리 제한
ulimit -m 102400  # 물리 메모리 제한

# 코어 덤프 활성화 (디버깅용)
ulimit -c unlimited

echo "🔧 System limits configured:"
echo "  Virtual memory: $(ulimit -v) KB"
echo "  Physical memory: $(ulimit -m) KB"
echo "  Core dump: $(ulimit -c)"

# 실행 모드 선택
case "$1" in
    "diagnosis")
        echo "🩺 Running segfault diagnosis..."
        python3 test_segfault_diagnosis.py
        ;;
    "safe")
        echo "🛡️ Running segfault-safe controller..."
        python3 bmw_controller_segfault_safe.py
        ;;
    "minimal")
        echo "🔍 Running minimal safe controller..."
        python3 bmw_controller_safe.py
        ;;
    "sudo")
        echo "🔧 Running with sudo privileges..."
        sudo PYTHONPATH="/home/pi/SEA-ME-RCcarCluster/piracer_team4/venv/lib/python3.11/site-packages:/home/pi/piracer_test/venv/lib/python3.11/site-packages:$PYTHONPATH" \
             /home/pi/SEA-ME-RCcarCluster/piracer_team4/venv/bin/python3 \
             bmw_controller_segfault_safe.py
        ;;
    *)
        echo "🚗 Running default safe controller..."
        python3 bmw_controller_segfault_safe.py
        ;;
esac

echo ""
echo "📊 Usage:"
echo "  ./run_safe_bmw.sh           # Default safe mode"
echo "  ./run_safe_bmw.sh diagnosis # Run diagnostics"
echo "  ./run_safe_bmw.sh safe      # Enhanced safe mode"
echo "  ./run_safe_bmw.sh minimal   # Minimal safe mode"
echo "  ./run_safe_bmw.sh sudo      # Run with sudo"