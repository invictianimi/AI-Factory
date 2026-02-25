"""
The LLM Report — Core Data Models
Pydantic models for every stage of the pipeline.
"""

from __future__ import annotations
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class CollectedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str
    source_tier: int  # 1, 2, or 3
    url: str
    title: str
    raw_content: str
    published_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)
    significance_score: Optional[float] = None
    promoted: bool = False

    @computed_field
    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.raw_content.encode()).hexdigest()


class TriagedItem(BaseModel):
    item: CollectedItem
    significance: int  # 1-10
    category: str
    rationale: str
    suggested_headline: str
    promoted: bool
    route: str  # "archive", "roundup", "story", "lead"


class StoryGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    primary: TriagedItem
    supporting: list[TriagedItem] = Field(default_factory=list)
    max_significance: int = 0

    def model_post_init(self, __context) -> None:
        scores = [self.primary.significance] + [s.significance for s in self.supporting]
        self.max_significance = max(scores)


class AnalyzedStory(BaseModel):
    group: StoryGroup
    what_happened: str
    why_it_matters: str
    key_details: str
    sources: list[str]
    single_source_claims: list[str] = Field(default_factory=list)
    analysis_angles: list[str] = Field(default_factory=list)
    kb_context_used: bool = False
    llm_call_made: bool = False
    analysis_cost_usd: float = 0.0


class EditedArticle(BaseModel):
    story: AnalyzedStory
    headline: str
    subheadline: str
    lead_paragraph: str
    body: str
    analysis_section: Optional[str] = None
    sources_footer: str
    word_count: int = 0
    editorial_cost_usd: float = 0.0


class ComplianceResult(BaseModel):
    article: EditedArticle
    passed: bool
    failures: list[str] = Field(default_factory=list)
    long_quotes: list[str] = Field(default_factory=list)
    promotional_phrases: list[str] = Field(default_factory=list)
    rewrite_loop: int = 0
    compliance_cost_usd: float = 0.0


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_type: str = "standard"  # "standard" or "deep-dive"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    items_collected: int = 0
    items_triaged: int = 0
    items_published: int = 0
    total_cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)
    status: str = "running"  # "running", "complete", "failed", "paused"
