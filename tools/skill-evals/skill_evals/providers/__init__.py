"""Model providers: the ``ModelProvider`` port and its adapters.

``claude_cli`` drives headless Claude Code (the honest test of the Skills mechanism);
``openrouter`` drives any OpenAI-compatible tool-using model with mimicked skill activation.
"""

from skill_evals.providers.base import (
    MalformedOutputError,
    ModelMismatchError,
    ModelProvider,
    ProviderError,
    ProviderTimeoutError,
    RateLimitedError,
    ToolCall,
    Trajectory,
    TransportError,
    TurnRecord,
    Usage,
)

__all__ = [
    "MalformedOutputError",
    "ModelMismatchError",
    "ModelProvider",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitedError",
    "ToolCall",
    "Trajectory",
    "TransportError",
    "TurnRecord",
    "Usage",
]
