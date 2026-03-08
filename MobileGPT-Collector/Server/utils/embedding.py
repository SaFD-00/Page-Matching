"""OpenAI embedding utilities."""

import ast
from typing import Optional

import numpy as np
from openai import OpenAI

from ..config import OPENAI_API_KEY


def get_openai_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate OpenAI embedding vector for text."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def safe_literal_eval(val) -> Optional[list]:
    """Safely convert string representation of list back to list."""
    if isinstance(val, (list, np.ndarray)):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return None
    return None
