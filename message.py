"""Message module."""

import logging
import queue
from enum import Enum

REPORT = 15


class Level(Enum):

    """Level for message."""

    Report = 1
    Error = 2


class Message:

    """Linter message."""

    code: str
    body: str
    project: str | None = None
    level: Level

    def __init__(self: "Message", code: str, body: str, project: str | None = None, level: Level = Level.Report) -> None:
        """Init a new message."""
        self.code = code
        self.body = body
        self.project = project
        self.level = level

    def print_message_without_name(self: "Message", message_queue: None | queue.Queue = None) -> None:
        """Print the message."""
        message = f"{self.code} {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)

    def print_message(self: "Message", message_queue: None | queue.Queue = None) -> None:
        """Print the message."""
        message = f"{self.code} {self.body}"

        logging.log(REPORT, message)
        if message_queue is not None:
            message_queue.put(message)
