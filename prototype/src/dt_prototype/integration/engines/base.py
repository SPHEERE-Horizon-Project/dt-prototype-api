"""Conceptual interface shared by independent physics adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from dt_prototype.integration.schemas import MonthlyPhysicsResults


RequestT = TypeVar("RequestT")


class ForwardPhysicsEngine(ABC, Generic[RequestT]):
    """Return canonical monthly results without sharing heat-balance code."""

    engine_id: str
    engine_version: str

    @abstractmethod
    def simulate(self, inputs: RequestT) -> MonthlyPhysicsResults:
        """Run the wrapped engine and map its output to canonical records."""

