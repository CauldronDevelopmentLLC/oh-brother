"""Some utilities used in other modules."""

# pylint: disable=R1705

import io
import logging
import os
import shlex
import string
import sys
import traceback
import typing
from pathlib import Path
from urllib.parse import urlencode

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


class GitHubIssueReporter:
    def __init__(
        self,
        logger: logging.Logger,
        issue_url: str,
        handler_cb: typing.Callable[[str], None],
    ):
        self.logger = logger
        self.issue_url = issue_url
        self.handler_cb = handler_cb
        self._handler = logging.StreamHandler(stream=io.StringIO())
        self._handler.setLevel(logging.DEBUG)
        self._context = dict[str, str | bool | list[str]]()

    def __enter__(self):
        self._handler.stream.seek(0)
        self._handler.stream.truncate()
        self.logger.addHandler(self._handler)

        return self

    def __exit__(self, exc_class, exc, tb):
        if not exc_class or exc_class in (SystemExit, KeyboardInterrupt):
            return

        if isinstance(exc, ExceptionGroup):
            LOGGER.error("%s  Errors:", exc.message)
            for err in exc.exceptions:
                LOGGER.error("  - %s", err)
        else:
            LOGGER.error(exc)
        self.logger.removeHandler(self._handler)
        self._handler.stream.seek(0)
        log_output = self._handler.stream.read()
        prog = Path(sys.argv[0]).name
        cmd = prog + " " + shlex.join(sys.argv[1:])
        exc_io = io.StringIO()
        traceback.print_exception(exc, file=exc_io)
        exc_io.seek(0)
        exception = exc_io.read()
        emulation_cmd_parts = [prog]

        for key, value in self._context.items():
            if isinstance(value, bool):
                if value is True:
                    emulation_cmd_parts.append(key)
            elif isinstance(value, list):
                emulation_cmd_parts.extend([key, *value])
            else:
                emulation_cmd_parts.extend([key, value])
        emulation_cmd = shlex.join(emulation_cmd_parts)
        emulation_block = (
            ""
            if not self._context
            else f"""
**Command to emulate scenario:**

```sh
{emulation_cmd}
```

"""
        )
        report_url = (
            self.issue_url
            + "?"
            + urlencode(
                {
                    "title": str(exc),
                    "body": f"""
**Description:**

*please describe the issue*

**Command:**

```sh
{cmd}
```
{emulation_block}
**Output:**

```
{log_output}
```

**Exception:**

```python
{exception}
```
""".strip(),
                }
            )
        )
        self.handler_cb(report_url)
        sys.exit(1)

    def set_context_data(self, key: str, value: str | bool | list[str]):
        self._context[key] = value


def get_running_os() -> (
    typing.Literal["WINDOWS"] | typing.Literal["MAC"] | typing.Literal["LINUX"]
):
    if sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
        return "WINDOWS"
    elif sys.platform.startswith("darwin"):
        return "MAC"
    else:
        return "LINUX"


def add_logging_level(level_name: str, level_num: int, method_name: str | None = None):
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


CONSOLE_LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
CONSOLE_LOG_HANDLER.setFormatter(TerminalFormatter())
LOGGER = logging.getLogger(name="brother_printer_fwupd")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(CONSOLE_LOG_HANDLER)


def clear_screen():
    """Clear the terminal screen."""
    os.system("clear")
    #  print(chr(27) + '[2j')
    #  print('\033c')
    #  print('\x1bc')


def sluggify(value: str) -> str:
    """Convert value to a string that can be safely used as file name."""
    trans_tab = {
        " ": "_",
        "@": "-",
        ":": "-",
    }
    trans = str.maketrans(trans_tab)
    allowed_chars = string.ascii_letters + string.digits + "".join(trans_tab.values())
    assert "/" not in allowed_chars
    assert "." not in allowed_chars
    value = value.strip().lower().translate(trans)
    value = "".join(c for c in value if c in allowed_chars)
    return value
