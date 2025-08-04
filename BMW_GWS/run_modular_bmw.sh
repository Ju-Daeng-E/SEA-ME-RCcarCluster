#!/bin/bash
"""
BMW PiRacer Modular System Startup Script
모듈화된 BMW PiRacer 시스템을 실행하는 쉘 스크립트
"""

# 스크립트 설정
set -e  # 에러 발생시 종료
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$SCRIPT_DIR/bmw_modular_launcher.py"

# 색상 설정
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${BLUE}"
echo "  ██████╗ ███╗   ███╗██╗    ██╗    ██████╗ █████╗ ██╗     "
echo "  ██╔══██╗████╗ ████║██║    ██║    ██╔══██╗██╔══██╗██║     "
echo "  ██████╔╝██╔████╔██║██║ █╗ ██║    ██████╔╝███████║██║     "
echo "  ██╔══██╗██║╚██╔╝██║██║███╗██║    ██╔══██╗██╔══██║██║     "
echo "  ██████╔╝██║ ╚═╝ ██║╚███╔███╔╝    ██║  ██║██║  ██║███████╗"
echo "  ╚═════╝ ╚═╝     ╚═╝ ╚══╝╚══╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${GREEN}BMW PiRacer Modular Control System${NC}"
echo "======================================================"

# 파라미터 체크
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help, -h          Show this help message"
    echo "  --no-gui            Run without GUI (console mode)"
    echo "  --setup-can         Setup CAN interface before starting"
    echo "  --simulation        Run in full simulation mode"
    echo "  --config-check      Check configuration and exit"
    echo "  --deps-check        Check dependencies and exit"
    echo "  --verbose, -v       Enable verbose output"
    echo "  --max-throttle N    Set maximum throttle (0.1-1.0)"
    echo "  --max-steering N    Set maximum steering (0.1-1.0)"
    echo ""
    echo "Environment Variables:"
    echo "  BMW_CAN_INTERFACE   CAN interface name (default: can0)"
    echo "  PIRACER_MAX_THROTTLE Maximum throttle limit"
    echo "  LOG_LEVEL           Logging level (DEBUG|INFO|WARNING|ERROR|CRITICAL)"
    echo ""
    echo "Examples:"
    echo "  $0                  # Normal startup"
    echo "  $0 --no-gui         # Console mode only"
    echo "  $0 --simulation     # Simulation mode (no hardware)"
    echo "  $0 --setup-can      # Setup CAN interface first"
    exit 0
}

# 시스템 체크 함수
check_system() {
    echo -e "${YELLOW}🔍 System Check...${NC}"
    
    # Python 버전 체크
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 not found${NC}"
        exit 1
    fi
    
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo -e "${GREEN}✅ Python $python_version${NC}"
    
    # 런처 스크립트 존재 확인
    if [ ! -f "$LAUNCHER" ]; then
        echo -e "${RED}❌ Launcher script not found: $LAUNCHER${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Launcher script found${NC}"
    
    # 모듈 디렉터리 확인
    if [ ! -d "$SCRIPT_DIR/bmw_modular" ]; then
        echo -e "${RED}❌ Module directory not found: $SCRIPT_DIR/bmw_modular${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Module directory found${NC}"
    
    # 권한 확인 (CAN 설정용)
    if groups $USER | grep -q sudo; then
        echo -e "${GREEN}✅ Sudo access available${NC}"
    else
        echo -e "${YELLOW}⚠️ No sudo access (CAN setup may fail)${NC}"
    fi
    
    echo ""
}

# CAN 인터페이스 사전 체크
check_can_interface() {
    local interface=${BMW_CAN_INTERFACE:-can0}
    
    echo -e "${YELLOW}🔧 Checking CAN interface: $interface${NC}"
    
    if ip link show $interface &> /dev/null; then
        local state=$(ip link show $interface | grep -o "state [A-Z]*" | cut -d' ' -f2)
        echo -e "${GREEN}✅ CAN interface $interface exists (state: $state)${NC}"
    else
        echo -e "${YELLOW}⚠️ CAN interface $interface not found (will use mock data)${NC}"
    fi
}

# 프로세스 정리 함수
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    
    # BMW 관련 프로세스 종료
    pkill -f "bmw_modular_launcher" 2>/dev/null || true
    pkill -f "bmw.*control" 2>/dev/null || true
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# 시그널 트랩 설정
trap cleanup EXIT INT TERM

# 메인 실행 부분
main() {
    # 파라미터 파싱
    case "${1:-}" in
        --help|-h)
            show_help
            ;;
        --config-check)
            echo -e "${YELLOW}📋 Configuration Check${NC}"
            python3 "$LAUNCHER" --config-check
            exit $?
            ;;
        --deps-check)
            echo -e "${YELLOW}📦 Dependencies Check${NC}"
            python3 "$LAUNCHER" --deps-check
            exit $?
            ;;
    esac
    
    # 시스템 체크
    check_system
    
    # CAN 인터페이스 체크
    check_can_interface
    
    # 로그 디렉터리 생성
    mkdir -p "$SCRIPT_DIR/logs"
    
    echo -e "${GREEN}🚀 Starting BMW PiRacer Modular System...${NC}"
    echo "Press Ctrl+C to stop"
    echo ""
    
    # Python 런처 실행
    cd "$SCRIPT_DIR"
    python3 "$LAUNCHER" "$@"
}

# 스크립트 실행
main "$@"