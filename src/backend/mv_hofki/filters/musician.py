"""Filter for GET /musicians."""

from __future__ import annotations

from sqlalchemy import Select, case, select

from mv_hofki.filters.base import GroupSpec, ListFilter
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register, musician_registers


def _join_registers(query: Select) -> Select:
    return query.outerjoin(
        musician_registers, musician_registers.c.musician_id == Musician.id
    ).outerjoin(Register, Register.id == musician_registers.c.register_id)


class MusicianFilter(ListFilter):
    is_active: bool | None = None
    is_extern: bool | None = None
    register_id__in: list[int] | None = None

    class Constants(ListFilter.Constants):
        model = Musician
        search_model_fields = ["first_name", "last_name", "email", "city"]
        sort_fields = {
            "last_name": [Musician.last_name, Musician.first_name],
            "first_name": [Musician.first_name, Musician.last_name],
        }
        default_sort = ["last_name", "first_name"]
        group_fields = {
            "register": GroupSpec(
                key=Register.id,
                label=Register.label,
                order=Register.sort_order,
                empty_label="Ohne Register",
                join=_join_registers,
                multi=True,
            ),
            "status": GroupSpec(
                key=case((Musician.is_active, "aktiv"), else_="inaktiv"),
                label=case((Musician.is_active, "Aktiv"), else_="Inaktiv"),
                order=case((Musician.is_active, 0), else_=1),
                empty_label="—",
            ),
        }

    def filter_register_id__in(self, query: Select, value: list[int]) -> Select:
        members = select(musician_registers.c.musician_id).where(
            musician_registers.c.register_id.in_(value)
        )
        return query.where(Musician.id.in_(members))
