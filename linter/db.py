import datetime
import logging
from queue import Queue

import psycopg2
from psycopg2.extensions import parse_dsn
from message import Level, Message


class DatabaseConnection:
    connection: psycopg2.extensions.connection
    cursor: psycopg2.extensions.cursor
    mock: bool = False

    def __init__(self, creds: str, mock: bool = False) -> None:
        # If connection is fake, e.g. for testing or when no connection string is supplied
        self.mock = mock
        if mock:
            return

        # Connect
        conn: psycopg2.extensions.connection = psycopg2.connect(**parse_dsn(creds))
        cursor: psycopg2.extensions.cursor = conn.cursor()

        # Create table query
        create_table_query = "CREATE TABLE IF NOT EXISTS messages ( id SERIAL PRIMARY KEY, time BIGINT NOT NULL, tool TEXT NOT NULL, code TEXT NOT NULL, location TEXT NOT NULL, text TEXT NOT NULL, level INTEGER NOT NULL );"
        cursor.execute(create_table_query)

        self.connection = conn
        self.cursor = cursor

    def drop_rows_with_tool_name(self, name: str) -> None:
        logging.debug(f"Deleting rows with tools name {name}")
        if self.mock:
            return

        delete_query = "DELETE FROM messages WHERE tool = %s;"
        self.cursor.execute(delete_query, (name,))

    def insert_from_queue(self, queue: Queue) -> bool:
        """Insert message queue into database.

        Args:
        ----
            queue (Queue): Queue
            sql_cursor (psycopg2.cursor | None): SQL database cursor

        Returns:
        -------
            bool (bool): True if any messages have been received.
        """
        logging.info("Sending messages to database")

        returned_atleast_one_value = False

        while not queue.empty():
            item: Message = queue.get()
            returned_atleast_one_value = True

            if self.mock:
                continue

            if item.level == Level.LinterInternal:
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

    def commit(self):
        if self.mock:
            return

        self.connection.commit()

    def close(self):
        if self.mock:
            return

        self.connection.commit()
        self.connection.close()
