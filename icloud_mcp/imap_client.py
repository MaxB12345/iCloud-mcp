"""Thin read-only IMAP helpers for iCloud Mail."""

import email
import imaplib
import os
import re
from contextlib import contextmanager
from email.header import decode_header, make_header
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path

IMAP_HOST = "imap.mail.me.com"
IMAP_PORT = 993
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines from a .env file without overriding real env vars."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@contextmanager
def open_mailbox(folder: str = "INBOX"):
    """Log in, select `folder` read-only, and always log out afterwards."""
    load_env_file()
    try:
        user = os.environ["ICLOUD_EMAIL"]
        password = os.environ["ICLOUD_APP_PASSWORD"]
    except KeyError as missing:
        raise RuntimeError(f"Environment variable {missing} is not set") from None

    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        conn.login(user, password)
        status, _ = conn.select(quote(folder), readonly=True)
        if status != "OK":
            raise ValueError(f"Could not open folder '{folder}'")
        yield conn
    finally:
        try:
            conn.logout()
        except imaplib.IMAP4.error:
            pass


def quote(value: str) -> str:
    """Quote a string for use as an IMAP argument."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def decode(value: str | None) -> str:
    """Decode an RFC 2047 encoded header into plain text."""
    return str(make_header(decode_header(value or "")))


def fetch_message(conn: imaplib.IMAP4_SSL, uid: str, part: str = "BODY.PEEK[]") -> Message:
    """Fetch one message by UID without setting the \\Seen flag."""
    status, data = conn.uid("FETCH", uid, f"({part})")
    if status != "OK" or not data or data[0] is None:
        raise ValueError(f"No message with id {uid}")
    return email.message_from_bytes(data[0][1])


def summarize(msg: Message, uid: str) -> dict:
    return {
        "id": uid,
        "from": decode(msg.get("From")),
        "to": decode(msg.get("To")),
        "subject": decode(msg.get("Subject")),
        "date": msg.get("Date"),
    }


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        self._skip = tag in ("script", "style")
        if tag in ("br", "p", "div", "tr", "li"):
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.chunks.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.chunks)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_body(msg: Message) -> str:
    """Prefer the plain-text part; fall back to HTML converted to text."""
    plain = html = None
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            continue
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if kind == "text/plain" and plain is None:
            plain = text
        elif kind == "text/html" and html is None:
            html = text
    if plain:
        return plain.strip()
    return html_to_text(html) if html else "(no text body)"


def list_attachments(msg: Message) -> list[dict]:
    return [
        {"filename": decode(p.get_filename()), "type": p.get_content_type()}
        for p in msg.walk()
        if p.get_content_disposition() == "attachment" and p.get_filename()
    ]
