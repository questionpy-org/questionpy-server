#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import sys
from io import BufferedReader, FileIO, StringIO

from questionpy_server.worker.runtime.connection import WorkerToServerConnection
from questionpy_server.worker.runtime.manager import WorkerManager


def setup_server_communication() -> WorkerToServerConnection:
    """Setup stdin/stdout/stderr.

    The application server communicates with its worker through stdin/stdout, which means only this class is allowed to
    read from and write to these pipes. Other output should go through stderr.
    """
    file_stdin = FileIO(sys.stdin.buffer.fileno(), "r", closefd=False)
    file_stdout = FileIO(sys.stdout.fileno(), "w", closefd=False)
    connection = WorkerToServerConnection(BufferedReader(file_stdin), file_stdout)

    sys.stdin = StringIO()
    sys.stdout = sys.stderr  # All writes to sys.stdout should go to stderr.
    return connection


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    con = setup_server_communication()
    manager = WorkerManager(con)
    manager.bootstrap()
    manager.loop()
