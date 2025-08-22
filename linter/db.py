import datetime
import logging
from queue import Queue

from message import Level, Message
import psycopg2
from psycopg2.extensions import parse_dsn


class DatabaseConnection:
    """A class for managing the database. Allows for a mock and early returns in every function."""

    connection: None  #: psycopg2.extensions.connection
    cursor: None  #: psycopg2.extensions.cursor
    mock: bool = False

    def __init__(self, creds: str | None, mock: bool = False) -> None:
        """Initialize the database connection.

        Parameters
        ----------
        creds : str
            The database connection credentials in DSN format (postgres://user:pass@IP/dbname).
        mock : bool, optional
            If True, creates a mock database connection for testing.

        """
        # If connection is fake, e.g. for testing or when no connection string is supplied
        self.mock = mock
        if mock or creds is None:
            return

        logging.info(f"Connecting to database {parse_dsn(creds)['dbname']}")

        # Connect
        conn: psycopg2.extensions.connection = psycopg2.connect(**parse_dsn(creds))
        cursor: psycopg2.extensions.cursor = conn.cursor()

        # Create table query
        create_table_query = "CREATE TABLE IF NOT EXISTS messages ( id SERIAL PRIMARY KEY, time BIGINT NOT NULL, tool TEXT NOT NULL, code TEXT NOT NULL, location TEXT NOT NULL, text TEXT NOT NULL, level INTEGER NOT NULL );"
        cursor.execute(create_table_query)

        self.connection = conn
        self.cursor = cursor

    def drop_rows_with_tool_name(self, name: str) -> None:
        """Delete old entries of a tool.

        Args:
        ----
            name (str): Name of tool.

        """
        if self.mock:
            return

        logging.debug(f"Deleting rows with tools name {name}")
        delete_query = "DELETE FROM messages WHERE tool = %s;"
        self.cursor.execute(delete_query, (name,))

    def insert_from_queue(self, queue: Queue) -> bool:
        """Insert messages from queue into database. Empties the queue as a side effect.

        Args:
        ----
            queue (Queue): Queue

        Returns:
        -------
            bool (bool): True if any messages have been received.

        """
        if not self.mock:
            logging.info("Sending messages to database")

        returned_atleast_one_value = False

        while not queue.empty():
            item: Message = queue.get()

            if item.level == Level.LinterInternal:
                continue

            returned_atleast_one_value = True

            if self.mock:
                continue

            # Export
            insert_query = "INSERT INTO messages (time, tool, code, location, text, level) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING;"
            data = (
                int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()),
                item.tool,
                item.code,
                item.location,
                item.body,
                int(item.level),
            )
            self.cursor.execute(insert_query, data)

        return returned_atleast_one_value

    def commit(self) -> None:
        """Commit changes to database."""
        if self.mock:
            return

        self.connection.commit()

    def close(self) -> None:
        """Close database connection. Does not commit beforehand."""
        if self.mock:
            return

        self.connection.close()
