"""Mock pysnmp BEFORE any test imports — prevents asyncore crash on Python >=3.12."""
import sys
from unittest.mock import MagicMock

pysnmp_mock = MagicMock()
sys.modules['pysnmp'] = pysnmp_mock
sys.modules['pysnmp.entity'] = pysnmp_mock.entity
sys.modules['pysnmp.entity.rfc3413'] = pysnmp_mock.entity.rfc3413
sys.modules['pysnmp.entity.rfc3413.oneliner'] = pysnmp_mock.entity.rfc3413.oneliner
sys.modules['pysnmp.entity.rfc3413.oneliner.cmdgen'] = MagicMock()
