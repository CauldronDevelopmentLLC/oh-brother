"""Upload firmware to the brinter."""

import socket
from pathlib import Path

from .models import IPAddress

PORT_SERVICE_NAME = "pdl-datastream"


def upload_fw(
    target: IPAddress,
    port: int | None,
    fw_file_path: Path = Path("firmware.djf"),
):
    """
    Upload the firmware to the printer via PDL Datastream / JetDirect.

    Equals:
    ```
    cat LZ5413_P.djf | nc lp.local 9100
    ```
    """
    port = port if port else socket.getservbyname(PORT_SERVICE_NAME)
    addr_info = socket.getaddrinfo(str(target), port, 0, 0, socket.SOL_TCP)[0]
    with socket.socket(addr_info[0], addr_info[1], 0) as sock:
        sock.connect(addr_info[4])

        with fw_file_path.open("rb") as fw_file:
            sock.sendfile(fw_file)
