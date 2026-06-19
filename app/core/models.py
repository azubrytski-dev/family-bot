from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatRecord:
    chat_id: int
    title: str | None
    chat_type: str
    is_active: bool
    is_approved: bool
    allow_test: bool
    removed_at: datetime | None


@dataclass
class SchedulerJob:
    job_key: str
    job_type: str
    cron_hour: int
    cron_minute: int
    timezone_name: str
    chat_id: int | None
    enabled: bool
