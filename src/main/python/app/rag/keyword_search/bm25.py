"""Small dependency-free BM25 implementation for local lexical retrieval."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize Vietnamese and Latin text while preserving word boundaries."""
    return [token.lower() for token in _TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class BM25Document:
    """A document and its original retrieval metadata."""

    content: str
    metadata: dict
    index: int


class BM25Index:
    """In-memory BM25 index suitable for reranking a small retrieval result set."""

    def __init__(
        self,
        documents: Iterable[BM25Document],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(document.content) for document in self.documents]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._average_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._document_frequency = Counter(
            token for tokens in self._tokens for token in set(tokens)
        )

    def score(self, query: str, document_index: int) -> float:
        """Return the BM25 relevance score for one indexed document."""
        if not self.documents:
            return 0.0

        query_terms = Counter(tokenize(query))
        document_terms = Counter(self._tokens[document_index])
        document_length = self._lengths[document_index]
        total_documents = len(self.documents)
        score = 0.0

        for term, query_frequency in query_terms.items():
            term_frequency = document_terms.get(term, 0)
            if term_frequency == 0:
                continue
            frequency = self._document_frequency.get(term, 0)
            inverse_document_frequency = math.log(
                1 + (total_documents - frequency + 0.5) / (frequency + 0.5)
            )
            normalization = 1 - self.b + self.b * (
                document_length / self._average_length if self._average_length else 0
            )
            term_score = (
                inverse_document_frequency
                * (term_frequency * (self.k1 + 1))
                / (term_frequency + self.k1 * normalization)
            )
            score += query_frequency * term_score

        return score

    def search(self, query: str, top_k: int | None = None) -> list[tuple[BM25Document, float]]:
        """Return documents ranked by descending BM25 score."""
        ranked = [
            (document, self.score(query, index))
            for index, document in enumerate(self.documents)
        ]
        ranked.sort(key=lambda item: (-item[1], item[0].index))
        return ranked[:top_k] if top_k is not None else ranked
