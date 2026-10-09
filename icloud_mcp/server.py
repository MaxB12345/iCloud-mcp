"""MCP server exposing read-only tools for iCloud Mail."""

from mcp.server.fastmcp import FastMCP

from .imap_client import (
    extract_body,
    fetch_message,
    list_attachments,
    open_mailbox,
    quote,
    summarize,
)

mcp = FastMCP("icloud-mail")

HEADER_FIELDS = "BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)]"
MAX_BODY_CHARS = 20000


def _search(folder: str, criteria: list[str], limit: int) -> list[dict]:
    """Run an IMAP UID search and return summaries, newest first."""
    with open_mailbox(folder) as conn:
        status, data = conn.uid("SEARCH", *criteria)
        if status != "OK":
            raise ValueError(f"Search failed: {data}")
        uids = data[0].split()[-limit:]
        return [
            summarize(fetch_message(conn, uid.decode(), HEADER_FIELDS), uid.decode())
            for uid in reversed(uids)
        ]


@mcp.tool()
def list_folders() -> list[str]:
    """List all mailbox folders (e.g. INBOX, Sent Messages, Archive)."""
    with open_mailbox() as conn:
        _, data = conn.list()
    # Each line looks like: (\HasNoChildren) "/" "Sent Messages"
    return [line.decode().rsplit(' "/" ', 1)[-1].strip('"') for line in data if line]


@mcp.tool()
def list_emails(folder: str = "INBOX", limit: int = 10, unread_only: bool = False) -> list[dict]:
    """List the most recent emails in a folder, newest first.

    Returns id, from, to, subject and date. Use read_email with the id for the body.
    """
    return _search(folder, ["UNSEEN" if unread_only else "ALL"], limit)


@mcp.tool()
def search_emails(
    query: str = "",
    sender: str = "",
    subject: str = "",
    since: str = "",
    before: str = "",
    folder: str = "INBOX",
    limit: int = 10,
) -> list[dict]:
    """Search a folder. All provided filters are combined with AND.

    query: text anywhere in the message. sender/subject: substring match.
    since/before: dates formatted like 01-Jan-2026.
    """
    criteria: list[str] = []
    for key, value in (("TEXT", query), ("FROM", sender), ("SUBJECT", subject)):
        if value:
            criteria += [key, quote(value)]
    for key, value in (("SINCE", since), ("BEFORE", before)):
        if value:
            criteria += [key, value]
    return _search(folder, criteria or ["ALL"], limit)


@mcp.tool()
def read_email(id: str, folder: str = "INBOX") -> dict:
    """Read one email's full text body and attachment names by id.

    The id comes from list_emails or search_emails for the same folder.
    Reading does not mark the message as read.
    """
    with open_mailbox(folder) as conn:
        msg = fetch_message(conn, id)
    body = extract_body(msg)
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n...[truncated]"
    return {**summarize(msg, id), "body": body, "attachments": list_attachments(msg)}


@mcp.tool()
def count_unread(folder: str = "INBOX") -> int:
    """Return the number of unread emails in a folder."""
    with open_mailbox(folder) as conn:
        _, data = conn.uid("SEARCH", "UNSEEN")
    return len(data[0].split())


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
