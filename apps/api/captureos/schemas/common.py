"""Shared schema base. camelCase on the wire, snake_case in Python (PRD §9)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Health(CamelModel):
    status: str
    version: str
    environment: str
