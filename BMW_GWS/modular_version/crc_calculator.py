"""
CRC calculation utilities for BMW PiRacer Integrated Control System
"""

# Try to import crccheck, fallback to mock if not available
try:
    import crccheck
    CRCCHECK_AVAILABLE = True
except ImportError:
    print("⚠️ crccheck library not found. Using mock CRC calculation.")
    CRCCHECK_AVAILABLE = False

class BMW3FDCRC:
    """BMW 3FD CRC implementation"""
    if CRCCHECK_AVAILABLE:
        class _CRC(crccheck.crc.Crc8Base):
            _poly = 0x1D
            _initvalue = 0x0
            _xor_output = 0x70
        
        @staticmethod
        def calc(data):
            return BMW3FDCRC._CRC.calc(data)
    else:
        @staticmethod
        def calc(data):
            # Simple mock CRC calculation
            return sum(data) & 0xFF

class BMW197CRC:
    """BMW 197 CRC implementation"""
    if CRCCHECK_AVAILABLE:
        class _CRC(crccheck.crc.Crc8Base):
            _poly = 0x1D
            _initvalue = 0x0
            _xor_output = 0x53
        
        @staticmethod
        def calc(data):
            return BMW197CRC._CRC.calc(data)
    else:
        @staticmethod
        def calc(data):
            # Simple mock CRC calculation
            return (sum(data) + 0x53) & 0xFF

class CRCCalculator:
    """CRC calculation with caching for performance optimization"""
    
    def __init__(self):
        self._cache_3fd = {}
        self._cache_197 = {}
    
    def bmw_3fd_crc(self, message: bytes) -> int:
        """BMW 3FD CRC calculation (cached)"""
        message_bytes = bytes(message) if not isinstance(message, bytes) else message
        if message_bytes not in self._cache_3fd:
            self._cache_3fd[message_bytes] = BMW3FDCRC.calc(message_bytes) & 0xFF
        return self._cache_3fd[message_bytes]
    
    def bmw_197_crc(self, message: bytes) -> int:
        """BMW 197 CRC calculation (cached)"""
        message_bytes = bytes(message) if not isinstance(message, bytes) else message
        if message_bytes not in self._cache_197:
            self._cache_197[message_bytes] = BMW197CRC.calc(message_bytes) & 0xFF
        return self._cache_197[message_bytes] 