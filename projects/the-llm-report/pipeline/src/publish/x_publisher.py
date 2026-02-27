"""
The LLM Report — X/Twitter Publisher
Posts edition announcements to @thellmreport after a successful publish.
NLSpec Section 5 — "Cross-post summaries to Twitter/X with links back."
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


def _load_env() -> dict:
    env_path = Path(__file__).parent.parent.parent.parent.parent.parent / ".env"
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env


def _get_client():
    """Return an authenticated Tweepy Client (API v2)."""
    import tweepy
    env = _load_env()
    return tweepy.Client(
        consumer_key=env.get("X_API_KEY") or os.environ.get("X_API_KEY"),
        consumer_secret=env.get("X_API_SECRET") or os.environ.get("X_API_SECRET"),
        access_token=env.get("X_ACCESS_TOKEN") or os.environ.get("X_ACCESS_TOKEN"),
        access_token_secret=env.get("X_ACCESS_SECRET") or os.environ.get("X_ACCESS_SECRET"),
    )


def _build_tweet(edition_date: str, headline: str, article_count: int) -> str:
    """
    Build the edition announcement tweet.
    Max 280 chars. Format:
      New edition: {headline}
      {article_count} stories → thellmreport.com/editions/YYYY-MM-DD
      #AI #LLM
    """
    url = f"https://thellmreport.com/editions/{edition_date}"
    tag_line = "#AI #LLM"
    story_word = "story" if article_count == 1 else "stories"
    footer = f"{article_count} {story_word} → {url}\n{tag_line}"

    # Truncate headline if needed to stay under 280 total
    max_headline = 280 - len("New edition: \n") - len(footer) - 2
    if len(headline) > max_headline:
        headline = headline[: max_headline - 1] + "…"

    return f"New edition: {headline}\n{footer}"


def post_edition(
    edition_date: str,
    headline: str,
    article_count: int,
    dry_run: bool = False,
) -> dict:
    """
    Post an edition announcement tweet.

    Args:
        edition_date: YYYY-MM-DD
        headline: Lead story headline or edition title
        article_count: Number of articles in the edition
        dry_run: If True, build the tweet but don't post it

    Returns:
        dict with: tweet_id, tweet_text, posted (bool), error (str|None)
    """
    tweet_text = _build_tweet(edition_date, headline, article_count)

    if dry_run:
        return {"tweet_id": None, "tweet_text": tweet_text, "posted": False, "error": None}

    try:
        client = _get_client()
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data["id"] if response.data else None
        return {"tweet_id": tweet_id, "tweet_text": tweet_text, "posted": True, "error": None}
    except Exception as e:
        return {"tweet_id": None, "tweet_text": tweet_text, "posted": False, "error": str(e)}
