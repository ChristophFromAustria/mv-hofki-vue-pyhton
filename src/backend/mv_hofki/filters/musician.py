"""Filter for GET /musicians."""

from __future__ import annotations

from sqlalchemy import Select, select

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import musician_registers


class MusicianFilter(ListFilter):
    is_active: bool | None = None
    is_extern: bool | None = None
    register_id__in: list[int] | None = None

    class Constants(ListFilter.Constants):
        model = Musician
        search_model_fields = ["first_name", "last_name", "email", "city"]
        sort_fields = {
            "last_name": [Musician.last_name],
            "first_name": [Musician.first_name],
        }
        default_sort = ["last_name", "first_name"]

    def filter_register_id__in(self, query: Select, value: list[int]) -> Select:
        members = select(musician_registers.c.musician_id).where(
            musician_registers.c.register_id.in_(value)
        )
        return query.where(Musician.id.in_(members))
