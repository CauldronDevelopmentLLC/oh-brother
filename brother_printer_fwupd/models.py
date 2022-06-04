"""Types and model classes / definitions."""
import typing
import ipaddress
from dataclasses import dataclass, field
import argparse


IPAddress = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


@dataclass
class FWInfo:
    """Firmware fragment info."""

    firmid: typing.Optional[str] = field(default=None)
    firmver: typing.Optional[str] = field(default=None)

    @property
    def is_complete(self):
        """Return True if firmid and firmver is given."""
        return self.firmid is not None and self.firmver is not None

    @property
    def is_empty(self):
        """Return True if firmid and firmver are None."""
        return self.firmid is None and self.firmver is None

    def __str__(self):
        return f"{self.firmid}@{self.firmver}"

    @classmethod
    def from_str(cls, value: str):
        """Parse FW info from string from command line argument."""
        try:
            firmid, firmver = value.split("@", 1)
        except ValueError as err:
            raise argparse.ArgumentTypeError(
                f"Invalid firmware ID {value}. Format: firmid@firmver"
            ) from err
        return cls(firmid, firmver)


@dataclass
class SNMPPrinterInfo:
    """Information about a printer."""

    model: typing.Optional[str] = field(default=None)
    serial: typing.Optional[str] = field(default=None)
    spec: typing.Optional[str] = field(default=None)
    fw_versions: typing.List[FWInfo] = field(default_factory=list)


@dataclass
class MDNSPrinterInfo:
    """Information about a printer received via MDNS."""

    ip_addr: IPAddress
    name: str
    port: typing.Optional[int]
    product: typing.Optional[str]
    note: typing.Optional[str]
    uuid: typing.Optional[str]
