from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CalendarEventTypeL = Literal["live", "exam"]


class CalendarEventOut(BaseModel):
    id: str
    type: CalendarEventTypeL
    title: str
    starts_at: datetime
    ends_at: datetime
    course_title: str
    href: str
