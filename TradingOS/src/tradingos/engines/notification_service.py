"""Notification service — Telegram push alerts for T+2.5 signals."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from tradingos.utils.config import cfg

log = logging.getLogger("tradingos.notifications")


class NotificationService:
    """
    Sends push notifications via Telegram Bot API.

    Configuration (config/local.toml):
        [notification]
        telegram_bot_token = "123456789:AAxxxxxxxxxxxxxx"
        telegram_chat_id   = "-1001234567890"
        enabled            = true
    """

    def __init__(self) -> None:
        self._token    = cfg.get("notification", "telegram_bot_token", default="")
        self._chat_id  = cfg.get("notification", "telegram_chat_id", default="")
        self._enabled  = bool(cfg.get("notification", "enabled", default=False))

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    # ── Public API ────────────────────────────────────────────────────────────

    def send_signal_alert(
        self,
        ticker: str,
        action: str,
        mfpm_score: int,
        sms_raw: int,
        tplus_verdict: str,
        entry_price: float,
        stop_loss: float,
        tp1: float,
        confidence: str = "",
        signal_mode: str = "",
    ) -> bool:
        """Send a new signal alert (STRONG_BUY / BUY)."""
        if not self._should_send():
            return False

        conf_badge = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(confidence, "⚪")
        action_icon = "🚀" if action == "STRONG_BUY" else "🟢" if action == "BUY" else "👀"

        text = (
            f"{action_icon} *TradingOS — {action}*\n"
            f"📌 *{ticker}*  {conf_badge} {confidence}\n\n"
            f"MFPM: `{mfpm_score}` · SMS: `{sms_raw}` · Mode: `{signal_mode}`\n"
            f"T\\+ Verdict: `{tplus_verdict}`\n\n"
            f"Entry: `{entry_price:,.0f}` VND\n"
            f"SL: `{stop_loss:,.0f}` · TP1: `{tp1:,.0f}`\n\n"
            f"_Advisory only — không phải khuyến nghị đầu tư_"
        )
        return self._send(text)

    def send_atc_reminder(self, positions: list[dict]) -> bool:
        """Send daily 14:30 ATC reminder for positions due today."""
        if not self._should_send() or not positions:
            return False

        lines = ["⚡ *TradingOS — ATC Reminder* (14:43–14:45)\n"]
        for p in positions:
            ticker = p.get("ticker", "")
            advisory = p.get("advisory")
            action = getattr(advisory, "action", "REVIEW") if advisory else "REVIEW"
            entry  = p.get("entry_price", 0)
            lines.append(f"• *{ticker}* — `{action}`  (vào: `{entry:,.0f}`)")

        lines.append("\n_Kiểm tra app để xem chi tiết_")
        return self._send("\n".join(lines))

    def send_sl_breach_alert(self, ticker: str, entry_price: float, current_price: float, sl: float) -> bool:
        """Send a stop-loss breach warning."""
        if not self._should_send():
            return False
        drop_pct = (current_price - entry_price) / max(entry_price, 1) * 100
        text = (
            f"⛔ *TradingOS — SL Breach Alert*\n"
            f"*{ticker}* đang dưới Stop-Loss!\n\n"
            f"Entry: `{entry_price:,.0f}` · Current: `{current_price:,.0f}` ({drop_pct:+.1f}%)\n"
            f"SL: `{sl:,.0f}`\n\n"
            f"_Cân nhắc thoát lệnh ngay_"
        )
        return self._send(text)

    def send_plain(self, message: str) -> bool:
        """Send arbitrary plain-text message."""
        if not self._should_send():
            return False
        return self._send(message)

    def test_connection(self) -> tuple[bool, str]:
        """
        Test Telegram connectivity.  Returns (success: bool, message: str).
        Does NOT require enabled=True — useful for Settings page health check.
        """
        if not self.is_configured:
            return False, "Chưa cấu hình token/chat_id trong local.toml"
        ok = self._send("✅ TradingOS — Kết nối Telegram thành công!", parse_mode=None)
        return ok, "OK" if ok else "Gửi thất bại — kiểm tra token và chat_id"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _should_send(self) -> bool:
        if not self._enabled:
            return False
        if not self.is_configured:
            log.debug("Notification skipped — not configured")
            return False
        return True

    def _send(self, text: str, parse_mode: str | None = "MarkdownV2") -> bool:
        """
        POST message to Telegram Bot API.
        Returns True on HTTP 200, False otherwise.
        MarkdownV2 special chars in prices are escaped by the caller via :,.0f formatting.
        """
        import urllib.request
        import urllib.parse
        import json as _json

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id":                  self._chat_id,
            "text":                     text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        data = urllib.parse.urlencode(payload).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = _json.loads(resp.read())
                if body.get("ok"):
                    return True
                log.warning("Telegram API error: %s", body.get("description"))
                return False
        except Exception as exc:
            log.warning("Telegram send failed: %s", exc)
            return False


# Module-level singleton
notification_svc = NotificationService()
