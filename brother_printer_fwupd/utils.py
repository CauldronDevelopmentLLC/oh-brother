"""Some utilities used in other modules."""

# pylint: disable=R1705

import os
import sys

import termcolor
import logging

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


def add_logging_level(level_name: str, level_num: int, method_name: str = None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `level_name` becomes an attribute of the `logging` module with the value
    `level_num`. `method_name` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `method_name` is not specified, `level_name.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> add_logging_level('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """

    if not method_name:
        method_name = level_name.lower()

    if hasattr(logging, level_name):
        raise AttributeError(f"{level_name} already defined in logging module")

    if hasattr(logging, method_name):
        raise AttributeError(f"{method_name} already defined in logging module")

    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError(f"{method_name} already defined in logger class")

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(level_num):
            self._log(level_num, message, args, **kwargs)

    def log_to_root(message, *args, **kwargs):
        logging.log(level_num, message, *args, **kwargs)

    logging.addLevelName(level_num, level_name)
    setattr(logging, level_name, level_num)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)


add_logging_level("SUCCESS", logging.INFO + 5)


class TerminalFormatter(logging.Formatter):
    """Logging formatter with colors."""

    colors = {
        logging.DEBUG: "grey",
        logging.INFO: "cyan",
        logging.SUCCESS: "green",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "red",
    }
    prefix = {
        logging.DEBUG: "[d]",
        logging.INFO: "[i]",
        logging.SUCCESS: "[i]",
        logging.WARNING: "[!]",
        logging.ERROR: "[!]",
        logging.CRITICAL: "[!]",
    }
    attrs = {
        logging.CRITICAL: ["bold"],
    }

    def __init__(self, fmt="%(message)s"):
        super().__init__(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record):
        return termcolor.colored(
            f"{self.prefix[record.levelno]} {super().format(record)}",
            color=self.colors[record.levelno],
            attrs=self.attrs.get(record.levelno),
        )


LOGGER = logging.getLogger(name="brother_printer_fwupd")
CONSOLE_LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG)
CONSOLE_LOG_HANDLER.setFormatter(TerminalFormatter())
LOGGER.addHandler(CONSOLE_LOG_HANDLER)


def clear_screen():
    """Clear the terminal screen."""
    os.system("clear")
    #  print(chr(27) + '[2j')
    #  print('\033c')
    #  print('\x1bc')
