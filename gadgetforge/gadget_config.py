from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class InteractionType(str, Enum):
    LISTEN = "listen"
    CONNECT = "connect"
    SCRIPT = "script"
    SCRIPT_DIRECTORY = "scriptdirectory"


class OnLoad(str, Enum):
    WAIT = "wait"
    RESUME = "resume"


class OnPortConflict(str, Enum):
    FAIL = "fail"
    PICK_NEXT = "pick-next"


class ListenInteraction(BaseModel):
    type: Literal["listen"] = "listen"
    address: str = "127.0.0.1"
    port: int = Field(default=27042, ge=1, le=65535)
    on_port_conflict: OnPortConflict = OnPortConflict.FAIL
    on_load: OnLoad = OnLoad.WAIT


class ConnectInteraction(BaseModel):
    type: Literal["connect"] = "connect"
    address: str = "127.0.0.1"
    port: int = Field(default=27042, ge=1, le=65535)
    on_port_conflict: OnPortConflict = OnPortConflict.FAIL
    on_load: OnLoad = OnLoad.WAIT


class ScriptInteraction(BaseModel):
    type: Literal["script"] = "script"
    path: str
    on_change: Literal["ignore", "reload"] = "ignore"
    on_load: OnLoad = OnLoad.WAIT


class ScriptDirectoryInteraction(BaseModel):
    type: Literal["scriptdirectory"] = "scriptdirectory"
    path: str
    on_change: Literal["ignore", "reload"] = "ignore"
    on_load: OnLoad = OnLoad.WAIT


class GadgetConfig(BaseModel):
    interaction: (
        ListenInteraction
        | ConnectInteraction
        | ScriptInteraction
        | ScriptDirectoryInteraction
    )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent)

    def suggested_filename(self, gadget_binary_name: str = "libfrida-gadget") -> str:
        return f"{gadget_binary_name}.config.so"


def default_listen_config() -> GadgetConfig:
    return GadgetConfig(interaction=ListenInteraction())


def merge_script_interaction(
    base: GadgetConfig,
    script_path: str,
    on_change: Literal["ignore", "reload"] = "reload",
) -> GadgetConfig:
    """After attach, scripts are loaded by the host; for embedded gadget use script mode."""
    return GadgetConfig(
        interaction=ScriptInteraction(
            path=script_path,
            on_change=on_change,
            on_load=base.interaction.on_load
            if hasattr(base.interaction, "on_load")
            else OnLoad.WAIT,
        )
    )


def android_packaging_notes() -> dict[str, Any]:
    return {
        "extractNativeLibs": 'Set android:extractNativeLibs="true" in the manifest so config sits beside the .so on disk.',
        "configNaming": "Config must share the gadget library basename with a .config suffix (e.g. libfrida-gadget.config.so).",
        "scriptPathAndroid": 'Embedded script paths often use libfrida-gadget.script.so relative to the library directory.',
    }
