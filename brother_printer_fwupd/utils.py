"""Some utilities used in other modules."""

# pylint: disable=R1705

import os
import sys

import termcolor

try:
    from gooey import Gooey
except ImportError:
    Gooey = None


def gooey_if_exists(func):
    """Make the app graphical, if gooey is installed."""

    if Gooey:
        return Gooey(func)
    else:
        return func


def print_error(text: str):
    """Print error to stderr in red."""
    termcolor.cprint(f"[!] {text}", color="red", file=sys.stderr)


def print_warning(text: str):
    """Print a warning to stderr in red."""
    termcolor.cprint(f"[!] {text}", color="yellow", file=sys.stderr)


def print_info(text: str):
    """Print a warning to stderr in red."""
    termcolor.cprint(f"[i] {text}", color="blue")


def print_success(text: str):
    """Print a text in green to stdout."""
    termcolor.cprint(f"[i] {text}", color="green")


def print_debug(text: str):
    """Print a debug message in grey to stderr."""
    termcolor.cprint(f"[d] {text}", color="grey", file=sys.stderr)


def clear_screen():
    """Clear the terminal screen."""
    os.system("clear")
    #  print(chr(27) + '[2j')
    #  print('\033c')
    #  print('\x1bc')
