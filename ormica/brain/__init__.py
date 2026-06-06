"""
brain — the pluggable thinking engine.

Every agent thinks through a Brain. Swap between Claude, OpenAI, Gemini,
or local models without changing agent logic. Includes per-node routing,
token-budget control, and the tool-use abstraction.

The separation from ``cortex`` (which is the colony's constitutional /
governance layer) is deliberate: the brain *generates* responses, the
cortex *constrains* what's permissible.

Biological metaphor: the cerebrum — the bulk of neural processing.
"""

from .mock import AsyncMockBrain, MockBrain
from .protocol import AsyncBrain, Brain, Prompt, to_messages
from .router import Router
from .tool import Tool, ToolCall, ToolResult, tool
from .types import BudgetExhausted, Message, Response, TokenBudget

__all__ = [
    "AsyncBrain",
    "AsyncMockBrain",
    "BudgetExhausted",
    "Brain",
    "Message",
    "MockBrain",
    "Prompt",
    "Response",
    "Router",
    "Tool",
    "ToolCall",
    "ToolResult",
    "TokenBudget",
    "tool",
    "to_messages",
]


def __getattr__(name: str):
    # Lazy-load optional provider adapters so missing extras don't break import.
    if name == "ClaudeBrain":
        from .claude import ClaudeBrain
        return ClaudeBrain
    if name == "AsyncClaudeBrain":
        from .claude import AsyncClaudeBrain
        return AsyncClaudeBrain
    if name == "GPTBrain":
        from .gpt import GPTBrain
        return GPTBrain
    if name == "AsyncGPTBrain":
        from .gpt import AsyncGPTBrain
        return AsyncGPTBrain
    if name == "UniversalBrain":
        from .universal import UniversalBrain
        return UniversalBrain
    if name == "AsyncUniversalBrain":
        from .universal import AsyncUniversalBrain
        return AsyncUniversalBrain
    if name == "GeminiBrain":
        from .gemini import GeminiBrain
        return GeminiBrain
    if name == "AsyncGeminiBrain":
        from .gemini import AsyncGeminiBrain
        return AsyncGeminiBrain
    # Provider shortcut constructors — wrap UniversalBrain with the right base_url.
    if name in {
        "ollama_brain", "async_ollama_brain",
        "openrouter_brain", "async_openrouter_brain",
        "groq_brain", "async_groq_brain",
        "together_brain", "async_together_brain",
        "deepseek_brain", "async_deepseek_brain",
    }:
        from . import providers
        return getattr(providers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
