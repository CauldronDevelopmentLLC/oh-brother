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
        "-o",
        "--fw-dir",
        type=Path,
        dest="fw_dir",
        default=".",
        help="Directory, where the firmware will be downloaded (default: '%(default)s').",
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
        help=(
            "Do no install update but download firmware and save it"
            " under the directory path given with --fw-dir."
        ),
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
                        "Do you want to open an issue on Github? [yN] ", color="yellow"
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

    try:
        with GitHubIssueReporter(
            logger=LOGGER,
            issue_url=ISSUE_URL,
            handler_cb=handler_cb,
        ) as issue_reporter:
            run(issue_reporter)
    except KeyboardInterrupt:
        print()
        LOGGER.critical("Quit")
        sys.exit(0)


def run(issue_reporter: GitHubIssueReporter):
    """Do a firmware upgrade."""
    args = parse_args()

    issue_reporter.set_context_data("--community", args.community)
    issue_reporter.set_context_data("--fw-dir", str(args.fw_dir))
    issue_reporter.set_context_data("--os", args.os)
    issue_reporter.set_context_data("--download-only", args.download_only)
    issue_reporter.set_context_data("--debug", args.debug)

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

    if printer_ip:
        issue_reporter.set_context_data("--printer", str(printer_ip))

    if use_snmp:
        LOGGER.info("Querying printer info via SNMP.")
        assert printer_ip, "Printer IP is required but not given."
        printer_info = get_snmp_info(target=printer_ip, community=args.community)
    else:
        printer_info = SNMPPrinterInfo(
            model=args.model,
            serial=args.serial,
            spec=args.spec,
            fw_versions=args.fw_versions,
        )

    if printer_info.model:
        issue_reporter.set_context_data("--model", printer_info.model)

    if printer_info.serial:
        issue_reporter.set_context_data("--serial", printer_info.serial)

    if printer_info.spec:
        issue_reporter.set_context_data("--spec", printer_info.spec)

    if printer_info.fw_versions:
        issue_reporter.set_context_data(
            "--fw-versions",
            [str(fw_version) for fw_version in printer_info.fw_versions],
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
        LOGGER.info("Try to get information for firmware part %s", fw_part)

        latest_version, download_url = get_download_url(
            printer_info=printer_info,
            firmid=str(fw_part.firmid),
            reported_os=args.os,
        )

        if not download_url:
            continue

        assert download_url

        LOGGER.debug("  Download URL is %s", download_url)
        LOGGER.success("Downloading firmware file.")
        fw_file_path = download_fw(
            url=download_url,
            dst_dir=args.fw_dir,
            printer_model=printer_info.model,
            fw_part=fw_part,
            latest_version=latest_version,
        )

        if args.download_only:
            LOGGER.info("Skipping firmware upload due to --download-only")
        else:
            LOGGER.info("Uploading firmware file to printer via jetdirect.")
            assert printer_ip, "Printer IP is required but not given"
            try:
                upload_fw(
                    target=printer_ip, port=upload_port, fw_file_path=fw_file_path
                )
            except OSError as err:
                LOGGER.error(
                    "Could not upload firmware %s to update part %s: %s",
                    fw_file_path,
                    fw_part,
                    str(err),
                )
                continue

            input("Continue? ")

    LOGGER.success("Done.")


if __name__ == "__main__":
    main()
