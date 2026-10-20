"""Личный QR-код профиля для отметки прихода на мероприятие.

В QR зашит не telegram_id «голым», а подписанный код «BO1:<telegram_id>.<подпись>»
(HMAC-SHA256 от SECRET_KEY): подделать код для чужого id нельзя, а посторонняя
программа-сканер увидит просто непонятную строку, без ссылки на админку.
Код постоянный (один на профиль); от пересылки скриншота защищает то, что
админ при сканировании видит фото и имя человека.
"""
import hashlib
import hmac
import io
import re
from typing import Optional

import segno

from config import Config

PREFIX = "BO1:"
_ID = re.compile(r"^\d{3,20}$")


def _sig(telegram_id: str) -> str:
    return hmac.new(Config.SECRET_KEY.encode("utf-8"), f"checkin:{telegram_id}".encode(), hashlib.sha256).hexdigest()[:20]


def make_code(telegram_id) -> str:
    tid = str(telegram_id)
    return f"{PREFIX}{tid}.{_sig(tid)}"


def parse_code(code: str) -> Optional[str]:
    """telegram_id из кода или None, если код не наш / подпись не сошлась."""
    text = (code or "").strip()
    if not text.startswith(PREFIX) or "." not in text:
        return None
    tid, _, signature = text[len(PREFIX):].partition(".")
    if not _ID.match(tid) or not hmac.compare_digest(_sig(tid), signature):
        return None
    return tid


def qr_svg(telegram_id) -> bytes:
    """SVG с QR-кодом профиля: тёмные модули на белом фоне с полями (по бокам
    нужна «тихая зона», иначе сканер не поймает) и viewBox, чтобы картинка
    масштабировалась CSS-размером."""
    qr = segno.make(make_code(telegram_id), error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=1, border=2, dark="#111111", light="#ffffff", xmldecl=False, nl=False)
    svg = buffer.getvalue().decode("utf-8")
    size = qr.symbol_size(border=2)[0]
    svg = svg.replace("<svg ", f'<svg viewBox="0 0 {size} {size}" shape-rendering="crispEdges" ', 1)
    return svg.encode("utf-8")
