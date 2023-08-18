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

    Report = 1
    Error = 2
    Debug = 3

class Message:

    """Linter message."""

    project: str # Project will be filled-in in lib/lint_specific_project
    level: Level
    code: str
    body: str

    def __init__(self: Message, code: str, body: str, level: Level = Level.Report) -> Message:
        """Init a new message."""
        self.code = code
        self.body = body
        self.level = level

    def print_message(self: Message, message_queue: None | queue.Queue = None) -> None:
        """Print the message."""
        message = f"{self.project}: [{self.code}] {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)

    def get_location(self: Message) -> str:
        """Return where the error happened. Strips the project name."""
        return self.body.split("`")[3].split("//")[1]

    def get_value(self: Message) -> str:
        """Return the value of the error."""
        return self.body.split("`")[1]
