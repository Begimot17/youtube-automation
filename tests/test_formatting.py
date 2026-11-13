from src.utils.formatting import format_log_tail


def test_empty_logs():
    assert "No logs available" in format_log_tail([])
    assert "No logs available" in format_log_tail(["  \n"])


def test_escapes_html():
    out = format_log_tail(["<class 'KeyError'> & more\n"])
    assert "<pre>&lt;class &#x27;KeyError&#x27;&gt; &amp; more\n</pre>" in out


def test_keeps_last_lines_only():
    lines = [f"line{i}\n" for i in range(100)]
    out = format_log_tail(lines, max_lines=2)
    assert "line98" in out and "line99" in out and "line97" not in out


def test_truncated_message_fits_telegram_limit():
    out = format_log_tail(["<" * 5000 + "\n"])
    assert len(out) < 4096
    out = format_log_tail(["x" * 10000])
    assert len(out) < 4096
