"""Types and model classes / definitions."""
import typing
import ipaddress
from dataclasses import dataclass, field


IPAddress = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


@dataclass
class SNMPPrinterInfo:
    """Information about a printer."""

    model: typing.Optional[str] = field(default=None)
    serial: typing.Optional[str] = field(default=None)
    spec: typing.Optional[str] = field(default=None)
    fw_versions: typing.List[typing.Tuple[str, str]] = field(default_factory=list)


@dataclass
class MDNSPrinterInfo:
    """Information about a printer received via MDNS."""

    ip_addr: IPAddress
    name: str
    port: typing.Optional[int]
    product: typing.Optional[str]
    note: typing.Optional[str]
