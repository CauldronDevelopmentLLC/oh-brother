"""Mock pysnmp BEFORE any test imports — prevents asyncore crash on Python >=3.12."""
import sys
from unittest.mock import MagicMock

pysnmp_mock = MagicMock()
sys.modules['pysnmp'] = pysnmp_mock
sys.modules['pysnmp.hlapi'] = MagicMock()
