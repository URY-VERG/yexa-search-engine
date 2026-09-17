"""Pluggable semantic-retrieval boundary; no synthetic embeddings are produced."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str

    def available(self) -> bool: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DisabledEmbeddingProvider:
    name = "disabled"

    def available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("No local embedding model is configured for YEXA.")


def get_embedding_provider() -> EmbeddingProvider:
    """Future configuration point for a real local embedding model."""
    return DisabledEmbeddingProvider()
