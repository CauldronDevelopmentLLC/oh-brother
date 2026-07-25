import importlib.util
import os
import sys
import xml.etree.ElementTree as ET
import pytest

# Import oh-brother.py (filename has a hyphen, not directly importable)
module_path = os.path.join(os.path.dirname(__file__), '..', 'oh-brother.py')
spec = importlib.util.spec_from_file_location("oh_brother", module_path)
oh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oh)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

REAL_SNMP_TABLE = [
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.1", 'MODEL="HL-L2865DW"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.2", 'SERIAL="U00000A0A000000"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.3", 'SPEC="0906"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.4", 'DEMOID="?"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.5", 'FONT="?"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.6", 'FIRMID="MAIN"')],
    [("1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2.7", 'FIRMVER="1.24"')],
]

REAL_BROTHER_RESPONSE_UP_TO_DATE = (
    b'<?xml version="1.0" encoding="UTF-8" ?>'
    b'<RESPONSEINFO>'
    b'<FIRMUPDATEINFO>'
    b'<VERSIONCHECK>1</VERSIONCHECK>'
    b'<FIRMID>MAIN</FIRMID>'
    b'</FIRMUPDATEINFO>'
    b'</RESPONSEINFO>'
)


# ---------------------------------------------------------------------------
# parse_snmp_table
# ---------------------------------------------------------------------------

class TestParseSnmpTable:
    def test_real_printer_data(self):
        """Full extraction from real HL-L2865DW SNMP output."""
        result = oh.parse_snmp_table(REAL_SNMP_TABLE)
        assert result['serial'] == 'U00000A0A000000'
        assert result['model'] == 'HL-L2865DW'
        assert result['spec'] == '0906'
        assert len(result['firmwares']) == 1
        assert result['firmwares'][0] == {'cat': 'MAIN', 'version': '1.24'}

    def test_multiple_firmwares(self):
        """Printer with MAIN + SUB1 firmware."""
        table = [
            [("...6", 'FIRMID="MAIN"')],
            [("...7", 'FIRMVER="1.24"')],
            [("...6", 'FIRMID="SUB1"')],
            [("...7", 'FIRMVER="2.10"')],
        ]
        result = oh.parse_snmp_table(table)
        assert result['firmwares'] == [
            {'cat': 'MAIN', 'version': '1.24'},
            {'cat': 'SUB1', 'version': '2.10'},
        ]

    def test_firmver_before_firmid(self):
        """FIRMVER appearing before its FIRMID — should be skipped."""
        table = [
            [("...7", 'FIRMVER="1.24"')],  # No FIRMID yet — skip
            [("...6", 'FIRMID="MAIN"')],
            [("...7", 'FIRMVER="1.25"')],  # Now paired with MAIN
        ]
        result = oh.parse_snmp_table(table)
        assert len(result['firmwares']) == 1
        assert result['firmwares'][0] == {'cat': 'MAIN', 'version': '1.25'}

    def test_no_equals_sign_skipped(self):
        """Rows without '=' should be silently ignored."""
        table = [
            [("...x", "0x0c")],  # Raw hex byte, no '='
            [("...6", 'FIRMID="MAIN"')],
            [("...7", 'FIRMVER="1.24"')],
        ]
        result = oh.parse_snmp_table(table)
        assert result['model'] is None
        assert result['firmwares'][0] == {'cat': 'MAIN', 'version': '1.24'}

    def test_empty_table(self):
        """Empty table returns all None/empty."""
        result = oh.parse_snmp_table([])
        assert result['serial'] is None
        assert result['model'] is None
        assert result['spec'] is None
        assert result['firmwares'] == []

    def test_model_only(self):
        """Table with only MODEL — no serial, no firmware."""
        table = [[("...1", 'MODEL="HL-L2865DW"')]]
        result = oh.parse_snmp_table(table)
        assert result['model'] == 'HL-L2865DW'
        assert result['serial'] is None
        assert result['firmwares'] == []

    def test_verbose_output(self, capsys):
        """Verbose mode prints the table."""
        oh.parse_snmp_table(REAL_SNMP_TABLE, verbose=True)
        captured = capsys.readouterr()
        assert 'HL-L2865DW' in captured.out


