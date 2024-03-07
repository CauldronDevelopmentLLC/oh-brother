"""Types and model classes / definitions."""

import argparse
import ipaddress
from dataclasses import dataclass, field

import termcolor

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass
class FWInfo:
    """Firmware fragment info."""

    # TODO don't allow None here...
    firmid: str | None = field(default=None)
    firmver: str | None = field(default=None)

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
                termcolor.colored(
                    f"Invalid firmware ID {value}. Format: firmid@firmver",
                    "red",
                )
            ) from err
        return cls(firmid, firmver)


@dataclass
class SNMPPrinterInfo:
    """Information about a printer."""

    model: str | None = field(default=None)
    serial: str | None = field(default=None)
    spec: str | None = field(default=None)
    fw_versions: list[FWInfo] = field(default_factory=list[FWInfo])


@dataclass
class MDNSPrinterInfo:
    """Information about a printer received via MDNS."""

    ip_addr: IPAddress
    name: str
    port: int | None
    product: str | None
    note: str | None
    uuid: str | None
