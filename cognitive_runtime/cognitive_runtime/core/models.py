from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RuntimeState(StrEnum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class HealthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RuntimeState
    services: dict[str, str]
