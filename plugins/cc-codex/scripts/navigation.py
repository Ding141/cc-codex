"""Machine-local project directory and per-Claude-session selections."""

from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3


@contextmanager
def database(write=False):
    home = Path(os.environ.get("CC_CODEX_HOME") or Path.home() / ".cc-codex").expanduser().resolve()
    path = home / "navigation.sqlite3"
    if not write and not path.is_file():
        yield None
        return
    if write:
        home.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path.as_uri() + ("?mode=rwc" if write else "?mode=ro"),
                                 uri=True)) as db:
        if write:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS projects (path_key TEXT PRIMARY KEY, root TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, root TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS selections (
                    session TEXT, root TEXT, task TEXT NOT NULL, PRIMARY KEY(session, root)
                );
            """)
        elif not db.execute("SELECT 1 FROM sqlite_master WHERE name='selections'").fetchone():
            # A first registration in another process has not committed yet.
            yield None
            return
        with db:
            yield db


def projects():
    with database() as db:
        if db is None:
            return []
        return [Path(row[0]) for row in db.execute("SELECT root FROM projects ORDER BY root")]


def active_project(session):
    if not session:
        return Path.cwd()
    with database() as db:
        row = db.execute("SELECT root FROM sessions WHERE id=?", (session,)).fetchone() if db else None
    return Path(row[0]) if row else Path.cwd()


def selected_task(session, root):
    if not session:
        return None
    with database() as db:
        row = db.execute("SELECT task FROM selections WHERE session=? AND root=?",
                         (session, os.path.normcase(str(root)))).fetchone() if db else None
    return row[0] if row else None


def remember(root, session, task=None):
    display = str(root)
    key = os.path.normcase(display)
    with database(write=True) as db:
        db.execute("INSERT OR IGNORE INTO projects VALUES (?, ?)", (key, display))
        if session:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?)", (session, display))
            if task:
                db.execute("INSERT OR REPLACE INTO selections VALUES (?, ?, ?)",
                           (session, key, task))


def resolve_project(value):
    path = Path(value).expanduser()
    if path.is_absolute() or path.parent != Path(".") or value.startswith("."):
        return path.resolve(strict=True)
    matches = [known for known in projects() if os.path.normcase(known.name) == os.path.normcase(value)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError("Ambiguous project name. Use an absolute path: " + ", ".join(map(str, matches)))
    raise ValueError("Unknown project. Use project list or the absolute path of an initialized project.")
