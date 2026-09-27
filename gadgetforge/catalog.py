from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CATALOG_PATH = Path(__file__).parent / "actions" / "catalog.json"
TEMPLATES_DIR = Path(__file__).parent / "actions" / "templates"


class ActionParameter(BaseModel):
    key: str
    label: str
    type: str = "string"
    default: Any = None


class ActionDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: str
    platforms: list[str]
    required: bool = False
    parameters: list[ActionParameter] = Field(default_factory=list)
    template: str


class ActionCatalog(BaseModel):
    version: int
    actions: list[ActionDefinition]


def load_catalog() -> ActionCatalog:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return ActionCatalog.model_validate(data)


def get_action(action_id: str) -> ActionDefinition | None:
    catalog = load_catalog()
    for action in catalog.actions:
        if action.id == action_id:
            return action
    return None


def list_actions(platform: str | None = None) -> list[ActionDefinition]:
    catalog = load_catalog()
    if not platform:
        return catalog.actions
    return [a for a in catalog.actions if platform in a.platforms or "generic" in a.platforms]
