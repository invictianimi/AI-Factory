"""
The LLM Report — Compliance Checker
Enforces editorial standards before publication.
NLSpec Section 5.6
"""

from __future__ import annotations
import re
from typing import Callable, Optional

from pipeline.src.models import ComplianceResult, EditedArticle

# Prohibited promotional phrases (NLSpec Section 5.5 / 5.6)
PROMO_PHRASES = [
    "revolutionary",
    "game-changing",
    "groundbreaking",
    "unprecedented",
    "amazing",
    "incredible",
    "stunning",
    "exciting",
    "fantastic",
]

# First-person patterns (case-insensitive)
FIRST_PERSON_PATTERNS = [
    r"\bI\b",        # standalone "I"
    r"\bwe\b",       # standalone "we"
    r"\bour\b",      # standalone "our"
    r"\bI'm\b",
    r"\bI've\b",
    r"\bI'll\b",
    r"\bI'd\b",
    r"\bwe're\b",
    r"\bwe've\b",
    r"\bwe'll\b",
    r"\bwe'd\b",
]

# Emoji detection: any character with Unicode category "So" (symbol, other) or
# chars in common emoji ranges outside BMP / high BMP ranges
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # misc symbols and pictographs
    "\U0001F680-\U0001F6FF"  # transport and map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002600-\U000027BF"  # misc symbols
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

# Bullet point pattern: lines starting with -, *, or •
_BULLET_RE = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)

# Direct quote pattern: text inside double quotes
_QUOTE_RE = re.compile(r'"([^"]{1,500})"')


def _strip_direct_quotes(text: str) -> str:
    """Remove text inside double-quoted speech (attributed quotes) before checking voice."""
    # Remove content inside double quotes — these are sourced quotes, not the author's voice
    return re.sub(r'"[^"]*"', '"…"', text)


def _check_first_person(text: str) -> list[str]:
    """
    Return list of first-person violations found in text.
    Direct quotes (inside double quotes) are excluded — they represent
    attributed speech and do not reflect the author's voice.
    """
    # Strip quoted speech before checking — "We are committed to safety" is a CEO quote,
    # not the journalist's first-person voice.
    text_without_quotes = _strip_direct_quotes(text)
    violations: list[str] = []
    for pattern in FIRST_PERSON_PATTERNS:
        matches = re.findall(pattern, text_without_quotes, flags=re.IGNORECASE)
        if matches:
            violations.append(f"First person '{matches[0]}' found in article")
    return violations


def _check_promo_language(text: str) -> list[str]:
    """Return list of promotional phrases found (case-insensitive)."""
    found: list[str] = []
    text_lower = text.lower()
    for phrase in PROMO_PHRASES:
        if phrase.lower() in text_lower:
            found.append(phrase)
    return found


def _check_emoji(text: str) -> list[str]:
    """Return list of emoji violations."""
    matches = _EMOJI_RE.findall(text)
    if matches:
        return [f"Emoji found in article body: {m!r}" for m in matches[:3]]
    return []


def _check_bullet_points(text: str) -> list[str]:
    """Return list of bullet point violations in body text."""
    matches = _BULLET_RE.findall(text)
    if matches:
        return [f"Bullet point found in body ({len(matches)} instance(s))"]
    return []


def _check_headline_length(headline: str) -> list[str]:
    """Return violation if headline exceeds 80 characters."""
    if len(headline) > 80:
        return [f"Headline too long: {len(headline)} chars (max 80)"]
    return []


def _check_long_quotes(text: str) -> list[str]:
    """
    Find direct quotes longer than 14 words.
    Returns list of offending quote strings.
    """
    long_quotes: list[str] = []
    for match in _QUOTE_RE.finditer(text):
        quoted = match.group(1)
        word_count = len(quoted.split())
        if word_count > 14:
            long_quotes.append(quoted)
    return long_quotes


