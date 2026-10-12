"""Загрузка картинок из админ-панели: обложки событий и материалов.

Любой файл перекодируем сами (Pillow) и сохраняем под сгенерированным именем —
исходные байты и имя файла от клиента на диск не попадают. HEIC с телефона
открывается так же, как в avatar_client.

Куда кладём: на Railway постоянный том смонтирован ТОЛЬКО в static/avatars
(остальная файловая система стирается при каждом деплое), поэтому загрузки
лежат в static/avatars/uploads/ и отдаются по /static/avatars/uploads/<имя>.
"""
import os
import secrets

import pillow_heif
from PIL import Image, ImageEnhance, ImageOps

pillow_heif.register_heif_opener()

UPLOAD_DIR = os.path.join("static", "avatars", "uploads")
UPLOAD_URL = "/static/avatars/uploads"

# Тёмная версия обложки (для карточки «Ближайшее событие» на Главной) — то же
# затемнение, что у присланных пар: ×0.47.
DARK_FACTOR = 0.47


def _open(file_stream) -> Image.Image:
    try:
        image = Image.open(file_stream)
        image.load()
    except Exception as exc:
        raise ValueError("invalid_image") from exc
    return ImageOps.exif_transpose(image).convert("RGB")


def _crop_to_ratio(image: Image.Image, ratio: float) -> Image.Image:
    """Обрезает по центру до ширина/высота = ratio."""
    width, height = image.size
    if width / height > ratio:
        new_width = int(round(height * ratio))
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = int(round(width / ratio))
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def _save(image: Image.Image, name: str, quality: int) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    image.save(os.path.join(UPLOAD_DIR, name), "JPEG", quality=quality, optimize=True, progressive=True)
    return f"{UPLOAD_URL}/{name}"


def _token() -> str:
    return secrets.token_hex(6)


def save_event_cover(file_stream, poster: bool = False) -> dict:
    """Обложка события -> {"photo": светлая, "photo_dark": тёмная}.
    Обычное фото режем до 2:1 (1280x640, как остальные обложки); постер с
    текстом (poster=True) оставляем целиком в 16:9 (1280x720) — иначе обрезка
    съест надписи."""
    image = _open(file_stream)
    if poster:
        image = _crop_to_ratio(image, 16 / 9)
        light = image.resize((1280, 720), Image.LANCZOS)
        dark_src = image.resize((1200, 675), Image.LANCZOS)
        light_q = 86
    else:
        image = _crop_to_ratio(image, 2.0)
        light = image.resize((1280, 640), Image.LANCZOS)
        dark_src = image.resize((1200, 600), Image.LANCZOS)
        light_q = 84
    dark = ImageEnhance.Brightness(dark_src).enhance(DARK_FACTOR)
    token = _token()
    return {
        "photo": _save(light, f"event-{token}.jpg", light_q),
        "photo_dark": _save(dark, f"event-{token}-dark.jpg", 80),
    }


def save_event_photo_only(file_stream, dark: bool = False) -> str:
    """Заменить только одну из двух обложек — тёмную можно загрузить готовую."""
    image = _crop_to_ratio(_open(file_stream), 2.0)
    size = (1200, 600) if dark else (1280, 640)
    name = f"event-{_token()}{'-dark' if dark else ''}.jpg"
    return _save(image.resize(size, Image.LANCZOS), name, 80 if dark else 84)


def save_material_cover(file_stream) -> str:
    """Постер материала: 16:9, 1280x720 — показывается в Материалах целиком."""
    image = _crop_to_ratio(_open(file_stream), 16 / 9)
    return _save(image.resize((1280, 720), Image.LANCZOS), f"material-{_token()}.jpg", 86)
