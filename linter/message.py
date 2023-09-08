"""Message module."""
from __future__ import annotations

import logging
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import queue

REPORT = 15


class Level(IntEnum):

    """Level for message."""

    Report = 1 # Obsolete
    LinterError = 2 # Linter errors
    LinterInternal = 3 # For messaging between threads, e.g. the LINT-F for when a lint finishes
    ReportCritical = 4 # Reserved for security problems
    ReportHigh = 5
    ReportMedium = 6
    ReportLow = 7

class Message:

    """Message returned by the linter upwards to lib and cli."""

    project: str # Project will be filled-in in lib/lint_specific_project
    level: Level
    code: str
    body: str
    location: str

    def __init__(self: Message, code: str, body: str, location: str, level: Level = Level.Report) -> Message:
        """Init a new message."""
        self.code = code
        self.body = body
        self.level = level
        self.location = location

    def print_message(self: Message, message_queue: None | queue.Queue = None) -> None:
        """Print the message."""
        message = f"{self.project}: [{self.code}] {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)

