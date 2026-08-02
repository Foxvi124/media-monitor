"""Notifikasi opsional: Telegram dan email (SMTP). Kredensial diambil dari
environment (GitHub Secrets); bila tidak diset, notifikasi dilewati dengan rapi."""

from __future__ import annotations

import json
import smtplib
import urllib.request
from email.message import EmailMessage
from typing import Dict, List

from .cluster import Cluster

TELEGRAM_LIMIT = 4000  # batas aman di bawah 4096 karakter


def _post_json(url: str, payload: dict, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "media-monitor/2.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def digest_summary_text(clusters_by_topic: Dict[str, List[Cluster]],
                        date_label: str, max_per_topic: int = 3) -> str:
    """Ringkasan teks polos untuk pesan Telegram/badan email teks."""
    total = sum(len(v) for v in clusters_by_topic.values())
    lines = [f"📰 Digest Media {date_label} — {total} berita cocok", ""]
    for topic, clusters in clusters_by_topic.items():
        if not clusters:
            continue
        lines.append(f"■ {topic} ({len(clusters)})")
        for cl in clusters[:max_per_topic]:
            fire = "🔥 " if cl.hot else ""
            lines.append(f"  {fire}{cl.item.title}")
            lines.append(f"  {cl.item.link}")
        if len(clusters) > max_per_topic:
            lines.append(f"  … dan {len(clusters) - max_per_topic} lainnya")
        lines.append("")
    text = "\n".join(lines).strip()
    if len(text) > TELEGRAM_LIMIT:
        text = text[: TELEGRAM_LIMIT - 1] + "…"
    return text


def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    resp = _post_json(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
    )
    if not resp.get("ok", False):
        raise RuntimeError(f"Telegram menolak pesan: {resp}")


def send_email(host: str, port: int, user: str, password: str,
               sender: str, to: List[str], subject: str,
               text_body: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        try:
            smtp.starttls()
            smtp.ehlo()
        except smtplib.SMTPNotSupportedError:
            pass
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


def notify_all(notify_cfg: dict, env: Dict[str, str], *,
               summary_text: str, html_body: str, subject: str) -> List[str]:
    """Jalankan semua kanal yang aktif; kegagalan dicatat, tidak menghentikan run."""
    log: List[str] = []
    cfg = notify_cfg or {}

    if cfg.get("telegram"):
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat = env.get("TELEGRAM_CHAT_ID", "").strip()
        if token and chat:
            try:
                send_telegram(token, chat, summary_text)
                log.append("telegram: terkirim")
            except Exception as exc:
                log.append(f"telegram: GAGAL ({type(exc).__name__}: {exc})")
        else:
            log.append("telegram: dilewati (secret TELEGRAM_BOT_TOKEN/"
                       "TELEGRAM_CHAT_ID belum diset)")

    email_cfg = cfg.get("email") or {}
    if email_cfg.get("enabled"):
        host = env.get("SMTP_HOST", "").strip()
        to = [str(x) for x in (email_cfg.get("to") or [])]
        if host and to:
            try:
                send_email(
                    host=host,
                    port=int(env.get("SMTP_PORT", "587")),
                    user=env.get("SMTP_USER", ""),
                    password=env.get("SMTP_PASSWORD", ""),
                    sender=env.get("SMTP_FROM", env.get("SMTP_USER", "media-monitor")),
                    to=to,
                    subject=subject,
                    text_body=summary_text,
                    html_body=html_body,
                )
                log.append(f"email: terkirim ke {len(to)} penerima")
            except Exception as exc:
                log.append(f"email: GAGAL ({type(exc).__name__}: {exc})")
        else:
            log.append("email: dilewati (secret SMTP_HOST belum diset atau "
                       "daftar 'to' kosong)")
    return log
