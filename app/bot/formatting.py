from __future__ import annotations

from datetime import date
from typing import Iterable


def format_good_morning() -> str:
    return "Доброе утро, семья! ☕️ Желаю всем классного дня!"


def format_good_night() -> str:
    return "Спокойной ночи, семья 😴 Пусть завтра будет ещё лучше, чем сегодня."


def format_activity_summary(
    today: date,
    inactive_users: Iterable[str],
) -> str:
    users = list(inactive_users)
    if not users:
        return (
            f"Сегодня ({today:%d.%m.%Y}) все отметились в чате. "
            "Вы супер команда! ❤️"
        )
    mentions = ", ".join(users)
    return (
        f"Сегодня ({today:%d.%m.%Y}) ещё никто не писал: {mentions}.\n"
        "Забегайте в чат хотя бы с парой слов 😊"
    )

