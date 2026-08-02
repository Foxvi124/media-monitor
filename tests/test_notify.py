import smtplib

import monitor.notify as notify
from monitor.cluster import Cluster
from monitor.feeds import Item


def _clusters():
    it = Item(title="Smelter nikel diresmikan", link="https://x/1",
              summary="", published=None, source="Media A")
    return {"Tambang": [Cluster(item=it, keywords=["nikel", "smelter"])]}


def test_summary_text():
    text = notify.digest_summary_text(_clusters(), "2026-08-02")
    assert "Digest Media 2026-08-02" in text
    assert "🔥 Smelter nikel diresmikan" in text and "https://x/1" in text


def test_telegram_sent(monkeypatch):
    calls = {}

    def fake_post(url, payload, timeout=20):
        calls["url"], calls["payload"] = url, payload
        return {"ok": True}

    monkeypatch.setattr(notify, "_post_json", fake_post)
    log = notify.notify_all(
        {"telegram": True},
        {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "42"},
        summary_text="halo", html_body="<p>halo</p>", subject="s",
    )
    assert log == ["telegram: terkirim"]
    assert "bot" + "abc" in calls["url"] and calls["payload"]["chat_id"] == "42"


def test_telegram_skipped_without_secrets():
    log = notify.notify_all({"telegram": True}, {}, summary_text="x",
                            html_body="y", subject="s")
    assert "dilewati" in log[0]


def test_email_sent(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            sent["host"], sent["port"] = host, port
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def ehlo(self):
            pass
        def starttls(self):
            sent["tls"] = True
        def login(self, user, password):
            sent["login"] = (user, password)
        def send_message(self, msg):
            sent["to"], sent["subject"] = msg["To"], msg["Subject"]

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    log = notify.notify_all(
        {"email": {"enabled": True, "to": ["a@b.c"]}},
        {"SMTP_HOST": "mail.x", "SMTP_PORT": "587",
         "SMTP_USER": "u", "SMTP_PASSWORD": "p"},
        summary_text="x", html_body="<p>x</p>", subject="[t] uji",
    )
    assert log == ["email: terkirim ke 1 penerima"]
    assert sent["host"] == "mail.x" and sent["to"] == "a@b.c"
    assert sent["login"] == ("u", "p") and sent["subject"] == "[t] uji"