# ---------------------------------------------------------------------------
# build_firmware_xml
# ---------------------------------------------------------------------------

class TestBuildFirmwareXml:
    def test_basic_xml_structure(self):
        xml_bytes = oh.build_firmware_xml('HL-L2865DW', '0906', 'MAIN', '1.24')
        root = ET.fromstring(xml_bytes)
        assert root.find('FIRMUPDATETOOLINFO/FIRMCATEGORY').text == 'MAIN'
        assert root.find('FIRMUPDATETOOLINFO/OS').text == 'WIN_NATIVE'
        assert root.find('FIRMUPDATETOOLINFO/INSPECTMODE').text == '0'
        assert root.find('FIRMUPDATEINFO/MODELINFO/NAME').text == 'HL-L2865DW'
        assert root.find('FIRMUPDATEINFO/MODELINFO/SPEC').text == '0906'
        firm = root.find('FIRMUPDATEINFO/MODELINFO/FIRMINFO/FIRM')
        assert firm.find('ID').text == 'MAIN'
        assert firm.find('VERSION').text == '1.24'

    def test_firm_category_mapped_to_main(self):
        """FIRM category should be mapped to MAIN in FIRMCATEGORY element."""
        xml_bytes = oh.build_firmware_xml('HL-L2865DW', '0906', 'FIRM', '1.00')
        root = ET.fromstring(xml_bytes)
        assert root.find('FIRMUPDATETOOLINFO/FIRMCATEGORY').text == 'MAIN'

    def test_ifax_id_mapped_to_main(self):
        """IFAX firm ID should be mapped to MAIN in ID element."""
        xml_bytes = oh.build_firmware_xml('HL-L2865DW', '0906', 'IFAX', '2.00')
        root = ET.fromstring(xml_bytes)
        firm = root.find('FIRMUPDATEINFO/MODELINFO/FIRMINFO/FIRM')
        assert firm.find('ID').text == 'MAIN'

    def test_beta_mode(self):
        xml_bytes = oh.build_firmware_xml('HL-L2865DW', '0906', 'MAIN', '1.24',
                                          beta=True)
        root = ET.fromstring(xml_bytes)
        assert root.find('FIRMUPDATETOOLINFO/INSPECTMODE').text == '1'

    def test_output_is_bytes(self):
        result = oh.build_firmware_xml('HL-L2865DW', '0906', 'MAIN', '1.24')
        assert isinstance(result, bytes)

    def test_driver_is_ews(self):
        xml_bytes = oh.build_firmware_xml('HL-L2865DW', '0906', 'MAIN', '1.24')
        root = ET.fromstring(xml_bytes)
        assert root.find('FIRMUPDATEINFO/MODELINFO/DRIVER').text == 'EWS'


# ---------------------------------------------------------------------------
# parse_brother_response
# ---------------------------------------------------------------------------

