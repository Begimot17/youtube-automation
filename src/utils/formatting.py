"""Pure text helpers for Telegram messages."""

import html


def format_log_tail(lines, max_lines=50, max_chars=4000):
    """
    Builds an HTML-safe <pre> block with the tail of the log. Truncation happens
    before escaping so the message never exceeds Telegram's limit with entities.
    """
    text = "".join(lines[-max_lines:]) if lines else ""
    if not text.strip():
        return "📋 <b>Last Logs:</b>\nNo logs available."
    if len(text) > max_chars:
        text = text[-max_chars:]
    # Escaping can grow the text (< -> &lt;); keep the final message under 4096.
    while len(html.escape(text)) > 4000 and len(text) > 1:
        text = text[len(text) // 10 + 1 :]
    return f"📋 <b>Last Logs:</b>\n<pre>{html.escape(text)}</pre>"
