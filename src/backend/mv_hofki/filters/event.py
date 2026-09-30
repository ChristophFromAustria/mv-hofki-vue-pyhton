"""Filter for GET /events (the event log)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import Select

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.event import Event

# Areas of the log page; "item" also covers its loans, invoices and images.
AREAS = {
    "item": ("item", "loan", "invoice", "image"),
    "musician": ("musician",),
    "loan": ("loan",),
    "invoice": ("invoice",),
    "master_data": (
        "instrument_type",
        "clothing_type",
        "register",
        "general_item_category",
        "sheet_music_genre",
        "currency",
    ),
    "import": ("import",),
}


class EventFilter(ListFilter):
    item_id: int | None = None
    musician_id: int | None = None
    area: str | None = None
    actor: str | None = None
    action: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    class Constants(ListFilter.Constants):
        model = Event
        search_model_fields = ["entity_label", "summary"]
        # Same second: the later row (higher id) first as well.
        sort_fields = {"at": [Event.at, Event.id]}
        default_sort = ["-at"]

    def filter_area(self, query: Select, value: str) -> Select:
        return query.where(Event.entity_type.in_(AREAS.get(value, (value,))))

    def filter_actor(self, query: Select, value: str) -> Select:
        # "unknown" = no Cloudflare e-mail (local use, CLI)
        if value == "unknown":
            return query.where(Event.actor.is_(None))
        return query.where(Event.actor == value)

    def filter_date_from(self, query: Select, value: date) -> Select:
        return query.where(Event.at >= datetime.combine(value, time.min))

    def filter_date_to(self, query: Select, value: date) -> Select:
        return query.where(
            Event.at < datetime.combine(value + timedelta(days=1), time.min)
        )
