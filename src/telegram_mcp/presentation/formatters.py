from __future__ import annotations

from ..domain.models import ChatInfo, MessageInfo


def format_chat_list(chats: list[ChatInfo]) -> str:
    if not chats:
        return "No chats found."

    lines: list[str] = []
    for c in chats:
        handle = f" (@{c.username})" if c.username else ""
        unread = f" [{c.unread_count} unread]" if c.unread_count else ""
        lines.append(f"- **{c.name}**{handle} (id={c.id}, {c.type.value}){unread}")
    return "\n".join(lines)


def format_messages(messages: list[MessageInfo]) -> str:
    if not messages:
        return "No messages found."

    lines: list[str] = []
    for m in messages:
        ts = m.date.strftime("%Y-%m-%d %H:%M")
        sender = m.sender or "Unknown"
        text = m.text.replace("\n", " ") if m.text else "[no text]"
        lines.append(f"[{ts}] {sender}: {text}")
    return "\n".join(lines)


def format_search_results(messages: list[MessageInfo]) -> str:
    if not messages:
        return "No messages found."

    lines: list[str] = []
    for m in messages:
        ts = m.date.strftime("%Y-%m-%d %H:%M")
        sender = m.sender or "Unknown"
        text = m.text.replace("\n", " ") if m.text else "[no text]"
        lines.append(f"[{ts}] [{m.chat_name}] {sender}: {text}")
    return "\n".join(lines)
