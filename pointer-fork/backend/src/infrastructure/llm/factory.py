"""Chat-LLM and embeddings factories.

Returns LangChain primitives (``BaseChatModel`` / ``Embeddings``) so every
consumer stays agnostic to the provider. Both returned chat clients support
``with_structured_output`` and ``bind_tools``.

Supported providers:
 - ``openai`` → ``ChatOpenAI`` / ``OpenAIEmbeddings``
 - ``bedrock`` → ``ChatBedrockConverse`` (Claude, Nova, Llama) / ``BedrockEmbeddings`` (Titan, Cohere)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.infrastructure.config import Settings, settings as _default_settings

if TYPE_CHECKING:  # pragma: no cover
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


# ─── Chat ─────────────────────────────────────────────────────────────────────

def get_chat_llm(settings: Settings | None = None) -> "BaseChatModel":
    """Instantiate the chat LLM selected by ``settings.llm_provider``."""
    s = settings or _default_settings
    provider = (s.llm_provider or "openai").lower()

    if provider == "bedrock":
        return _build_bedrock_chat(s)
    if provider == "openai":
        return _build_openai_chat(s)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r} (expected 'openai' or 'bedrock')")


def _build_openai_chat(s: Settings) -> "BaseChatModel":
    from langchain_openai import ChatOpenAI

    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    return ChatOpenAI(
        model=s.model,
        temperature=s.model_temperature,
        api_key=s.openai_api_key,
    )


def _build_bedrock_chat(s: Settings) -> "BaseChatModel":
    from langchain_aws import ChatBedrockConverse

    kwargs: dict = {
        "model": s.model,
        "temperature": s.model_temperature,
        "region_name": s.aws_region,
    }
    if s.aws_access_key_id and s.aws_secret_access_key:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    return ChatBedrockConverse(**kwargs)


# ─── Embeddings ───────────────────────────────────────────────────────────────

def get_embeddings(settings: Settings | None = None) -> "Embeddings":
    """Instantiate the embedding model selected by ``settings.embeddings_provider``.

    **Important**: the same model must back both the seeder and the runtime
    categorizer — switching providers invalidates the vector dimensions stored
    in pgvector. When swapping providers, also rotate ``COLLECTION_NAME`` so
    the seeder writes to a fresh collection.
    """
    s = settings or _default_settings
    provider = (s.embeddings_provider or "openai").lower()

    if provider == "bedrock":
        return _build_bedrock_embeddings(s)
    if provider == "openai":
        return _build_openai_embeddings(s)
    raise ValueError(
        f"Unsupported EMBEDDINGS_PROVIDER: {provider!r} (expected 'openai' or 'bedrock')"
    )


def _build_openai_embeddings(s: Settings) -> "Embeddings":
    from langchain_openai import OpenAIEmbeddings

    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when EMBEDDINGS_PROVIDER=openai")

    return OpenAIEmbeddings(model=s.embeddings_model, api_key=s.openai_api_key)


def _build_bedrock_embeddings(s: Settings) -> "Embeddings":
    from langchain_aws import BedrockEmbeddings

    kwargs: dict = {
        "model_id": s.embeddings_model,
        "region_name": s.aws_region,
    }
    if s.aws_access_key_id and s.aws_secret_access_key:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    return BedrockEmbeddings(**kwargs)
