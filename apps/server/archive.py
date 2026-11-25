"""Online SQLite backup and restore to a new local file."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile


def copy_workspace(source: Path, destination: Path):
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise ValueError("Choose an existing destination directory.")

    # Link only a complete, verified snapshot. A racing process that creates
    # the destination first wins; no existing backup or DB can be replaced.
    with NamedTemporaryFile(dir=destination.parent, prefix=".polysia-backup-") as staging:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            with closing(sqlite3.connect(staging.name)) as writer:
                reader.backup(writer, pages=256)
                if writer.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("The copied database failed the SQLite integrity check.")
                if writer.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise ValueError("This file is not a supported PolySia workspace.")
                tables = set(writer.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table' AND name IN ('workspace', 'runs')"
                ))
                if tables != {("workspace",), ("runs",)}:
                    raise ValueError("The workspace schema is incomplete.")
                row = writer.execute(
                    "SELECT theme, account_revision, settings_revision FROM workspace WHERE id = 1"
                ).fetchone()
                if row is None or row[0] not in ("light", "dark"):
                    raise ValueError("The workspace settings are missing or invalid.")
                writer.execute("SELECT id, record FROM runs LIMIT 0")
        os.fsync(staging.fileno())
        os.link(staging.name, destination)
        dir_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
