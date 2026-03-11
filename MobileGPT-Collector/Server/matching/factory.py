"""Factory for creating matching strategies."""

from .base import MatchingStrategy


STRATEGY_NAMES = ["keyui-mobilegpt", "embedding"]


def create_strategy(name: str, **kwargs) -> MatchingStrategy:
    """Create a matching strategy by name.

    Args:
        name: Strategy name
        **kwargs: Additional arguments passed to the strategy constructor.
            - keyui-mobilegpt: match_threshold (float, default 0.7)
            - embedding: model (str), threshold (float, default 0.95)

    Returns:
        MatchingStrategy instance
    """
    if name == "keyui-mobilegpt":
        from .keyui_v1_strategy import KeyUIV1Strategy
        return KeyUIV1Strategy(**kwargs)
    elif name == "embedding":
        from .embedding_strategy import EmbeddingStrategy
        return EmbeddingStrategy(**kwargs)
    else:
        raise ValueError(
            f"Unknown matching strategy: '{name}'. "
            f"Available: {STRATEGY_NAMES}"
        )
