#!/usr/bin/env python3
"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

import argparse
import sys
import typing

try:
    from .autodiscover_printer import PrinterDiscoverer
except ImportError:
    PrinterDiscoverer = None

from .firmware_downloader import download_fw, get_download_url
from .firmware_uploader import upload_fw
from .snmp_info import get_snmp_info
from .utils import gooey_if_exists, print_debug, print_error, print_info, print_success

if typing.TYPE_CHECKING:
    from .models import IPAddress


@gooey_if_exists
def parse_args():
    """Parse command line args."""
    parser = argparse.ArgumentParser(
        prog=__file__,
        description=__doc__.strip().splitlines()[0],
    )
    if PrinterDiscoverer is None:
        discovery_available = False
        blurb = "required, because zeroconf is not available"
    else:
        discovery_available = True
        blurb = "default: autodiscover via mdns"
    parser.add_argument(
        "-p",
        "--printer",
        required=not discovery_available,
        metavar="host",
        default=None,
        help=f"IP Address or hostname of the printer ({blurb}).",
    )
    parser.add_argument(
        "--community",
        "-c",
        default="public",
        help="SNMP Community string for the printer (default: '%(default)s').",
    )
    parser.add_argument(
        "--fw-file",
        "-f",
        default="firmware.djf",
        help="File name for the downloaded firmware (default: '%(default)s').",
    )
    parser.add_argument(
        "--os",
        type=str.upper,
        choices=["WINDOWS", "MAC", "LINUX"],
        help="Operating system to report when downloading firmware (default: autodetect)",
    )

    return parser.parse_args()


def main():
    """Do a firmware upgrade."""
    args = parse_args()

    printer_ip: typing.Optional["IPAddress"] = args.printer
    upload_port: typing.Optional[int] = None

    if not printer_ip:
        print_info("Querying printer info via SNMP.")
        discoverer = PrinterDiscoverer()
        mdns_printer_info = discoverer.run_cli()

        if mdns_printer_info:
            printer_ip = mdns_printer_info.ip_addr
            upload_port = mdns_printer_info.port

    if not printer_ip:
        print_error("No printer given or found.")
        sys.exit(1)

    print_info("Querying printer info via SNMP.")
    printer_info = get_snmp_info(target=printer_ip, community=args.community)
    versions_str = ", ".join(
        f"{fw_info.firmid} @ {fw_info.firmver}" for fw_info in printer_info.fw_versions
    )
    print_info(
        f" Detected {printer_info.model} with following firmware version(s): {versions_str}"
    )
    print_info("Querying firmware download URL from Brother update API.")
    download_url: typing.Optional[str] = None

    for fw_part in printer_info.fw_versions:
        download_url = get_download_url(
            printer_info=printer_info,
            firmid=str(fw_part.firmid),
            reported_os=args.os,
        )

        if not download_url:
            continue

        print_debug(f"  Download URL is {download_url}")
        print_success("Downloading firmware file.")
        download_fw(url=download_url, dst=args.fw_file)
        print_info("Uploading firmware file to printer via jetdirect.")
        upload_fw(target=printer_ip, port=upload_port, file_name=args.fw_file)
        input("Continue? ")

    print_success("Done.")


if __name__ == "__main__":
    main()
