from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckOutcome(str, Enum):
    HIT = "HIT"
    BAD = "BAD"
    RETRY = "RETRY"
    BAN = "BAN"
    CAPTCHA = "CAPTCHA"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class HeaderExtract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: Literal["response_header", "response_body", "request_header"] = Field(
        alias="from"
    )
    name: str
    json_path: str | None = None
    regex: str | None = None
    store_as: str


class FlowStep(BaseModel):
    id: str
    method: str = "GET"
    url: str | None = None
    path: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] | str | None = None
    auth_header: str | None = None
    auth_from: str | None = None
    extracts: list[HeaderExtract] = Field(default_factory=list)
    optional: bool = False
    tags: list[str] = Field(default_factory=list)


class ClassifyRule(BaseModel):
    outcome: CheckOutcome
    step_id: str | None = None
    status_codes: list[int] = Field(default_factory=list)
    body_contains: list[str] = Field(default_factory=list)
    body_regex: str | None = None
    json_path: str | None = None
    json_exists: bool = True
    priority: int = 100


class CheckerRecipe(BaseModel):
    name: str = "discovered-login-flow"
    base_url: str = ""
    platform: str = "android"
    steps: list[FlowStep] = Field(default_factory=list)
    classify: list[ClassifyRule] = Field(default_factory=list)
    notes: str = ""

    def login_step_id(self) -> str | None:
        for step in self.steps:
            if "login" in step.tags or "login" in step.id.lower():
                return step.id
        for step in reversed(self.steps):
            if step.body_template and isinstance(step.body_template, dict):
                blob = str(step.body_template)
                if "password" in blob or "{{password}}" in blob:
                    return step.id
        return self.steps[-1].id if self.steps else None


class CaptureEvent(BaseModel):
    ts: float
    phase: Literal["request", "response"]
    url: str
    method: str
    status: int | None = None
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: str | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    source: str = "gadget"


class CheckResult(BaseModel):
    outcome: CheckOutcome
    email: str
    password: str
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    def line(self) -> str:
        if self.outcome == CheckOutcome.HIT:
            extra = " | ".join(f"{k}={v}" for k, v in self.data.items()) if self.data else ""
            base = f"HIT | {self.email}:{self.password}"
            return f"{base} | {extra}" if extra else base
        return f"{self.outcome.value} | {self.email}:{self.password} | {self.message}"