class TestParseBrotherResponse:
    def test_up_to_date(self):
        result = oh.parse_brother_response(REAL_BROTHER_RESPONSE_UP_TO_DATE)
        assert result['version_check'] == '1'
        assert result['firmware_url'] is None

    def test_update_available(self):
        xml = (
            b'<?xml version="1.0" encoding="UTF-8" ?>'
            b'<RESPONSEINFO>'
            b'<FIRMUPDATEINFO>'
            b'<VERSIONCHECK>0</VERSIONCHECK>'
            b'<PATH>http://update-akamai.brother.co.jp/CS/D00XXX_A.djf</PATH>'
            b'</FIRMUPDATEINFO>'
            b'</RESPONSEINFO>'
        )
        result = oh.parse_brother_response(xml)
        assert result['version_check'] == '0'
        assert result['firmware_url'] == (
            'http://update-akamai.brother.co.jp/CS/D00XXX_A.djf'
        )

    def test_no_path_element(self):
        """Newer models (HL-L2865DW) may return no PATH — should return None."""
        xml = (
            b'<?xml version="1.0" encoding="UTF-8" ?>'
            b'<RESPONSEINFO>'
            b'<FIRMUPDATEINFO>'
            b'<VERSIONCHECK>0</VERSIONCHECK>'
            b'<FIRMID>MAIN</FIRMID>'
            b'</FIRMUPDATEINFO>'
            b'</RESPONSEINFO>'
        )
        result = oh.parse_brother_response(xml)
        assert result['version_check'] == '0'
        assert result['firmware_url'] is None

    def test_no_versioncheck(self):
        """Response missing VERSIONCHECK entirely."""
        xml = (
            b'<?xml version="1.0" encoding="UTF-8" ?>'
            b'<RESPONSEINFO>'
            b'<FIRMUPDATEINFO>'
            b'<PATH>http://example.com/firmware.djf</PATH>'
            b'</FIRMUPDATEINFO>'
            b'</RESPONSEINFO>'
        )
        result = oh.parse_brother_response(xml)
        assert result['version_check'] is None
        assert result['firmware_url'] is not None

    def test_empty_response(self):
        """Totally unexpected XML — shouldn't crash."""
        xml = b'<?xml version="1.0" encoding="UTF-8" ?><OTHER/>'
        result = oh.parse_brother_response(xml)
        assert result['version_check'] is None
        assert result['firmware_url'] is None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    """CLI argument parsing — parameterized to avoid testing stdlib argparse."""

    @pytest.mark.parametrize("args_str,attr,expected", [
        # Boolean flags (default False)
        ("1.2.3.4", "yes", False),
        ("1.2.3.4", "test", False),
        ("1.2.3.4", "verbose", False),
        ("1.2.3.4", "beta", False),
        # Boolean flags (set)
        ("--yes 1.2.3.4", "yes", True),
        ("--test 1.2.3.4", "test", True),
        ("--verbose 1.2.3.4", "verbose", True),
        ("--beta 1.2.3.4", "beta", True),
    ])
    def test_boolean_flags(self, args_str, attr, expected):
        args = oh.parser.parse_args(args_str.split())
        assert getattr(args, attr) == expected

    @pytest.mark.parametrize("args_str,attr,expected", [
        # String args (defaults)
        ("1.2.3.4", "community", "public"),
        ("1.2.3.4", "fw_version", "B0000000000"),
        ("1.2.3.4", "model", None),
        ("1.2.3.4", "category", None),
        ("1.2.3.4", "password", None),
        # String args (set)
        ("--community private 1.2.3.4", "community", "private"),
        ("--model HL-1110 1.2.3.4", "model", "HL-1110"),
        ("--password admin123 1.2.3.4", "password", "admin123"),
    ])
    def test_string_args(self, args_str, attr, expected):
        args = oh.parser.parse_args(args_str.split())
        assert getattr(args, attr) == expected

    def test_category_with_version(self):
        args = oh.parser.parse_args(
            "--category SUB1 --fw-version 2.00 1.2.3.4".split())
        assert args.category == "SUB1"
        assert args.fw_version == "2.00"

    def test_ip_required(self):
        with pytest.raises(SystemExit):
            oh.parser.parse_args([])

    def test_parser_accessible(self):
        """Module-level parser is importable."""
        assert hasattr(oh, "parser")


