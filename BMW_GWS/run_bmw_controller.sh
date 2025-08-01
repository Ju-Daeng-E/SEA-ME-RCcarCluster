#!/bin/bash
# BMW Controller 실행 스크립트

echo "🚗 Starting BMW PiRacer Controller..."
cd /home/pi/SEA-ME-RCcarCluster/piracer_team4
source venv/bin/activate
cd ../BMW_GWS

# sudo가 필요한 경우
if [ "$1" = "sudo" ]; then
    echo "🔧 Running with sudo privileges..."
    # 두 개의 venv 경로를 모두 포함
    COMBINED_PYTHONPATH="/home/pi/SEA-ME-RCcarCluster/piracer_team4/venv/lib/python3.11/site-packages:/home/pi/piracer_test/venv/lib/python3.11/site-packages:$PYTHONPATH"
    
    sudo PYTHONPATH="$COMBINED_PYTHONPATH" \
         LD_LIBRARY_PATH="/home/pi/SEA-ME-RCcarCluster/piracer_team4/venv/lib/python3.11/site-packages:/home/pi/piracer_test/venv/lib/python3.11/site-packages:$LD_LIBRARY_PATH" \
         /home/pi/SEA-ME-RCcarCluster/piracer_team4/venv/bin/python3 \
         bmw_piracer_integrated_control_optimized.py
else
    echo "🔧 Running with user privileges..."
    python3 bmw_piracer_integrated_control_optimized.py
fi