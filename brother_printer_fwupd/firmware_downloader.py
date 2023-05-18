"""Logic to download the correct firmware from the official Brother server."""
import typing
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .utils import LOGGER

if typing.TYPE_CHECKING:
    from .models import SNMPPrinterInfo

FW_UPDATE_URL = (
    "https://firmverup.brother.co.jp/kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate"
)


def get_download_url(
    printer_info: "SNMPPrinterInfo",
    reported_os: str,
    firmid: str = "MAIN",
) -> str | None:
    """Get the firmware download URL for the target printer."""
    firm_info = ""

    for fw_info in printer_info.fw_versions:
        firm_info += f"""
        <FIRM>
            <ID>{fw_info.firmid}</ID>
            <VERSION>{fw_info.firmver}</VERSION>
        </FIRM>
        """

    api_data = f"""
<REQUESTINFO>
    <FIRMUPDATETOOLINFO>
        <FIRMCATEGORY>{firmid}</FIRMCATEGORY>
        <OS>{reported_os}</OS>
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
    LOGGER.debug(
        "Sending POST request to %s with following content:\n%s",
        FW_UPDATE_URL,
        api_data,
    )
    resp = requests.post(
        FW_UPDATE_URL, data=api_data, headers={"Content-Type": "text/xml"}
    )
    resp.raise_for_status()
    LOGGER.debug("Response:\n%s", resp.text)

    resp_xml = BeautifulSoup(resp.text, "xml")
    versioncheck = resp_xml.select("VERSIONCHECK")
    if len(versioncheck) == 1:
        versioncheck_val = versioncheck[0].text
        if versioncheck_val == "0":
            LOGGER.info("It seems that a firmware update is required for %s", firmid)
        elif versioncheck_val == "1":
            LOGGER.success("Firmware part %s seems to be up to date.", firmid)
            return None
        else:
            raise ValueError(f"Unknown versioncheck response for firmid={firmid}.")

    path = resp_xml.find("PATH")
    if not path:
        LOGGER.warning("Did not receive download url for %s.", firmid)
        LOGGER.warning("Either this firmware part is up to date or there is a bug.")
        return None

    return path.text


def download_fw(url: str, dst: Path = Path("firmware.djf")):
    """Download the firmware."""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))
    size_written = 0
    chunk_size = 8192

    with dst.open("wb") as out:
        for chunk in resp.iter_content(chunk_size):
            size_written += out.write(chunk)
            progress = size_written / total_size * 100
            print(f"\r{progress: 5.1f} %", end="", flush=True)

    print()