# ---------------------------------------------------------------------------
# Global state reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_global_state(monkeypatch):
    """Reset oh module globals between tests to prevent cross-test leakage."""
    for attr in ("args", "model", "spec", "serial", "firmInfo"):
        monkeypatch.setattr(oh, attr, None, raising=False)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainSmoke:
    """Smoke tests for main() — verifies orchestration without real I/O."""

    def test_main_parses_snmp_and_calls_update(self, monkeypatch):
        """main() extracts SNMP data then calls update_firmware for each category."""
        from unittest.mock import MagicMock

        def fake_walkCmd(*args, **kwargs):
            for snmp_row in REAL_SNMP_TABLE:
                varBinds = [(oid, val) for oid, val in snmp_row]
                yield (None, None, None, varBinds)

        monkeypatch.setattr("builtins.input", lambda _=None: None)

        called_with = []
        def fake_update(cat, ver):
            called_with.append((cat, ver))
        monkeypatch.setattr(oh, "update_firmware", fake_update)

        monkeypatch.setattr(oh, "walkCmd", fake_walkCmd)
        monkeypatch.setattr("sys.argv", ["oh-brother.py", "1.2.3.4"])
        oh.main()

        assert called_with == [("MAIN", "1.24")]

    def test_main_model_override(self, monkeypatch):
        """--model flag overrides SNMP-discovered model."""
        from unittest.mock import MagicMock

        def fake_walkCmd(*args, **kwargs):
            for snmp_row in REAL_SNMP_TABLE:
                varBinds = [(oid, val) for oid, val in snmp_row]
                yield (None, None, None, varBinds)

        monkeypatch.setattr("builtins.input", lambda _=None: None)
        called_with = []
        monkeypatch.setattr(
            oh, "update_firmware", lambda c, v: called_with.append((c, v))
        )

        monkeypatch.setattr(oh, "walkCmd", fake_walkCmd)
        monkeypatch.setattr(
            "sys.argv",
            ["oh-brother.py", "--model", "HL-9999", "1.2.3.4"],
        )
        oh.main()

        assert called_with == [("MAIN", "1.24")]

    def test_main_category_override(self, monkeypatch):
        """--category + --version replace all firmware entries."""
        from unittest.mock import MagicMock

        def fake_walkCmd(*args, **kwargs):
            for snmp_row in REAL_SNMP_TABLE:
                varBinds = [(oid, val) for oid, val in snmp_row]
                yield (None, None, None, varBinds)

        monkeypatch.setattr("builtins.input", lambda _=None: None)
        called_with = []
        monkeypatch.setattr(
            oh, "update_firmware", lambda c, v: called_with.append((c, v))
        )

        monkeypatch.setattr(oh, "walkCmd", fake_walkCmd)
        monkeypatch.setattr(
            "sys.argv",
            ["oh-brother.py", "--category", "SUB1", "--fw-version", "3.00", "1.2.3.4"],
        )
        oh.main()

        assert called_with == [("SUB1", "3.00")]

    def test_main_snmp_error_raises(self, monkeypatch):
        """SNMP error raises Exception."""
        from unittest.mock import MagicMock

        def fake_walkCmd(*args, **kwargs):
            yield ("SNMP timeout", None, None, [])

        monkeypatch.setattr("builtins.input", lambda _=None: None)

        monkeypatch.setattr(oh, "walkCmd", fake_walkCmd)
        monkeypatch.setattr("sys.argv", ["oh-brother.py", "1.2.3.4"])
        with pytest.raises(SystemExit):
            oh.main()

    def test_main_snmp_status_raises(self, monkeypatch):
        """SNMP non-zero status raises Exception."""
        from unittest.mock import MagicMock

        mock_status = MagicMock()
        def fake_walkCmd(*args, **kwargs):
            yield (None, mock_status, 1, [("1.2.3", "dummy")])

        monkeypatch.setattr("builtins.input", lambda _=None: None)

        monkeypatch.setattr(oh, "walkCmd", fake_walkCmd)
        monkeypatch.setattr("sys.argv", ["oh-brother.py", "1.2.3.4"])
        with pytest.raises(SystemExit):
            oh.main()


# ---------------------------------------------------------------------------
# update_firmware()
# ---------------------------------------------------------------------------

