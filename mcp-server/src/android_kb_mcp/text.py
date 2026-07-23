from __future__ import annotations

import re
from typing import Iterable


MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
HTML_TAG = re.compile(r"<[^>]+>")
WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
WORD_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")


def markdown_to_text(markdown: str) -> str:
    text = re.sub(r"```[^\n]*\n([\s\S]*?)```", r"\1", markdown)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = MARKDOWN_LINK.sub(r"\1", text)
    text = WIKI_LINK.sub(r"\1", text)
    text = HTML_TAG.sub(" ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def count_words(markdown: str) -> int:
    return len(WORD_TOKEN.findall(markdown_to_text(markdown)))


def related_documents(markdown: str) -> list[str]:
    return sorted({match.strip() for match in WIKI_LINK.findall(markdown) if match.strip()})


def make_embedding_text(title: str, tags: Iterable[str], body: str) -> str:
    parts = [title.strip(), " ".join(tags), markdown_to_text(body)]
    return "\n".join(part for part in parts if part)


def excerpt(markdown: str, limit: int = 1200) -> str:
    plain = markdown_to_text(markdown)
    if len(plain) <= limit:
        return plain
    return plain[:limit].rstrip() + "…"
