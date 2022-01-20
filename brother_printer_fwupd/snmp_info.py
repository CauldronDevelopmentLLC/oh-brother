"""Logic to receive info via SNMP."""

import ipaddress
import re
import sys

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    nextCmd,
)

from .models import FWInfo, IPAddress, SNMPPrinterInfo
from .utils import print_error

SNMP_OID = "iso.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2"

SNMP_RE = re.compile(r'(?P<name>[A-Z]+) ?= ?"(?P<value>.*)"')
UDP_SNMP_PORT = 161


def get_snmp_info(
    target: IPAddress,
    community: str = "public",
) -> SNMPPrinterInfo:
    """
    Get the required info about the printer via SNMP.

    Equals to:
    snmpwalk -v 2c -c public lp.local iso.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2
    :return: A tuple of:
        - the model / series
        - the spec
        - a list of firmware infos, which are tuples of the id and their version.
        (Whatever this information means).
    """
    printer_info = SNMPPrinterInfo()
    fw_info = FWInfo()

    if isinstance(target, str):
        target = ipaddress.ip_address(target)

    if isinstance(target, ipaddress.IPv6Address):
        udp_target = Udp6TransportTarget((str(target), UDP_SNMP_PORT))
    elif isinstance(target, ipaddress.IPv4Address):
        udp_target = UdpTransportTarget((str(target), UDP_SNMP_PORT))
    else:
        assert False

    for error_indication, error_status, error_index, var_binds in nextCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=0),
        udp_target,
        ContextData(),
        ObjectType(ObjectIdentity(SNMP_OID)),
    ):

        if error_indication:
            print_error(error_indication)
            sys.exit(1)
        elif error_status:
            position = var_binds[int(error_index) - 1][0] if error_index else "?"
            print_error(f"{error_status.prettyPrint()} at {position}")
            sys.exit(1)
        else:
            # TODO this is ugly
            var_bind = var_binds[0]
            data = str(var_bind[1]).strip()

            if not data:
                break
            match = SNMP_RE.match(data)

            if not match:
                print_error(f'Data "{data}" does not match the regex.')
                sys.exit(1)
            name = match.group("name")
            value = match.group("value")

            if name == "MODEL":
                printer_info.model = value
            elif name == "SERIAL":
                printer_info.serial = value
            elif name == "SPEC":
                printer_info.spec = value
            elif name in ("FIRMID", "FIRMVER"):
                if value:
                    setattr(fw_info, name.lower(), value)

                    if fw_info.is_complete:
                        printer_info.fw_versions.append(fw_info)
                        fw_info = FWInfo()

    if not fw_info.is_empty:
        print_error(
            f"Did not receive firmid or firmver from printer via SNMP: {fw_info=}"
        )
        sys.exit(1)

    return printer_info
