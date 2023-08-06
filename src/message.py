"""Message module."""

import logging
import queue
from enum import IntEnum

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

    def __init__(self: "Message", code: str, body: str, level: Level = Level.Report) -> "Message":
        """Init a new message."""
        self.code = code
        self.body = body
        self.level = level

    def print_message(self: "Message", message_queue: None | queue.Queue = None) -> None:
        """Print the message."""
        message = f"{self.project}: [{self.code}] {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)