def _check_attribution(text: str) -> list[str]:
    """
    Check that paragraphs with specific claims have source attribution.
    Heuristic: paragraphs containing numbers/statistics or named entities
    should contain 'according to', 'said', 'stated', 'reported', or a URL.
    Returns list of warnings (not hard failures).
    """
    attribution_markers = [
        "according to", "said ", "stated ", "reported ", "confirmed ",
        "announced ", "told ", "wrote ", "per ", "noted "
    ]
    violations: list[str] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paragraphs:
        # Skip short paragraphs and analysis sections
        if len(para) < 40:
            continue
        if para.startswith("**Analysis:**"):
            continue
        # Check if paragraph has factual claims (numbers or proper nouns)
        has_numbers = bool(re.search(r'\d+', para))
        if has_numbers:
            para_lower = para.lower()
            has_attribution = any(marker in para_lower for marker in attribution_markers)
            # Also accept source footnote markers or URLs
            has_url = "http" in para_lower or "source" in para_lower
            if not has_attribution and not has_url:
                snippet = para[:60].replace("\n", " ")
                violations.append(f"Paragraph with numbers may lack attribution: \"{snippet}...\"")
    return violations


def check_compliance(article: EditedArticle) -> ComplianceResult:
    """
    Run all compliance checks against an EditedArticle.

    Checks:
    - No first person
    - No promotional language
    - No emoji
    - No bullet points in body
    - Headline <= 80 chars
    - No direct quotes > 14 words
    - Attribution in paragraphs with factual claims

    Returns:
        ComplianceResult with passed=True/False and all violations listed.
    """
    full_text = (
        f"{article.headline}\n"
        f"{article.subheadline}\n"
        f"{article.lead_paragraph}\n"
        f"{article.body}\n"
        f"{article.analysis_section or ''}"
    )

    failures: list[str] = []

    # 1. First person
    failures.extend(_check_first_person(full_text))

    # 2. Promotional language
    promo_found = _check_promo_language(full_text)
    failures.extend([f"Promotional phrase: '{p}'" for p in promo_found])

    # 3. Emoji
    failures.extend(_check_emoji(full_text))

    # 4. Bullet points in body
    body_text = f"{article.lead_paragraph}\n{article.body}"
    failures.extend(_check_bullet_points(body_text))

    # 5. Headline length
    failures.extend(_check_headline_length(article.headline))

    # 6. Long quotes (> 14 words)
    long_quotes = _check_long_quotes(full_text)
    if long_quotes:
        failures.extend([f"Quote exceeds 14 words ({len(q.split())} words): \"{q[:80]}...\"" for q in long_quotes])

    # 7. Attribution (advisory — appended to failures as warnings)
    attribution_warnings = _check_attribution(
        f"{article.lead_paragraph}\n\n{article.body}"
    )
    # Attribution warnings are soft — don't fail compliance, but log them
    # (per NLSpec: "every paragraph with specific claims should have attribution")
    # We add them as failures only if > 2 paragraphs lack attribution
    if len(attribution_warnings) > 2:
        failures.extend(attribution_warnings[:2])  # cap at 2 to avoid noise

    passed = len(failures) == 0

    return ComplianceResult(
        article=article,
        passed=passed,
        failures=failures,
        long_quotes=long_quotes,
        promotional_phrases=promo_found,
        rewrite_loop=0,
        compliance_cost_usd=0.0,
    )


def rewrite_loop(
    article: EditedArticle,
    llm_rewriter: Callable[[EditedArticle, list[str]], EditedArticle],
    max_loops: int = 3,
) -> tuple[EditedArticle, ComplianceResult, int]:
    """
    Rewrite article until it passes compliance or max_loops is reached.

    Args:
        article: The article to check and potentially rewrite.
        llm_rewriter: Callable that takes (article, failures) and returns a new EditedArticle.
        max_loops: Maximum number of rewrite attempts (default 3).

    Returns:
        Tuple of (final_article, final_compliance_result, loops_used).
        If max_loops is reached without passing, returns the last article with failed result.
    """
    current_article = article
    loops_used = 0

    for attempt in range(max_loops + 1):
        result = check_compliance(current_article)
        result = ComplianceResult(
            article=result.article,
            passed=result.passed,
            failures=result.failures,
            long_quotes=result.long_quotes,
            promotional_phrases=result.promotional_phrases,
            rewrite_loop=attempt,
            compliance_cost_usd=result.compliance_cost_usd,
        )

        if result.passed:
            loops_used = attempt
            return current_article, result, loops_used

        if attempt == max_loops:
            # Exhausted all attempts
            loops_used = attempt
            return current_article, result, loops_used

        # Request rewrite with failure list
        current_article = llm_rewriter(current_article, result.failures)

    # Should not reach here
    final_result = check_compliance(current_article)
    return current_article, final_result, max_loops
