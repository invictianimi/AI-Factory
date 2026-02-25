"""
AI Factory Pipeline Framework — Base Stage Interface
Domain-agnostic. No hardcoded source URLs, brand names, or editorial guidelines.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")


@dataclass
class StageResult(Generic[Output]):
    """Result of running a pipeline stage."""
    output: list[Output]
    errors: list[str] = field(default_factory=list)
    stage_name: str = ""
    cost_usd: float = 0.0
    llm_calls: int = 0
    cached_calls: int = 0

    @property
    def success_rate(self) -> float:
        total = len(self.output) + len(self.errors)
        return len(self.output) / total if total > 0 else 1.0


class BaseStage(ABC, Generic[Input, Output]):
    """
    Abstract base class for all pipeline stages.

    Subclass this to implement a pipeline stage. Each stage:
    1. Receives input from the previous stage
    2. Optionally queries the knowledge base (KB-First Pattern)
    3. Optionally calls an LLM
    4. Returns a StageResult

    No stage should contain hardcoded source URLs, brand names,
    or editorial guidelines — those belong in project config.
    """

    def __init__(self, stage_name: str, config: dict | None = None):
        self.stage_name = stage_name
        self.config = config or {}

    @abstractmethod
    def process_item(self, item: Input, **kwargs) -> Output:
        """Process a single input item. Implement in subclass."""
        ...

    def process_batch(
        self,
        items: list[Input],
        max_errors: int = 3,
        **kwargs,
    ) -> StageResult[Output]:
        """
        Process a batch of items.
        Continues on individual errors up to max_errors.
        Override for custom batch behavior.
        """
        results = []
        errors = []
        for item in items:
            try:
                result = self.process_item(item, **kwargs)
                results.append(result)
            except Exception as e:
                errors.append(f"{self.stage_name}: {e}")
                if len(errors) >= max_errors:
                    break
        return StageResult(
            output=results,
            errors=errors,
            stage_name=self.stage_name,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(stage={self.stage_name})"
