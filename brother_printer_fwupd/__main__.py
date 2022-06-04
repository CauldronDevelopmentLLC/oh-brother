#!/usr/bin/env python3
"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

import argparse
import sys
import typing
import logging

PrinterDiscoverer: typing.Optional[typing.Type] = None
try:
    from .autodiscover_printer import PrinterDiscoverer
except ImportError:
    pass

from .firmware_downloader import download_fw, get_download_url
from .firmware_uploader import upload_fw
from .snmp_info import get_snmp_info
from .utils import gooey_if_exists, LOGGER
from .models import FWInfo, SNMPPrinterInfo

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
    parser.add_argument(
        "--model",
        type=str,
        help="Skip SNMP scanning by directly specifying the printer model.",
    )
    parser.add_argument(
        "--serial",
        type=str,
        help="Skip SNMP scanning by directly specifying the printer serial.",
    )
    parser.add_argument(
        "--spec",
        type=str,
        help="Skip SNMP scanning by directly specifying the printer spec.",
    )
    parser.add_argument(
        "--fw",
        "--fw-versions",
        dest="fw_versions",
        nargs="*",
        default=list[FWInfo](),
        type=FWInfo.from_str,
        help="Skip SNMP scanning by directly specifying the firmware parts to update.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug messages",
    )

    return parser.parse_args()


def main():
    """Do a firmware upgrade."""
    args = parse_args()

    LOGGER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    printer_ip: typing.Optional["IPAddress"] = args.printer
    upload_port: typing.Optional[int] = None

    if not printer_ip:
        LOGGER.info("Discovering printer via MDNS.")
        discoverer = PrinterDiscoverer()
        mdns_printer_info = discoverer.run_cli()

        if mdns_printer_info:
            printer_ip = mdns_printer_info.ip_addr
            upload_port = mdns_printer_info.port

    if not printer_ip:
        LOGGER.critical("No printer given or found.")
        sys.exit(1)

    if args.model and args.serial and args.spec and args.fw_versions:
        printer_info = SNMPPrinterInfo(
            model=args.model,
            serial=args.serial,
            spec=args.spec,
            fw_versions=args.fw_versions,
        )
        snmp_used = False
    else:
        LOGGER.info("Querying printer info via SNMP.")
        printer_info = get_snmp_info(target=printer_ip, community=args.community)
        snmp_used = True

    versions_str = ", ".join(str(fw_info) for fw_info in printer_info.fw_versions)
    LOGGER.success(
        "%s %s with following firmware version(s): %s",
        "Detected" if snmp_used else "Using",
        printer_info.model,
        versions_str,
    )
    LOGGER.info("Querying firmware download URL from Brother update API.")
    download_url: typing.Optional[str] = None

    for fw_part in printer_info.fw_versions:
        download_url = get_download_url(
            printer_info=printer_info,
            firmid=str(fw_part.firmid),
            reported_os=args.os,
        )

        if not download_url:
            continue

        LOGGER.debug("  Download URL is %s", download_url)
        LOGGER.success("Downloading firmware file.")
        download_fw(url=download_url, dst=args.fw_file)
        LOGGER.info("Uploading firmware file to printer via jetdirect.")
        upload_fw(target=printer_ip, port=upload_port, file_name=args.fw_file)
        input("Continue? ")

    LOGGER.success("Done.")


if __name__ == "__main__":
    main()
