"""
The LLM Report — Regex Tagger
Auto-tags items before LLM calls. Only calls LLM if regex tagging is ambiguous.
Cost optimization: prevents LLM calls for obvious patterns.
NLSpec Section 5.1
"""

from __future__ import annotations
import re

# Pattern map: tag → list of regex patterns
TAG_PATTERNS: dict[str, list[str]] = {
    "model-release": [
        r"\bnew model\b", r"\bmodel release\b", r"\breleas(es|ed|ing)\b",
        r"\blaunch(es|ed|ing)\b", r"\bintroduc(es|ed|ing)\b", r"\bannounc(es|ed|ing)\b",
        r"v\d+\.\d+", r"\bgpt-\d", r"\bclaude-\d", r"\bgemini[\s-]\d",
        r"\bllama[\s-]\d", r"\bdeepseek[\s-]v\d", r"\bqwen[\s-]\d",
        r"\bmistral[\s-]\d", r"\bsona?net[\s-]\d", r"\bopus[\s-]\d",
        r"\bhaiku[\s-]\d", r"\bparameter count\b", r"\bbillion parameter",
    ],
    "api-update": [
        r"\bapi update\b", r"\bnew endpoint\b", r"\bapi change\b",
        r"\bdeprecated?\b", r"\brate limit\b", r"\bbreaking change\b",
        r"\bapi version\b", r"\bsdk update\b", r"\bapi key\b",
    ],
    "security-patch": [
        r"\bsecurity\b", r"\bvulnerability\b", r"\bCVE-\d+",
        r"\bpatch(es|ed|ing)?\b", r"\bexploit\b", r"\bsafety incident\b",
        r"\bjailbreak\b", r"\bbreach\b",
    ],
    "acquisition": [
        r"\bacquir(es|ed|ing|ition)\b", r"\bmerger\b", r"\bbuys\b",
        r"\bpurchas(es|ed|ing)\b", r"\btakeover\b", r"\bbuyout\b",
    ],
    "partnership": [
        r"\bpartner(s|ship|ing)?\b", r"\bcollaboration\b", r"\bagreement\b",
        r"\bjoint venture\b", r"\bintegration\b", r"\bteam(ing)? up\b",
    ],
    "research-paper": [
        r"\bpaper\b", r"\bresearch\b", r"\bstudy\b", r"\barxiv\b",
        r"\bbenchmark\b", r"\bevals?\b", r"\bpeer.review\b",
        r"\bpublish(ed|ing)?\b", r"\bfindings?\b",
    ],
    "framework-release": [
        r"\bframework\b", r"\blibrary\b", r"\bsdk\b", r"\btoolkit\b",
        r"\bopen.sourc(e|ed)\b", r"\bgithub release\b", r"\bpackage release\b",
        r"\bagent framework\b", r"\borchestrat\b",
    ],
    "methodology": [
        r"\bmethodology\b", r"\bbest practice\b", r"\bworkflow\b",
        r"\bsoftware factory\b", r"\bagent(ic)? pattern\b", r"\bmulti.agent\b",
    ],
    "policy-regulatory": [
        r"\bregulat(ion|ory|ed)\b", r"\bpolicy\b", r"\bgovernment\b",
        r"\blegislat(ion|ure)\b", r"\bcompliance\b", r"\bEU AI Act\b",
        r"\bexecutive order\b", r"\bsafety guideline\b",
    ],
    "benchmark": [
        r"\bbenchmark\b", r"\bMMBench\b", r"\bHELM\b", r"\bSWE-bench\b",
        r"\bMMLU\b", r"\bstate.of.the.art\b", r"\bSOTA\b",
        r"\bleaderboard\b", r"\bperformance comparison\b",
    ],
    "pricing-change": [
        r"\bpric(e|es|ed|ing)\b", r"\bcost reduction\b", r"\bfree tier\b",
        r"\bsubscription\b", r"\bper.token\b", r"\bcheaper\b",
        r"\btoken cost\b", r"\bAPI cost\b", r"\bplan change\b",
    ],
}

AMBIGUOUS_THRESHOLD = 0  # If 0 tags found, consider ambiguous


def tag_item(title: str, content: str) -> tuple[list[str], bool]:
    """
    Apply regex tagging to an item.
    Returns (tags, is_ambiguous).
    is_ambiguous = True when LLM tagging should be called.
    """
    text = f"{title} {content}".lower()
    tags = []
    for tag, patterns in TAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                tags.append(tag)
                break  # One match per tag is enough

    is_ambiguous = len(tags) == AMBIGUOUS_THRESHOLD
    return tags, is_ambiguous


def extract_model_mentions(text: str) -> list[str]:
    """Extract AI model names mentioned in text."""
    patterns = [
        r"\bGPT-[\d.]+\b", r"\bClaude[\s-][\w.]+\b", r"\bGemini[\s-][\w.]+\b",
        r"\bLLaMA[\s-]?\d+\b", r"\bDeepSeek[\s-][\w.]+\b", r"\bQwen[\s-]?\d+\b",
        r"\bMistral[\s-][\w.]+\b", r"\bGrok[\s-]?\d*\b", r"\bPhi[\s-]?\d+\b",
    ]
    mentions = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        mentions.extend(found)
    return list(set(mentions))


def extract_org_mentions(text: str) -> list[str]:
    """Extract AI organization names mentioned in text."""
    orgs = [
        "OpenAI", "Anthropic", "Google DeepMind", "Google", "Meta",
        "DeepSeek", "Mistral", "Hugging Face", "Microsoft", "Amazon",
        "Apple", "xAI", "Cohere", "AI21", "StrongDM",
    ]
    found = []
    for org in orgs:
        if re.search(r'\b' + re.escape(org) + r'\b', text, re.IGNORECASE):
            found.append(org)
    return found
