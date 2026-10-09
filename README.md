# iCloud-mcp

A small, **read-only** MCP server that lets Claude read your iCloud Mail over IMAP.

## Tools

| Tool | What it does |
| --- | --- |
| `list_folders` | List mailbox folders |
| `list_emails` | Recent emails in a folder (optionally unread only) |
| `search_emails` | Filter by text, sender, subject, date range |
| `read_email` | Full body and attachment names for one email |
| `count_unread` | Number of unread emails in a folder |

Messages are fetched with `BODY.PEEK` on a read-only mailbox, so nothing is
marked as read, moved, or deleted. There are no send tools.

## Setup

1. Create an app-specific password at account.apple.com
   (Sign-In and Security -> App-Specific Passwords). 2FA must be on.
2. Install:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```

3. Add your credentials to a git-ignored `.env` file:

   ```bash
   cp .env.example .env   # then edit it
   ```

   (Real environment variables, if set, take precedence over `.env`.)

4. Test with the MCP Inspector:

   ```bash
   .venv/bin/mcp dev icloud_mcp/server.py
   ```

## Connect to Claude

**Claude Code**

```bash
claude mcp add icloud-mail -- /absolute/path/to/iCloud-mcp/.venv/bin/icloud-mcp
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "icloud-mail": {
      "command": "/absolute/path/to/iCloud-mcp/.venv/bin/icloud-mcp"
    }
  }
}
```

The server uses stdio, so Claude starts and stops it for you.
