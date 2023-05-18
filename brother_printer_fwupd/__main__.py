#!/usr/bin/env python3
"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

import argparse
import logging
import sys
import typing
import webbrowser
from pathlib import Path

import termcolor

from . import ISSUE_URL
from .autodiscover_printer import PrinterDiscoverer
from .firmware_downloader import download_fw, get_download_url
from .firmware_uploader import upload_fw
from .models import FWInfo, SNMPPrinterInfo
from .snmp_info import get_snmp_info
from .utils import (
    CONSOLE_LOG_HANDLER,
    LOGGER,
    GitHubIssueReporter,
    get_running_os,
    gooey_if_exists,
)

if typing.TYPE_CHECKING:
    from .models import IPAddress


RUNNING_OS = get_running_os()


@gooey_if_exists
def parse_args():
    """Parse command line args."""
    parser = argparse.ArgumentParser(
        prog=__file__,
        description=__doc__.strip().splitlines()[0],
    )
    parser.add_argument(
        "-p",
        "--printer",
        dest="printer",
        metavar="host",
        default=None,
        help="IP Address or hostname of the printer (default: autodiscover via mdns).",
    )
    parser.add_argument(
        "--model",
        dest="model",
        type=str,
        help="Skip SNMP scanning by directly specifying the printer model.",
    )
    parser.add_argument(
        "--serial",
        dest="serial",
        type=str,
        help="Skip SNMP scanning by directly specifying the printer serial.",
    )
    parser.add_argument(
        "--spec",
        dest="spec",
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
        "-c",
        "--community",
        dest="community",
        default="public",
        help="SNMP Community string for the printer (default: '%(default)s').",
    )
    parser.add_argument(
        "-f",
        "-o",
        "--fw-file",
        type=Path,
        dest="fw_file",
        default="firmware.djf",
        help="File name for the downloaded firmware (default: '%(default)s').",
    )
    parser.add_argument(
        "--os",
        dest="os",
        type=str.upper,
        default=RUNNING_OS,
        choices=["WINDOWS", "MAC", "LINUX"],
        help="Operating system to report when downloading firmware (default: '%(default)s').",
    )
    parser.add_argument(
        "--download-only",
        dest="download_only",
        action="store_true",
        help="Do no install update but download firmware and save it unter the path given with --fw-file.",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print debug messages",
    )

    return parser.parse_args()


def main():
    """Run the program."""

    def handler_cb(report_url: str):
        LOGGER.error("This might be a bug.")

        while True:
            ret = (
                input(
                    termcolor.colored(
                        "Do you want open an issue? [yN] ", color="yellow"
                    )
                )
                .strip()
                .lower()
            )

            if ret.lower() == "y":
                webbrowser.open(report_url)

                return
            elif ret.lower() == "n" or not ret:
                return

    with GitHubIssueReporter(
        logger=LOGGER,
        issue_url=ISSUE_URL,
        handler_cb=handler_cb,
    ):
        run()


def run():
    """Do a firmware upgrade."""
    args = parse_args()

    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    printer_ip: typing.Optional["IPAddress"] = args.printer
    upload_port: int | None = None
    use_snmp = (
        not args.model or not args.serial or not args.spec or not args.fw_versions
    )
    printer_ip_required = use_snmp or not args.download_only

    if not printer_ip and printer_ip_required:
        LOGGER.info("Discovering printer via MDNS.")
        discoverer = PrinterDiscoverer()
        mdns_printer_info = discoverer.run_cli()

        if mdns_printer_info:
            printer_ip = mdns_printer_info.ip_addr
            upload_port = mdns_printer_info.port

    if not printer_ip and printer_ip_required:
        LOGGER.critical("No printer given or found.")
        sys.exit(1)

    assert printer_ip

    if use_snmp:
        LOGGER.info("Querying printer info via SNMP.")
        printer_info = get_snmp_info(target=printer_ip, community=args.community)
    else:
        printer_info = SNMPPrinterInfo(
            model=args.model,
            serial=args.serial,
            spec=args.spec,
            fw_versions=args.fw_versions,
        )

    versions_str = ", ".join(str(fw_info) for fw_info in printer_info.fw_versions)
    LOGGER.success(
        "%s %s with following firmware version(s): %s",
        "Detected" if use_snmp else "Using",
        printer_info.model,
        versions_str,
    )
    LOGGER.info("Querying firmware download URL from Brother update API.")
    download_url: str | None = None

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

        if args.download_only:
            LOGGER.info("Skipping firmware upload due to --download-only")
        else:
            LOGGER.info("Uploading firmware file to printer via jetdirect.")
            upload_fw(target=printer_ip, port=upload_port, file_path=args.fw_file)
            input("Continue? ")

    LOGGER.success("Done.")


if __name__ == "__main__":
    main()
