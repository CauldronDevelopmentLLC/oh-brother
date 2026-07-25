# AGENTS.md — oh-brother

> AI agent guidance. Read before writing code.

## What this is

Cross-platform Python 3 CLI to update Brother printer firmware. SNMP discovery → XML query to Brother's Japan server → HTTP download → TCP 9100 or FTP upload.

- **Repo:** https://github.com/rvasilev/oh-brother
- **Upstream:** https://github.com/CauldronDevelopmentLLC/oh-brother (commit `a9c8b10`)
- **License:** GPLv2
- **Lines:** 339, single file (`oh-brother.py`)
- **Branch:** `dev` (refactored with test suite)

## Architecture

```
User → CLI args (IP, --password, --category, --model, --test, --beta, --yes)
  │
  ├─[1] SNMP walk (OID 1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2)
  │     → parse_snmp_table() → model, serial, spec, firmwares
  │
  ├─[2] XML POST — build_firmware_xml() → Brother API
  │     → parse_brother_response() → version check, firmware URL (PATH)
  │
  ├─[3] HTTP GET firmware blob (.djf/.upd) → CWD
  │     ⚠ Known gap: PATH not returned for newer models (HL-L2865DW, HL-L2xxx series)
  │
  └─[4] Upload to printer
        ├─ TCP port 9100 (default, passwordless — Raw Port must be enabled)
        └─ FTP (when --password set — admin password as username)
```

## Refactored structure

Original upstream had no functions beyond `update_firmware()` and `sslwrap()` (dead). Fork extracted 3 pure, testable functions:

| Function | Lines | Purpose |
|---|---|---|
| `parse_snmp_table(table, verbose=False)` | 59-91 | Parse SNMP walk result → dict with serial, model, spec, firmwares |
| `build_firmware_xml(model, spec, cat, ver, beta=False)` | 94-115 | Build XML request for Brother API → bytes |
| `parse_brother_response(xml_bytes)` | 118-135 | Parse Brother API XML → dict with version_check, firmware_url |
| `update_firmware(cat, version)` | 180-271 | Orchestration: XML build → HTTP POST → parse → download → upload |
| `main()` | 274-339 | Entry point: argparse → SNMP walk → parse → update loop |
| `sslwrap` / `bar` | 168-177 | Dead code (retained from upstream, never called) |

Module is import-safe: `if __name__ == '__main__':` guard at line 339.

## Key external systems

| System | Protocol | Notes |
|---|---|---|
| Brother firmware API | HTTPS XML | `firmverup.brother.co.jp`, requires `User-Agent: BrHttpc/1.00` |
| Brother firmware CDN | HTTP | `update-akamai.brother.co.jp/CS/` — `.djf` / `.upd` files |
| Printer SNMP | UDP 161 | Community string (default `public`), Brother enterprise OID |
| Printer raw port | TCP 9100 | Must be enabled in printer web UI |
| Printer FTP | TCP 21 | Admin password sent as FTP username (Brother quirk) |

## Code conventions

- **Python 3.10** runtime (pysnmp `oneliner` requires `asyncore`, removed in 3.12)
- **Procedural style** — pure functions extracted, no classes
- **No external HTTP libraries** — stdlib `urllib` only
- **XML parsing** — stdlib `xml.etree.ElementTree`
- **Firmware downloads** go to CWD (upstream) — temp dir migration pending
- **Import-safe** — `if __name__ == '__main__':` guard prevents side effects on import
- **Test imports** use `importlib.util.spec_from_file_location` because source filename has a hyphen

## CLI reference

```
./oh-brother.py [OPTIONS] <printer IP>

  -t, --test       Check firmware availability (no upload)
  -c, --category   Force a specific firmware category (MAIN, SUB1, etc.)
  -m, --model      Force a specific printer model
  -f, --version    Force a specific firmware version (requires --category)
  -v, --verbose    Verbose output (SNMP dump, XML request/response)
  --beta           Query for beta firmware (INSPECTMODE=1)
  -p, --password   Upload via FTP using printer admin password
  -C, --community  SNMP community string (default: public)
  -y, --yes        Skip all confirmation prompts (non-interactive mode)
```

## Testing

**45 tests, 6 classes.** Run: `python3 -m pytest tests/ -v`

| Class | Tests | What it covers |
|---|---|---|
| `TestParseSnmpTable` | 7 | Real printer data, multi-FW, ordering edge cases, empty table, verbose |
| `TestBuildFirmwareXml` | 6 | XML structure, FIRM→MAIN mapping, IFAX→MAIN mapping, beta flag, bytes output |
| `TestParseBrotherResponse` | 5 | Up-to-date, update available, no PATH, no VERSIONCHECK, empty response |
| `TestCLI` | 5 (parameterized) | All boolean flags, string args, category+version combo, IP required |
| `TestMainSmoke` | 5 | SNMP→parse pipeline, model override, category override, SNMP error/status |
| `TestUpdateFirmware` | 3 + 1 skip | Version up-to-date, no PATH return, --yes skips prompts |

