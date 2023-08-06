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

    project: str
    level: Level
    code: str
    body: str

    def __init__(self: "Message", code: str, body: str, project: str, level: Level = Level.Report) -> "Message":
        """Init a new message."""
        self.code = code
        self.body = body
        self.level = level
        self.project = project

    def to_dict(self: "Message") -> dict:
        """Convert to dict."""
        return {
            "code": self.code,
            "body": self.body,
            "level": self.level,
            "project": self.project,
        }

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

    def message_to_string(self: "Message") -> str:
        """Output that would be printed into a string."""
        return f"{self.code} {self.body}"

    def message_to_json(self: "Message") -> dict[str]:
        """Output a JSON dict for the API."""
        return {
            "code": self.code,
            "body": self.body,
            "level": self.level,
            "project": self.project,
        }
