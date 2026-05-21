import logging
import os
from google import genai

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-004"
_EMBEDDING_DIMS = 768


def embed_text(text: str) -> list[float] | None:
    """Generate a 768-dim embedding via Gemini text-embedding-004.

    Returns None on any failure so callers can fall back to regex search.
    """
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client(
                vertexai=True,
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location="us-central1",
            )
        result = client.models.embed_content(
            model=_EMBEDDING_MODEL,
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.warning("embed_text failed: %s", e)
        return None
