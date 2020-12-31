"""Logic to download the correct firmware from the official Brother server."""
import sys
import typing

import requests
from bs4 import BeautifulSoup

from .utils import print_error

if typing.TYPE_CHECKING:
    from .models import SNMPPrinterInfo

FW_UPDATE_URL = (
    "https://firmverup.brother.co.jp/kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate"
)


def get_download_url(printer_info: "SNMPPrinterInfo") -> str:
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
    resp_xml = BeautifulSoup(resp.text, "xml")
    path = resp_xml.find("PATH")
    if not path:
        print_error("Did not receive any url.")
        print_error("Maybe the firmware is already up to date or there is a bug.")
        print_error("This is the response of brothers update API:")
        print_error(resp.text)
        sys.exit(1)

    return path.text


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
