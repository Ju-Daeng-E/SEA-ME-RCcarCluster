#!/bin/bash
# BMW PiRacer Control 시작 스크립트

# 스크립트 디렉토리로 이동
cd /home/pi/SEA-ME-RCcarCluster/BMW_GWS

# 로그 파일 경로
LOG_FILE="/home/pi/SEA-ME-RCcarCluster/BMW_GWS/bmw_control.log"

# 시작 메시지
echo "$(date): BMW PiRacer Control 시작" >> "$LOG_FILE"

# CAN 인터페이스 설정 확인
echo "$(date): CAN 인터페이스 상태 확인" >> "$LOG_FILE"
ip link show can0 >> "$LOG_FILE" 2>&1
ip link show can1 >> "$LOG_FILE" 2>&1

# Python 스크립트 실행
echo "$(date): BMW PiRacer Control 애플리케이션 실행" >> "$LOG_FILE"
python3 bmw_piracer_integrated_control_optimized.py >> "$LOG_FILE" 2>&1

# 종료 메시지
echo "$(date): BMW PiRacer Control 종료" >> "$LOG_FILE"