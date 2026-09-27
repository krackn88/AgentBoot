from __future__ import annotations

from threading import Lock

from gadgetforge.checker.models import CheckerRecipe

_lock = Lock()
_active_recipe: CheckerRecipe | None = None


def get_recipe() -> CheckerRecipe | None:
    with _lock:
        return _active_recipe


def set_recipe(recipe: CheckerRecipe) -> None:
    global _active_recipe
    with _lock:
        _active_recipe = recipe