**Test infrastructure:**
- `tests/conftest.py` — mocks pysnmp at `sys.modules` level so tests run on Python ≥3.12
- `tests/test_oh_brother.py` — imports module via `importlib.util` (filename has hyphen)
- Fixture data from real HL-L2865DW at 192.168.88.65
- `test_test_flag_stops_before_upload` is skipped — HTTP download mocking needs deeper `urllib.request` interception

```bash
# Full test run
python3 -m pytest tests/ -v

# With coverage
python3 -m pytest tests/ --cov=oh-brother.py --cov-report=term-missing

# Real printer integration test
echo "" | ~/.pyenv/versions/3.10.14/bin/python3 oh-brother.py --test --yes 192.168.88.65
```

Roman's test printer: **Brother HL-L2865DW** at `192.168.88.65`, SPEC `0906`, MAIN `1.24`, serial `E83118M5N186598`.

## Known issues (upstream a9c8b10)

| Issue | Location | Severity | Status |
|---|---|---|---|
| `pysnmp.oneliner` needs `asyncore` | Line 17 | **Critical** — breaks on Python ≥3.12 | Migration planned (hlapi, ~15 lines) |
| Dead `ssl.wrap_socket` monkey-patch | Lines 166-175 | **None** — unused | Retained for upstream compat |
| Bare `urlopen()` — no timeout, no error handling | Lines 198, 222 | High — hangs on network failure | Unfixed |
| Downloads to CWD not temp dir | Line 216 | Medium | Unfixed |
| `socket.sendfile()` — may fail on some platforms | Line 253 | Medium | Unfixed |
| FTP no timeout, narrow exception catch | Lines 260-264 | Medium | Unfixed |
| No `--dry-run` flag | — | Low — `--test` stops before upload but not before download | Unfixed |
| No empty-file check before upload | After download | Medium | Unfixed |
| `--version` default `B0000000000` is a magic sentinel | Line 152 | Low | Unfixed |

## Python 3.12+ migration plan

### Problem
`pysnmp.entity.rfc3413.oneliner` (line 17) was removed in pysnmp ≥6.2, which dropped `asyncore` to support Python 3.12+.

### Solution
Replace the old `oneliner` API with `pysnmp.hlapi.v1arch` (same package, maintained by lextudio). Only ~15 lines change in `main()` — the SNMP walk call plus error handling. The 3 pure functions (`parse_snmp_table`, `build_firmware_xml`, `parse_brother_response`) don't change at all.

**Before:**
```python
from pysnmp.entity.rfc3413.oneliner import cmdgen
cg = cmdgen.CommandGenerator()
error, status, index, table = cg.nextCmd(
    cmdgen.CommunityData(args.community),
    cmdgen.UdpTransportTarget((args.ip, 161)),
    '1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2')
```

**After:**
```python
from pysnmp.hlapi.v1arch import *
iterator = nextCmd(
    SnmpEngine(),
    CommunityData(args.community),
    UdpTransportTarget((args.ip, 161)),
    ContextData(),
    ObjectType(ObjectIdentity('1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2')),
    lexicographicMode=False)
# varBinds format: [(ObjectType, payload), ...] instead of [(name, value), ...]
```

### Steps
1. Pin `pysnmp >= 6.2` in requirements.txt
2. Rewrite SNMP walk in `main()` (~15 lines)
3. Update `conftest.py` to mock `pysnmp.hlapi.v1arch` instead of `pysnmp.entity.rfc3413.oneliner`
4. Adapt `TestMainSmoke` to use hlapi-shaped mock returns
5. Run test suite (45 tests) — all must stay green
6. Integration test: `--test --yes` against HL-L2865DW

### Risk
**Low.** Same OID walk, same wire protocol, same Brother API calls. Only the Python API surface changes. The printer doesn't care which SNMP library you use. Test coverage exists on the orchestration path (`TestMainSmoke`).

## Changelog (fork, `dev` branch)

| Commit/Milestone | What |
|---|---|
| Phase 0 | Added `if __name__ == '__main__':` guard, extracted 3 pure functions |
| Phase 0.5 | Added `-y`/`--yes` flag (non-interactive mode) |
| Phase 1 | 31 initial tests (parse, XML, CLI) |
| Phase 1.5 | 45 tests: added `TestMainSmoke` (5), `TestUpdateFirmware` (4), collapsed CLI to parameterized |
