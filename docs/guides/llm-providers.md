# LLM providers — every recipe in one place

Ormica works with **15+ LLM providers** through 4 adapter classes plus 5 convenience helpers. This page is the copy-paste catalogue.

## TL;DR — the recipe matrix

| Provider | Adapter | One-liner |
|---|---|---|
| Anthropic Claude | `ClaudeBrain` | `ClaudeBrain(model="claude-opus-4-7")` |
| Google Gemini | `GeminiBrain` | `GeminiBrain(model="gemini-2.0-flash")` |
| OpenAI | `UniversalBrain` | `UniversalBrain(model="gpt-4o")` |
| **Ollama** (local LLMs) | `ollama_brain()` | `ollama_brain(model="llama3.2")` |
| OpenRouter (300+ models) | `openrouter_brain()` | `openrouter_brain(model="anthropic/claude-opus-4-7")` |
| Groq (fast Llama/Mixtral) | `groq_brain()` | `groq_brain(model="llama-3.3-70b-versatile")` |
| Together AI | `together_brain()` | `together_brain(model="meta-llama/Llama-3.3-70B-Instruct-Turbo")` |
| DeepSeek | `deepseek_brain()` | `deepseek_brain(model="deepseek-chat")` |
| Mistral La Plateforme | `UniversalBrain(base_url=...)` | see [below](#mistral-la-plateforme) |
| Anyscale Endpoints | `UniversalBrain(base_url=...)` | see [below](#anyscale-endpoints) |
| Fireworks AI | `UniversalBrain(base_url=...)` | see [below](#fireworks-ai) |
| vLLM self-hosted | `UniversalBrain(base_url=...)` | see [below](#vllm-self-hosted) |
| LM Studio (local desktop) | `UniversalBrain(base_url=...)` | see [below](#lm-studio) |

## Native providers

### Anthropic Claude

```bash
pip install ormica[claude]
export ANTHROPIC_API_KEY=sk-ant-...
```

```python
from ormica.brain import ClaudeBrain

brain = ClaudeBrain(model="claude-opus-4-7")          # or claude-sonnet-4-6, claude-haiku-4-5
```

Why native: full content blocks, native tool_use parsing, adaptive thinking.

### Google Gemini

```bash
pip install ormica[gemini]
export GOOGLE_API_KEY=...                              # or GEMINI_API_KEY
```

```python
from ormica.brain import GeminiBrain

brain = GeminiBrain(model="gemini-2.0-flash")         # or gemini-1.5-pro, gemini-1.5-flash
```

Why native: function-declaration tool format, multi-part responses (text + function_call together).

## OpenAI-compatible providers (via `UniversalBrain`)

All of these route through a single adapter — `UniversalBrain` — by varying `base_url=` and `api_key=`. Convenience helpers exist for the five most popular; the rest use `UniversalBrain` directly.

```bash
pip install ormica[universal]                          # or ormica[openai] — same thing
```

### Ollama (local LLMs)

Free. Private. No API key. Runs on your laptop.

```bash
# 1. Install Ollama from https://ollama.ai
# 2. Pull a model
ollama pull llama3.2
```

```python
from ormica.brain import ollama_brain

brain = ollama_brain(model="llama3.2")
# Or any model Ollama supports: qwen2.5, mistral, phi3.5, deepseek-r1, ...
```

Custom host (remote Ollama box):

```python
brain = ollama_brain(model="llama3.2", host="http://192.168.1.10:11434")
```

### OpenRouter

One API key, 300+ models from Anthropic / OpenAI / Google / Meta / Mistral / etc.

```bash
export OPENROUTER_API_KEY=sk-or-...                    # https://openrouter.ai/keys
```

```python
import os
from ormica.brain import openrouter_brain

brain = openrouter_brain(
    model="anthropic/claude-opus-4-7",                 # or any model on openrouter.ai/models
    api_key=os.environ["OPENROUTER_API_KEY"],
)
```

### Groq

Very fast inference for open-source models (Llama, Mixtral, Gemma).

```bash
export GROQ_API_KEY=gsk-...                            # https://console.groq.com/keys
```

```python
import os
from ormica.brain import groq_brain

brain = groq_brain(
    model="llama-3.3-70b-versatile",                   # default
    api_key=os.environ["GROQ_API_KEY"],
)
```

### Together AI

Hosted open-source models. Generous free tier for some models.

```bash
export TOGETHER_API_KEY=...                            # https://api.together.xyz/settings/api-keys
```

```python
import os
from ormica.brain import together_brain

brain = together_brain(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo",   # default
    api_key=os.environ["TOGETHER_API_KEY"],
)
```

### DeepSeek

Strong reasoning at low cost.

```bash
export DEEPSEEK_API_KEY=sk-...                         # https://platform.deepseek.com/api_keys
```

```python
import os
from ormica.brain import deepseek_brain

brain = deepseek_brain(
    model="deepseek-chat",                             # or deepseek-reasoner
    api_key=os.environ["DEEPSEEK_API_KEY"],
)
```

### Mistral La Plateforme

```python
from ormica.brain import UniversalBrain
import os

brain = UniversalBrain(
    base_url="https://api.mistral.ai/v1",
    model="mistral-large-latest",
    api_key=os.environ["MISTRAL_API_KEY"],
)
```

### Anyscale Endpoints

```python
brain = UniversalBrain(
    base_url="https://api.endpoints.anyscale.com/v1",
    model="meta-llama/Llama-3.3-70B-Instruct",
    api_key=os.environ["ANYSCALE_API_KEY"],
)
```

### Fireworks AI

```python
brain = UniversalBrain(
    base_url="https://api.fireworks.ai/inference/v1",
    model="accounts/fireworks/models/llama-v3p3-70b-instruct",
    api_key=os.environ["FIREWORKS_API_KEY"],
)
```

### vLLM (self-hosted)

When you're running vLLM yourself with `vllm serve <model> --port 8000`:

```python
brain = UniversalBrain(
    base_url="http://your-server:8000/v1",
    model="meta-llama/Llama-3.3-70B-Instruct",
    api_key="vllm",                                    # vLLM doesn't enforce auth by default
)
```

### LM Studio

When you've started LM Studio's local server (default port 1234):

```python
brain = UniversalBrain(
    base_url="http://localhost:1234/v1",
    model="loaded-model-name",                         # whatever's loaded in LM Studio
    api_key="lm-studio",
)
```

## Mixing providers per node — `Router`

You don't have to pick one. A `Router` selects a brain per node:

```python
from ormica.brain import Router, ClaudeBrain, groq_brain, ollama_brain

router = Router(
    default=ollama_brain(model="llama3.2"),                   # cheap default for scouts
    by_role={
        "executive": ClaudeBrain(model="claude-opus-4-7"),    # smartest model for leadership
        "scout":     groq_brain(),                            # fast model for high-throughput
    },
)

org.run(brain=router)
```

The router doesn't care whether brains are native or universal — it just returns whatever you stored.

## From the CLI

The CLI knows about the popular providers:

```bash
ormica run --brain claude       # native Claude
ormica run --brain gemini       # native Gemini
ormica run --brain openai       # GPT
ormica run --brain ollama       # local Ollama
ormica run --brain openrouter   # OpenRouter
ormica run --brain groq         # Groq
ormica run --brain together     # Together AI
ormica run --brain deepseek     # DeepSeek
```

For anything not on this list, use Python — pass a configured `UniversalBrain` to `org.run(...)` directly.

## Related

- [Brain architecture](../architecture/03-brain.md) — the `Brain` / `AsyncBrain` protocol design.
- [Async + Router](./async-and-routing.md) — multi-provider routing in detail.
- [Writing tools](./writing-tools.md) — `@tool` works the same across every provider.
