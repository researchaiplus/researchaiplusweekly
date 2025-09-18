"""Primary topic classification using heuristics with LLM fallback."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import lru_cache
from urllib.parse import urlparse

from newsletter.io.models import ArticleContent, ClassifiedArticle, PrimaryTopic
from newsletter.services.openrouter_client import OpenRouterClient

LOGGER = logging.getLogger(__name__)

PAPER_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "paperswithcode.com",
    "neurips.cc",
    "acm.org",
    "ieee.org",
}

BLOG_DOMAINS = {
    "medium.com",
    "substack.com",
    "dev.to",
    "hashnode.dev",
    "blogspot.com",
    "wordpress.com",
    "zhihu.com",
    "wechat.com",
}

OPEN_SOURCE_DOMAINS = {"github.com", "gitlab.com", "huggingface.co", "bitbucket.org"}


def _normalize_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


class TopicClassifier:
    """Expose a simple API for classifying newsletter entries."""

    def __init__(self, llm_client: OpenRouterClient | None = None) -> None:
        self._llm_client = llm_client
        self._cache: dict[str, PrimaryTopic] = {}

    def classify(self, article: ArticleContent) -> ClassifiedArticle:
        topic = self._classify_with_rules(article)
        source = "rules"

        if topic is None and self._llm_client is not None:
            topic = self._classify_with_llm(article)
            source = "llm"

        if topic is None:
            topic = PrimaryTopic.UNKNOWN

        return ClassifiedArticle(content=article, topic=topic, classification_source=source)

    def _classify_with_rules(self, article: ArticleContent) -> PrimaryTopic | None:
        domain = _normalize_domain(str(article.url))
        if _matches_domain(domain, PAPER_DOMAINS) or _text_contains(
            article, {"arxiv", "iclr", "neurips"}
        ):
            return PrimaryTopic.PAPERS

        if _matches_domain(domain, OPEN_SOURCE_DOMAINS) or "github.com" in article.text.lower():
            return PrimaryTopic.OPEN_SOURCE

        if _matches_domain(domain, BLOG_DOMAINS) or domain.startswith("blog."):
            return PrimaryTopic.BLOGS

        if any(keyword in domain for keyword in ("press", "news")):
            return PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS

        if "release" in article.text.lower() or "roadmap" in article.text.lower():
            return PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS

        return None

    def _classify_with_llm(self, article: ArticleContent) -> PrimaryTopic | None:
        cached = self._cache.get(str(article.url))
        if cached is not None:
            return cached

        prompt = _build_prompt(article)
        response = self._llm_client.complete(prompt)
        topic = _parse_topic(response)
        if topic is not None:
            self._cache[str(article.url)] = topic
        return topic


def _matches_domain(domain: str, targets: Iterable[str]) -> bool:
    return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in targets)


def _text_contains(article: ArticleContent, keywords: Iterable[str]) -> bool:
    text = article.text.lower()
    return any(keyword in text for keyword in keywords)


def _build_prompt(article: ArticleContent) -> list[dict[str, str]]:
    snippet = article.text[:1000]
    instructions = (
        "You classify the primary topic for AI/ML news articles. Choose exactly one of the "
        "following options: Paper, Blog, Open Source, Engineering & Product & Business. "
        "Respond with only the option name."
    )
    user_content = (
        f"URL: {article.url}\nTitle: {article.title or 'Unknown'}\nContent snippet:\n{snippet}"
    )
    return [{"role": "system", "content": instructions}, {"role": "user", "content": user_content}]


@lru_cache(maxsize=32)
def _parse_topic(candidate: str) -> PrimaryTopic | None:
    normalized = candidate.strip().lower()
    for prefix in ("topic:", "classification:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
    mapping = {
        "paper": PrimaryTopic.PAPERS,
        "papers": PrimaryTopic.PAPERS,
        "blog": PrimaryTopic.BLOGS,
        "blogs": PrimaryTopic.BLOGS,
        "open source": PrimaryTopic.OPEN_SOURCE,
        "open-source": PrimaryTopic.OPEN_SOURCE,
        "engineering": PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS,
        "product": PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS,
        "business": PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS,
        "engineering & product & business": PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS,
    }
    if normalized in mapping:
        return mapping[normalized]

    for key, value in mapping.items():
        if key in normalized:
            return value
    return None
