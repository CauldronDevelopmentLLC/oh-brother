"""Auto detect printer using zeroconf."""

# pylint: disable=C0103
# pylint: disable=R1723

import ipaddress
import typing

import termcolor

import zeroconf
from .models import MDNSPrinterInfo
from .utils import clear_screen, print_debug, print_error

if typing.TYPE_CHECKING:
    from .models import IPAddress

ZEROCONF_SERVICE_DOMAIN = "_pdl-datastream._tcp.local."

termcolor.ATTRIBUTES["italic"] = 3  # type: ignore


class PrinterDiscoverer(zeroconf.ServiceListener):
    """Discoverer of printers."""

    def __init__(self):
        self._printers: typing.List[MDNSPrinterInfo] = []
        self._zc = zeroconf.Zeroconf()
        self._mode = "CLI"
        self._invalid_answer = False
        self._browser: typing.Optional[zeroconf.ServiceBrowser] = None

    def remove_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        print_debug(f"Service {name} removed")
        self._remove_printer_infos_by_name(name)

        if self._mode == "CLI":
            self._update_screen()

    @staticmethod
    def _zc_info_to_mdns_printer_infos(
        service_info: zeroconf.ServiceInfo,
        name: str,
    ) -> typing.Iterator[MDNSPrinterInfo]:
        """Convert the info from zeroconf into MDNSPrinterInfo instances."""

        for addr in service_info.addresses:
            try:
                ip_addr = ipaddress.ip_address(addr)
            except ValueError as err:
                print_error(str(err))

                return

            product = service_info.properties.get(b"product", None)

            if product:
                product = product.decode("utf8")

            note = service_info.properties.get(b"note", None)

            if note:
                note = note.decode("utf8")

            uuid = service_info.properties.get(b"UUID", None)

            if uuid:
                uuid = uuid.decode("utf8")

            yield MDNSPrinterInfo(
                ip_addr=ip_addr,
                name=name,
                port=service_info.port,
                product=product,
                note=note,
                uuid=uuid,
            )

    def _remove_printer_infos_by_name(self, name: str):
        """Remove all known printer infos by their name."""
        printers_to_remove = [p for p in self._printers if p.name == name]

        for printer in printers_to_remove:
            self._printers.remove(printer)

    def _add_printer_infos(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Add printer info."""
        service_info = zc.get_service_info(type_, name)

        if not service_info:
            print_error(f"Received empty add_service request. Ignoring: {type_} {name}")

            return

        for printer_info in PrinterDiscoverer._zc_info_to_mdns_printer_infos(
            service_info, name
        ):
            self._printers.append(printer_info)

        if self._mode == "CLI":
            self._update_screen()

    def add_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        print_debug(f"Service {name} added")
        self._add_printer_infos(zc, type_, name)

    def update_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Update a service."""
        print_debug("Service {name} updated")
        self._remove_printer_infos_by_name(name)
        self._add_printer_infos(zc, type_, name)

    def _update_screen(self):
        """Update the CLI printer selection screen."""
        clear_screen()

        termcolor.cprint("Choose a printer", attrs=["bold"], end=" ")
        termcolor.cprint("Scanning Network via MDNS...", attrs=["italic"])

        if self._invalid_answer:
            print_error("Invalid answer.")
        print()

        if self._printers:
            max_str_len = len(str(len(self._printers) - 1))
            max_ip_len = max(len(str(info.ip_addr)) for info in self._printers)

            for i, info in enumerate(self._printers):
                num_str = termcolor.colored(
                    f"[{str(i).rjust(max_str_len)}]", color="blue", attrs=["bold"]
                )
                ip_addr_str = termcolor.colored(
                    str(info.ip_addr).rjust(max_ip_len), color="yellow"
                )
                port_str = termcolor.colored(f"Port {info.port}")
                name_str = termcolor.colored(info.name, color="white")
                product_str = (
                    termcolor.colored(f"- Product: {info.product}")
                    if info.product
                    else ""
                )
                note_str = (
                    termcolor.colored(f"- Note: {info.note}", attrs=["italic"])
                    if info.note
                    else ""
                )
                uuid_str = (
                    termcolor.colored(f"- UUID: {info.uuid}", attrs=["italic"])
                    if info.uuid
                    else ""
                )
                print(
                    f"{num_str} {ip_addr_str} {port_str} {name_str} {product_str} {note_str} {uuid_str}"
                )

            print()

            if len(self._printers) > 1:
                range_str = f"[0 - {len(self._printers) - 1}; Enter: Cancel]"
            else:
                range_str = "[0; Enter: Cancel]"

            range_str = termcolor.colored(range_str, color="blue")
            termcolor.cprint(
                f"Your choice {range_str}:",
                attrs=["bold"],
                end=" ",
                flush=True,
            )
        else:
            termcolor.cprint("No printers found yet. [Enter: Cancel]", attrs=["italic"])

    def run_cli(self) -> typing.Optional[MDNSPrinterInfo]:
        """Run as interactive terminal application."""
        self._mode = "CLI"
        choice: typing.Optional[int] = None
        self._run()
        self._update_screen()

        try:
            while True:
                inpt = input().strip()

                if not inpt:
                    break
                try:
                    choice = int(inpt)
                except ValueError:
                    choice = None

                if choice in range(len(self._printers)):
                    break
                else:
                    self._invalid_answer = True
                    self._update_screen()
        except (KeyboardInterrupt, EOFError):
            print()
        finally:
            self._stop()
            clear_screen()

        if choice is None:
            return None
        try:
            return self._printers[choice]
        except KeyError:
            print_error("This should not happen. Try again.")

            return None

    def _run(self):
        """Auto detect printer using zeroconf."""
        self._browser = zeroconf.ServiceBrowser(
            zc=self._zc,
            type_=ZEROCONF_SERVICE_DOMAIN,
            handlers=self,
        )

    def _stop(self):
        """Stop discovering."""
        self._zc.close()
