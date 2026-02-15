# telegram-mcp

Read-only MCP server for accessing your personal Telegram account from Claude Code.

## What it does

Exposes 3 tools to Claude Code via MCP (stdio transport):

- **list_chats** — list your chats/channels/groups with unread counts
- **get_messages** — read messages from a specific chat
- **search_messages** — global or per-chat message search

Uses Telethon (MTProto) with your personal account — not a bot, so it can see full chat history.

## Setup

### 1. Get Telegram API credentials

Go to https://my.telegram.org/apps, create an app, note `api_id` and `api_hash`.

### 2. Configure

```bash
cd ~/dev/tools/telegram-mcp
cp .env.example .env
# Edit .env: fill API_ID, API_HASH, PHONE
```

### 3. Build

```bash
docker compose --profile auth build
```

### 4. Authenticate

```bash
docker compose --profile auth run --rm --service-ports auth
```

Open http://localhost:8901, enter your phone, the code from Telegram, and 2FA password if enabled.

Session is saved to `var/telegram.session`.

### 5. Add to Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
"telegram": {
  "type": "stdio",
  "command": "docker",
  "args": [
    "compose", "-f", "/path/to/telegram-mcp/docker-compose.yml",
    "run", "--rm", "-i", "--no-deps", "mcp"
  ]
}
```

## Usage examples

Once connected, ask Claude Code:

- "Show my Telegram channels"
- "What are the latest messages in @channel_name?"
- "Search my Telegram for messages about project X"
- "What tasks were discussed in chat Y this week?"

## Architecture

```
domain/     — models (ChatInfo, MessageInfo) + TelegramReader protocol
infrastructure/ — Telethon adapter + config
presentation/   — MCP server, tools, formatters
auth/           — standalone web service for Telegram authorization
```

## Docker services

| Service | Purpose | Port |
|---------|---------|------|
| `mcp` | MCP stdio server (used by Claude Code) | — |
| `auth` | Web UI for Telegram auth (on-demand) | 8901 |

The `auth` service only runs when explicitly requested via `--profile auth`.
