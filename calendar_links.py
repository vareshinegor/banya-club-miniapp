"""«Добавить в календарь»: ссылки на Google Календарь и Outlook и файл .ics
(Apple Календарь, Яндекс, Outlook на компьютере и любые другие программы).

Время события берём из колонок «Дата» и «Время» афиши: «10:30–13:30» — начало и
конец, «18:00» — начало (длительность по умолчанию DEFAULT_EVENT_DURATION_MIN),
пусто — событие на весь день. Время московское; в календарь отдаём его в UTC
(«...Z»), поэтому у человека в другом часовом поясе оно пересчитается верно —
важно для Zoom-эфиров.

Файл .ics отдаётся по подписанной ссылке без сессии: его открывает внешний
браузер/приложение календаря, а не Telegram, куки там нет.
"""
import hashlib
import hmac
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from config import Config
from constants import DEFAULT_EVENT_DURATION_MIN, EVENT_TZ_OFFSET_HOURS

EVENT_TZ = timezone(timedelta(hours=EVENT_TZ_OFFSET_HOURS))
_TIME = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})")


def sign(event_id) -> str:
    return hmac.new(Config.SECRET_KEY.encode("utf-8"), f"calendar:{event_id}".encode(), hashlib.sha256).hexdigest()[:20]


def verify(event_id, signature: str) -> bool:
    return hmac.compare_digest(sign(event_id), signature or "")


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime((value or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def event_span(event: dict) -> Optional[dict]:
    """{"all_day": True, "start": date, "end": date(+1 день)} или
    {"all_day": False, "start": datetime UTC, "end": datetime UTC}; None, если
    дату разобрать не удалось."""
    day = _parse_date(event.get("Дата", ""))
    if not day:
        return None
    times = [
        (int(h), int(m)) for h, m in _TIME.findall(event.get("Время", "") or "")
        if int(h) < 24 and int(m) < 60
    ]
    if not times:
        return {"all_day": True, "start": day, "end": day + timedelta(days=1)}
    start = datetime(day.year, day.month, day.day, times[0][0], times[0][1], tzinfo=EVENT_TZ)
    if len(times) > 1:
        end = datetime(day.year, day.month, day.day, times[1][0], times[1][1], tzinfo=EVENT_TZ)
        if end <= start:  # «22:00–01:00»
            end += timedelta(days=1)
    else:
        end = start + timedelta(minutes=DEFAULT_EVENT_DURATION_MIN)
    return {"all_day": False, "start": start.astimezone(timezone.utc), "end": end.astimezone(timezone.utc)}


def _utc(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _day(d: date) -> str:
    return d.strftime("%Y%m%d")


def _details(event: dict, span: dict) -> str:
    parts = []
    if (event.get("Описание") or "").strip():
        parts.append(event["Описание"].strip())
    if not span["all_day"] and (event.get("Время") or "").strip():
        parts.append(f"Время по Москве: {event['Время'].strip()}")
    parts.append("Банный Орден")
    return "\n".join(parts)


def google_url(event: dict) -> Optional[str]:
    span = event_span(event)
    if not span:
        return None
    dates = f"{_day(span['start'])}/{_day(span['end'])}" if span["all_day"] else f"{_utc(span['start'])}/{_utc(span['end'])}"
    query = "&".join(
        f"{k}={quote(v, safe='')}"
        for k, v in (
            ("action", "TEMPLATE"),
            ("text", event.get("Название", "")),
            ("dates", dates),
            ("details", _details(event, span)),
            ("location", event.get("Место", "") or ""),
        )
    )
    return f"https://calendar.google.com/calendar/render?{query}"


def outlook_url(event: dict) -> Optional[str]:
    span = event_span(event)
    if not span:
        return None
    if span["all_day"]:
        when = [("startdt", span["start"].isoformat()), ("enddt", span["end"].isoformat()), ("allday", "true")]
    else:
        when = [("startdt", span["start"].strftime("%Y-%m-%dT%H:%M:%SZ")), ("enddt", span["end"].strftime("%Y-%m-%dT%H:%M:%SZ"))]
    query = "&".join(
        f"{k}={quote(v, safe='')}"
        for k, v in (
            [("path", "/calendar/action/compose"), ("rru", "addevent"), ("subject", event.get("Название", ""))]
            + when
            + [("body", _details(event, span)), ("location", event.get("Место", "") or "")]
        )
    )
    return f"https://outlook.live.com/calendar/0/deeplink/compose?{query}"


def _escape(text: str) -> str:
    """Экранирование значения свойства iCalendar (RFC 5545, 3.3.11)."""
    return (
        (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    """Строки в .ics не длиннее 75 октетов; длинные переносим (продолжение
    начинается с пробела), не разрывая многобайтовые символы."""
    out, current, size, limit = [], "", 0, 75
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > limit:
            out.append(current)
            current, size, limit = " ", 1, 75
        current += ch
        size += n
    out.append(current)
    return "\r\n".join(out)


def build_ics(event: dict, app_url: str = "") -> Optional[str]:
    span = event_span(event)
    if not span:
        return None
    title = event.get("Название", "")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Banny Orden//Mini App//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:banya-event-{event.get('id')}@banyaorden",
        f"DTSTAMP:{_utc(datetime.now(timezone.utc))}",
    ]
    if span["all_day"]:
        lines += [f"DTSTART;VALUE=DATE:{_day(span['start'])}", f"DTEND;VALUE=DATE:{_day(span['end'])}"]
    else:
        lines += [f"DTSTART:{_utc(span['start'])}", f"DTEND:{_utc(span['end'])}"]
    lines.append(f"SUMMARY:{_escape(title)}")
    if (event.get("Место") or "").strip():
        lines.append(f"LOCATION:{_escape(event['Место'].strip())}")
    lines.append(f"DESCRIPTION:{_escape(_details(event, span))}")
    if app_url:
        lines.append(f"URL:{app_url}")
    lines += ["STATUS:CONFIRMED", "TRANSP:OPAQUE"]
    if not span["all_day"]:
        lines += [
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape('Скоро: ' + title)}", "TRIGGER:-PT1H", "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def links(event: dict, base_url: str) -> Optional[dict]:
    """Три способа добавить событие в календарь для мини-аппа. None — у события
    нет понятной даты."""
    if not event_span(event):
        return None
    return {
        "google": google_url(event),
        "outlook": outlook_url(event),
        "ics": f"{base_url.rstrip('/')}/api/calendar/{event['id']}.ics?s={sign(event['id'])}",
    }
