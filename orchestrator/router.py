"""
AI Factory — Model Router
Rule-based routing: maps task types to the correct model.
All calls go through LiteLLM proxy — never direct API calls.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaskType(str, Enum):
    # Architecture & Design
    ARCHITECTURE = "architecture"
    DESIGN = "design"
    PLANNING = "planning"

    # Code
    CODE_COMPLEX = "code_complex"
    CODE_ROUTINE = "code_routine"
    CODE_REVIEW = "code_review"

    # Editorial & Writing
    EDITORIAL = "editorial"
    SPEC_WRITING = "spec_writing"

    # Pipeline stages
    COLLECTION = "collection"
    TRIAGE = "triage"
    ANALYSIS = "analysis"
    COMPLIANCE = "compliance"

    # Bridge
    BRIDGE_INTENT = "bridge_intent"

    # Board Review
    BOARD_CHAIR = "board_chair"
    BOARD_ADVERSARIAL = "board_adversarial"
    BOARD_COST_AUDIT = "board_cost_audit"
    BOARD_INTEGRATION = "board_integration"

    # Reports
    DAILY_REPORT_SUMMARY = "daily_report_summary"

    # Generic
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    VERIFICATION = "verification"


@dataclass
class RouteDecision:
    primary_model: str
    review_model: Optional[str]
    rationale: str
    estimated_cost_tier: str  # "low", "medium", "high"


# Model IDs (must match litellm_config.yaml)
class Models:
    OPUS = "claude-opus-4-6"
    SONNET = "claude-sonnet-4-5"
    HAIKU = "claude-haiku-4-5"
    GPT5_PRO = "gpt-5.2-pro"
    DEEPSEEK_R1 = "deepseek-r1"
    DEEPSEEK_V3 = "deepseek-v3"
    GEMINI_PRO = "gemini-2.5-pro"


# Routing table — NEVER have same model build AND review
ROUTING_TABLE: dict[TaskType, RouteDecision] = {
    TaskType.ARCHITECTURE: RouteDecision(
        primary_model=Models.OPUS,
        review_model=Models.GPT5_PRO,
        rationale="Architecture requires deepest reasoning; GPT adversarial review",
        estimated_cost_tier="high",
    ),
    TaskType.DESIGN: RouteDecision(
        primary_model=Models.OPUS,
        review_model=Models.GPT5_PRO,
        rationale="Design requires deep reasoning; GPT adversarial review",
        estimated_cost_tier="high",
    ),
    TaskType.PLANNING: RouteDecision(
        primary_model=Models.OPUS,
        review_model=None,
        rationale="Planning is Opus-only; no separate review needed",
        estimated_cost_tier="high",
    ),
    TaskType.CODE_COMPLEX: RouteDecision(
        primary_model=Models.SONNET,
        review_model=Models.DEEPSEEK_R1,
        rationale="Complex code: Sonnet implements, DeepSeek R1 reviews (15-30x cheaper)",
        estimated_cost_tier="medium",
    ),
    TaskType.CODE_ROUTINE: RouteDecision(
        primary_model=Models.DEEPSEEK_V3,
        review_model=Models.DEEPSEEK_R1,
        rationale="Routine code: cheapest capable model; R1 reviews",
        estimated_cost_tier="low",
    ),
    TaskType.CODE_REVIEW: RouteDecision(
        primary_model=Models.DEEPSEEK_R1,
        review_model=None,
        rationale="R1 is 15-30x cheaper for review tasks",
        estimated_cost_tier="low",
    ),
    TaskType.EDITORIAL: RouteDecision(
        primary_model=Models.OPUS,
        review_model=None,
        rationale="Editorial quality requires Opus; journalist voice",
        estimated_cost_tier="high",
    ),
    TaskType.SPEC_WRITING: RouteDecision(
        primary_model=Models.OPUS,
        review_model=Models.GPT5_PRO,
        rationale="Specs are source of truth; adversarial review critical",
        estimated_cost_tier="high",
    ),
    TaskType.COLLECTION: RouteDecision(
        primary_model=Models.HAIKU,
        review_model=None,
        rationale="Collection is structured scraping; Haiku is sufficient and cheap",
        estimated_cost_tier="low",
    ),
    TaskType.TRIAGE: RouteDecision(
        primary_model=Models.SONNET,
        review_model=None,
        rationale="Triage needs good judgment but not deepest reasoning",
        estimated_cost_tier="medium",
    ),
    TaskType.ANALYSIS: RouteDecision(
        primary_model=Models.OPUS,
        review_model=Models.SONNET,
        rationale="Analysis requires synthesis and multi-source reasoning",
        estimated_cost_tier="high",
    ),
    TaskType.COMPLIANCE: RouteDecision(
        primary_model=Models.SONNET,
        review_model=Models.DEEPSEEK_R1,
        rationale="Compliance is rule-following; Sonnet with R1 verify",
        estimated_cost_tier="medium",
    ),
    TaskType.BRIDGE_INTENT: RouteDecision(
        primary_model=Models.HAIKU,
        review_model=None,
        rationale="Intent classification is simple; Haiku is fast and cheap",
        estimated_cost_tier="low",
    ),
    TaskType.BOARD_CHAIR: RouteDecision(
        primary_model=Models.OPUS,
        review_model=None,
        rationale="Board Chair is Opus — synthesis, final decisions, veto power",
        estimated_cost_tier="high",
    ),
    TaskType.BOARD_ADVERSARIAL: RouteDecision(
        primary_model=Models.GPT5_PRO,
        review_model=None,
        rationale="Adversarial reviewer is GPT — different perspective from Opus",
        estimated_cost_tier="high",
    ),
    TaskType.BOARD_COST_AUDIT: RouteDecision(
        primary_model=Models.DEEPSEEK_R1,
        review_model=None,
        rationale="Cost auditor is DeepSeek — ironic that the cheap model audits costs",
        estimated_cost_tier="low",
    ),
    TaskType.BOARD_INTEGRATION: RouteDecision(
        primary_model=Models.GEMINI_PRO,
        review_model=None,
        rationale="Integration reviewer is Gemini — long-context, systems view",
        estimated_cost_tier="medium",
    ),
    TaskType.DAILY_REPORT_SUMMARY: RouteDecision(
        primary_model=Models.SONNET,
        review_model=None,
        rationale="Daily summary: Sonnet with $0.05 cost cap",
        estimated_cost_tier="low",
    ),
    TaskType.SUMMARIZATION: RouteDecision(
        primary_model=Models.DEEPSEEK_V3,
        review_model=None,
        rationale="High-volume summarization: cheapest capable model",
        estimated_cost_tier="low",
    ),
    TaskType.EXTRACTION: RouteDecision(
        primary_model=Models.HAIKU,
        review_model=None,
        rationale="Simple extraction: Haiku is sufficient",
        estimated_cost_tier="low",
    ),
    TaskType.VERIFICATION: RouteDecision(
        primary_model=Models.DEEPSEEK_R1,
        review_model=None,
        rationale="Verification: R1 is optimized for this",
        estimated_cost_tier="low",
    ),
}


def route(task_type: TaskType) -> RouteDecision:
    """Return the routing decision for a given task type."""
    decision = ROUTING_TABLE.get(task_type)
    if decision is None:
        # Fallback: Sonnet for unknown tasks
        return RouteDecision(
            primary_model=Models.SONNET,
            review_model=None,
            rationale=f"Unknown task type '{task_type}' — defaulting to Sonnet",
            estimated_cost_tier="medium",
        )
    return decision


def get_litellm_base_url() -> str:
    """Return the LiteLLM proxy base URL from environment."""
    return os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")


def get_litellm_api_key() -> str:
    """Return the LiteLLM master key from environment."""
    return os.environ.get("LITELLM_MASTER_KEY", "")
