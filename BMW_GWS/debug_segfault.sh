#!/bin/bash
# Segmentation Fault 디버깅 스크립트

echo "🔍 Running segfault debugging..."

cd /home/pi/SEA-ME-RCcarCluster/piracer_team4
source venv/bin/activate
cd ../BMW_GWS

# 코어 덤프 활성화
ulimit -c unlimited
echo "✅ Core dump enabled"

# gdb로 실행 (segfault 발생 시 스택 트레이스 확인)
echo "🐛 Running with GDB for debugging..."
gdb --batch --ex run --ex bt --ex quit --args python3 bmw_piracer_integrated_control_optimized.py