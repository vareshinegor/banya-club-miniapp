"""Обработка загрузки фото-аватара резидента.

Телефоны (особенно iPhone) по умолчанию сохраняют фото в HEIC — браузер такой
файл напрямую не отображает, поэтому конвертируем в JPEG на сервере, заодно
приводя к квадрату и разумному размеру, чтобы не грузить лишние мегабайты в
Telegram WebView.

Хранится как static/avatars/<telegram_id>.jpg — то есть без записи в Google
Таблицу: фронтенд просто обращается по предсказуемому пути.
"""
import os

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

AVATAR_DIR = os.path.join("static", "avatars")
AVATAR_SIZE = 512


def avatar_path(telegram_id) -> str:
    return os.path.join(AVATAR_DIR, f"{telegram_id}.jpg")


def save_avatar(telegram_id, file_stream) -> None:
    """Сохраняет присланное фото. Поднимает ValueError, если файл не похож на
    изображение (битый файл, не тот формат и т.п.)."""
    try:
        image = Image.open(file_stream)
        image.load()
    except Exception as exc:
        raise ValueError("invalid_image") from exc

    # exif_transpose — на фото с телефона поворот часто прописан только в EXIF,
    # без этого шага портрет может сохраниться боком/вверх ногами.
    image = ImageOps.exif_transpose(image).convert("RGB")

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    if side > AVATAR_SIZE:
        image = image.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)

    os.makedirs(AVATAR_DIR, exist_ok=True)
    image.save(avatar_path(telegram_id), "JPEG", quality=85)