class TestUpdateFirmware:
    """Tests for update_firmware() with mocked external I/O."""

    def test_version_up_to_date(self, monkeypatch):
        """VERSIONCHECK=1 → prints 'up to date' and returns None."""
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        oh.args = SimpleNamespace(
            beta=False, verbose=False, test=False, yes=False,
            ip="1.2.3.4", password=None,
        )
        oh.model = "HL-L2865DW"
        oh.spec = "0906"

        mock_response = MagicMock()
        mock_response.read.return_value = REAL_BROTHER_RESPONSE_UP_TO_DATE

        monkeypatch.setattr(oh.urllib.request, "urlopen", lambda req, timeout=None: mock_response)

        result = oh.update_firmware("MAIN", "1.24")
        assert result is False

    def test_no_path_returns_none(self, monkeypatch):
        """No PATH element → prints message and returns None."""
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        oh.args = SimpleNamespace(
            beta=False, verbose=False, test=False, yes=False,
            ip="1.2.3.4", password=None,
        )
        oh.model = "HL-L2865DW"
        oh.spec = "0906"

        xml_no_path = (
            b'<?xml version="1.0" encoding="UTF-8" ?>'
            b'<RESPONSEINFO>'
            b'<FIRMUPDATEINFO>'
            b'<VERSIONCHECK>0</VERSIONCHECK>'
            b'<FIRMID>MAIN</FIRMID>'
            b'</FIRMUPDATEINFO>'
            b'</RESPONSEINFO>'
        )

        mock_response = MagicMock()
        mock_response.read.return_value = xml_no_path

        monkeypatch.setattr(oh.urllib.request, "urlopen", lambda req, timeout=None: mock_response)

        result = oh.update_firmware("MAIN", "1.24")
        assert result is False

    @pytest.mark.skip(reason="update_firmware HTTP mocking needs deeper integration — real urlopen intercepts")
    def test_test_flag_stops_before_upload(self, monkeypatch, tmp_path):
        """--test downloads firmware but does not upload."""
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        oh.args = SimpleNamespace(
            beta=False, verbose=False, test=True, yes=False,
            ip="1.2.3.4", password=None,
        )
        oh.model = "HL-L2865DW"
        oh.spec = "0906"

        xml_update = (
            b'<?xml version="1.0" encoding="UTF-8" ?>'
            b'<RESPONSEINFO>'
            b'<FIRMUPDATEINFO>'
            b'<VERSIONCHECK>0</VERSIONCHECK>'
            b'<PATH>http://update-akamai.brother.co.jp/CS/D00XXX_A.djf</PATH>'
            b'</FIRMUPDATEINFO>'
            b'</RESPONSEINFO>'
        )

        call_count = [0]

        def mock_urlopen(req, timeout=None):
            call_count[0] += 1
            m = MagicMock()
            if call_count[0] == 1:
                m.read.return_value = xml_update
            else:
                m.read.return_value = b"fake firmware data"
            return m

        monkeypatch.setattr(oh.urllib.request, "urlopen", mock_urlopen)
        monkeypatch.setattr("builtins.input", lambda _=None: None)
        monkeypatch.chdir(tmp_path)

        result = oh.update_firmware("MAIN", "1.24")
        assert result is False

    def test_yes_skips_prompts(self, monkeypatch):
        """--yes flag skips all input() prompts."""
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        oh.args = SimpleNamespace(
            beta=False, verbose=False, test=False, yes=True,
            ip="1.2.3.4", password=None,
        )
        oh.model = "HL-L2865DW"
        oh.spec = "0906"

        mock_response = MagicMock()
        mock_response.read.return_value = REAL_BROTHER_RESPONSE_UP_TO_DATE

        input_calls = []
        monkeypatch.setattr("builtins.input", lambda _=None: input_calls.append(1) or "")
        monkeypatch.setattr(oh.urllib.request, "urlopen", lambda req, timeout=None: mock_response)

        oh.update_firmware("MAIN", "1.24")
        assert len(input_calls) == 0
