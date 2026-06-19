from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SchedulerJob:
    job_key: str
    job_type: str
    cron_hour: int
    cron_minute: int
    timezone_name: str
    chat_id: int | None
    enabled: bool
