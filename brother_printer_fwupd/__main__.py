#!/usr/bin/env python3
"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

import argparse
import sys
import typing

from .autodiscover_printer import PrinterDiscoverer
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
    parser.add_argument(
        "-h",
        "--host",
        metavar="printer",
        default=None,
        help="IP Address or hostname of the printer (default: autodiscover via mdns).",
    )
    parser.add_argument(
        "--community",
        "-c",
        default="public",
        help="SNMP Community string for the printer (default: 'public').",
    )
    parser.add_argument(
        "--fw-file",
        "-f",
        default="firmware.djf",
        help="File name for the downloaded firmware (default: 'firmware.djf').",
    )

    return parser.parse_args()


def main():
    """Do a firmware upgrade."""
    args = parse_args()

    printer_ip: typing.Optional["IPAddress"] = args.printer
    upload_port: typing.Optional[int] = None

    if printer_ip:
        print_info("Querying printer info via SNMP.")
        discoverer = PrinterDiscoverer()
        mdns_printer_info = discoverer.run_cli()
        printer_ip = mdns_printer_info.ip_addr
        upload_port = mdns_printer_info.port

    if not printer_ip:
        print_error("No printer given or found.")
        sys.exit(1)

    print_info("Querying printer info via SNMP.")
    printer_info = get_snmp_info(target=args.printer, community=args.community)
    versions_str = ", ".join(
        f"{firmid} @ {firmver}" for firmid, firmver in printer_info.fw_versions
    )
    print_info(
        f" Detected {printer_info.model} with following firmware version(s): {versions_str}"
    )
    print_info("Querying firmware download URL from brother update API.")
    download_url = get_download_url(printer_info)
    print_debug(f"  Download URL is {download_url}")
    print_success("Downloading firmware file.")
    download_fw(url=download_url, dst=args.fw_file)
    print_info("Uploading firmware file to printer via jetdirect.")
    upload_fw(target=printer_ip, port=upload_port, file_name=args.fw_file)
    print_success("Done.")


if __name__ == "__main__":
    main()
