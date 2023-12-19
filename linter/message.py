"""Message module."""
from __future__ import annotations

import logging
import queue
from enum import IntEnum

REPORT = 15


class Level(IntEnum):

    """Level for message."""

    Report = 1  # Obsolete
    LinterError = 2  # Linter errors
    LinterInternal = (
        3  # For messaging between threads, e.g. the LINT-F for when a lint finishes
    )
    ReportHigh = 5
    ReportMedium = 6
    ReportLow = 7
    ReportCritical = 8  # Reserved for security problems


class Message:

    """Message returned by the linter upwards to lib and cli."""

    tool: str  # Tool (biotools id) will be filled-in in lib/lint_specific_tool
    level: Level
    code: str
    body: str
    location: str

    def __init__(
        self: Message,
        code: str,
        body: str,
        location: str,
        level: Level = Level.Report,
    ) -> Message:
        """Init a new message."""
        self.code = code
        self.body = body
        self.level = level
        self.location = location
        self.tool = None

    def print_message(self: Message, message_queue: None | queue.Queue = None) -> str:
        """Print the message as a report, and put it into the message queue. Returns outputed string."""
        message = f"{self.tool}: [{self.code}] {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)

        return message
