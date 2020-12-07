#!/usr/bin/env python3
"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

# pylint: disable=R1705

import argparse
import re
import socket
import sys
import typing
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    nextCmd,
)

try:
    from gooey import Gooey
except ImportError:
    Gooey = None

FW_UPDATE_URL = (
    "https://firmverup.brother.co.jp/kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate"
)
SNMP_OID = "iso.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2"

SNMP_RE = re.compile(r'(?P<name>[A-Z]+) ?= ?"(?P<value>.+)"')


@dataclass
class PrinterInfo:
    """Information about a printer."""

    model: typing.Optional[str] = field(default=None)
    serial: typing.Optional[str] = field(default=None)
    spec: typing.Optional[str] = field(default=None)
    fw_versions: typing.List[typing.Tuple[str, str]] = field(default_factory=list)


def gooey_if_exists(func):
    """Make the app graphical, if gooey is installed."""

    if Gooey:
        return Gooey(func)
    else:
        return func


@gooey_if_exists
def parse_args():
    """Parse command line args."""
    parser = argparse.ArgumentParser(
        prog=__file__,
        description=__doc__.strip().splitlines()[0],
    )
    parser.add_argument(
        "printer",
        help="IP Address or hostname of the printer.",
    )
    parser.add_argument(
        "--community",
        "-c",
        default="public",
        help="SNMP Community string for the printer.",
    )
    parser.add_argument(
        "--fw-file",
        "-f",
        default="firmware.djf",
        help="File name for the downloaded firmware.",
    )

    return parser.parse_args()


def get_snmp_info(target: str, community: str = "public") -> PrinterInfo:
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
    firmid = None
    firmver = None
    printer_info = PrinterInfo()

    for error_indication, error_status, error_index, var_binds in nextCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=0),
        UdpTransportTarget((target, 161)),
        ContextData(),
        ObjectType(ObjectIdentity(SNMP_OID)),
    ):

        if error_indication:
            print("[!]", error_indication, file=sys.stderr)
            sys.exit(1)
        elif error_status:
            position = var_binds[int(error_index) - 1][0] if error_index else "?"
            print(f"[!] {error_status.prettyPrint()} at {position}", file=sys.stderr)
            sys.exit(1)
        else:
            # TODO this is ugly
            var_bind = var_binds[0]
            data = str(var_bind[1]).strip()

            if not data:
                break
            match = SNMP_RE.match(data)

            if not match:
                print(f'[!] Data "{data}" does not match the regex.', file=sys.stderr)
                sys.exit(1)
            name = match.group("name")
            value = match.group("value")

            if name == "MODEL":
                printer_info.model = value
            elif name == "SERIAL":
                printer_info.serial = value
            elif name == "SPEC":
                printer_info.spec = value
            elif name == "FIRMID":
                assert not firmver, "[!] Received FIRMVER before FIRMID"
                firmid = value
            elif name == "FIRMVER":
                assert firmid, "[!] Received FIRMVER before FIRMID"
                firmver = value
                printer_info.fw_versions.append((firmid, firmver))
                firmid = None
                firmver = None

    return printer_info


def get_download_url(printer_info: PrinterInfo) -> str:
    """Get the firmware download URL for the target printer. """
    firm_info = ""

    for fw_id, fw_version in printer_info.fw_versions:
        firm_info += f"""
        <FIRM>
            <ID>{fw_id}</ID>
            <VERSION>{fw_version}</VERSION>
        </FIRM>
        """
    api_data = f"""
<REQUESTINFO>
    <FIRMUPDATETOOLINFO>
        <FIRMCATEGORY>MAIN</FIRMCATEGORY>
        <OS>LINUX</OS>
        <INSPECTMODE>1</INSPECTMODE>
    </FIRMUPDATETOOLINFO>

    <FIRMUPDATEINFO>
        <MODELINFO>
            <SERIALNO></SERIALNO>
            <NAME>{printer_info.model}</NAME>
            <SPEC>{printer_info.spec}</SPEC>
            <DRIVER></DRIVER>
            <FIRMINFO>
                {firm_info}
            </FIRMINFO>
        </MODELINFO>
        <DRIVERCNT>1</DRIVERCNT>
        <LOGNO>2</LOGNO>
        <ERRBIT></ERRBIT>
        <NEEDRESPONSE>1</NEEDRESPONSE>
    </FIRMUPDATEINFO>
</REQUESTINFO>
"""
    # curl -X POST -d @hl3040cn-update.xml -H "Content-Type:text/xml"
    resp = requests.post(
        FW_UPDATE_URL, data=api_data, headers={"Content-Type": "text/xml"}
    )
    resp.raise_for_status()
    try:
        resp_xml = BeautifulSoup(resp.text, "xml")
        return resp_xml.find('PATH').text
    except:
        print('[!] Did not receive any url.', file=sys.stderr)
        print('[!] Maybe the firmware is already up to date or there is a bug.', file=sys.stderr)
        print('[!] This is the response of brothers update API:', file=sys.stderr)
        print(resp.text)
        sys.exit(1)


def download_fw(url: str, dst: str = "firmware.djf"):
    """Download the firmware."""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))
    size_written = 0
    chunk_size = 8192

    with open(dst, "wb") as out:
        for chunk in resp.iter_content(chunk_size):
            size_written += out.write(chunk)
            progress = size_written / total_size * 100
            print(f"\r{progress: 5.1f} %", end="", flush=True)

    print()


def upload_fw(target: str, port: int = 9100, file_name: str = "firmware.djf"):
    """
    Upload the firmware to the printer via jetdirect.
    Equals:
    cat LZ5413_P.djf | nc lp.local 9100
    """
    addr_info = socket.getaddrinfo(target, port, 0, 0, socket.SOL_TCP)[0]
    with socket.socket(addr_info[0], addr_info[1], 0) as sock:
        sock.connect(addr_info[4])

        with open(file_name, "rb") as fw_file:
            sock.sendfile(fw_file)


def main():
    """Do a firmware upgrade."""
    args = parse_args()
    print("[i] Querying printer info via SNMP.")
    printer_info = get_snmp_info(target=args.printer, community=args.community)
    print(
        f"[i]   Detected {printer_info.model} with {len(printer_info.fw_versions)} firmware parts."
    )
    print("[i] Querying firmware download URL from brother update API.")
    download_url = get_download_url(printer_info)
    print(f"[i]   Download URL is {download_url}")
    print("[i] Downloading firmware file.")
    download_fw(url=download_url, dst=args.fw_file)
    print("[i] Uploading firmware file to printer via jetdirect.")
    upload_fw(target=args.printer, file_name=args.fw_file)
    print("[i] Done.")


if __name__ == "__main__":
    main()
