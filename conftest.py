"""
Root conftest.py — adds project directories to sys.path so that
`pipeline.src.*` and `orchestrator.*` imports resolve correctly.
Sets HF_HOME to a local writable cache so the embedding model loads.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
PROJECT_ROOT = REPO_ROOT / "projects" / "the-llm-report"

for path in (str(REPO_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# Point HuggingFace to a writable local cache directory
hf_cache = str(REPO_ROOT / ".hf_cache")
os.environ.setdefault("HF_HOME", hf_cache)
os.environ.setdefault("TRANSFORMERS_CACHE", hf_cache)
