# Running Ormica fully local with Ollama

Run a whole colony — tree, rules, tools, traces — **with no cloud LLM API and no key**. [Ollama](https://ollama.com/) runs an open-weights model on your own machine; Ormica's `UniversalBrain` talks to it over the OpenAI-compatible API Ollama exposes.

This is the recipe for offline dev, privacy-sensitive workloads, and just keeping costs at zero while you prototype.

## 1. Install and start Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

Pull a model:

```bash
ollama pull llama3.2          # ~2GB, very fast
# or:
ollama pull qwen2.5:14b       # ~9GB, much smarter for tools
ollama pull mistral-nemo      # ~7GB, balanced
```

Run the daemon (it auto-starts on most installs):

```bash
ollama serve                  # listens on http://localhost:11434
```

Quick sanity check that the API speaks OpenAI:

```bash
curl http://localhost:11434/v1/models | python -m json.tool
```

## 2. Point Ormica at it

In `ormica.yaml`:

```yaml
name: My Local Colony
industry: business

brain:
  type: ollama
  model: llama3.2          # the model name you pulled above
  # No 'replies:' — the real brain will think now.
```

That's it. `ormica run` now drives a local model. The `--brain ollama` shortcut on the CLI is equivalent.

From Python:

```python
from ormica import Ormica
from ormica.brain import ollama_brain

org = Ormica("My Local Colony")
org.plant("business")
org.task("Find 3 SMB leads", dept="sales")
org.run(brain=ollama_brain(model="llama3.2"))
```

## 3. What works the same as the cloud path

- **Constitution rules** — pre / post / spawn enforcement is unchanged. `banned_words`, `max_tokens`, `block_role`, all of it.
- **Persistence** — `memory_db: ./local.db` works exactly the same; traces persist, `ormica trace <id>` reads them.
- **Tools** — `@tool` functions and `act_with_tools` work; small models are weaker at tool use, so see notes below.
- **Dashboard** — `ormica dashboard --config ormica.yaml` shows the same live event stream.
- **Async** — `ormica run --async --concurrency 5` fans out to multiple Ollama requests in parallel.

## 4. What's different

### Smaller models are weaker at tool use

`llama3.2:3b` will *sometimes* call a tool correctly. `qwen2.5:14b`, `mistral-nemo`, and `llama3.1:70b` are dramatically better. If your agent has tools and they're not getting called, the model is usually the problem — not Ormica.

### Smaller models hallucinate JSON

The `require_json()` Constitution rule (a v0.2 standard library rule) is more useful here than against Claude/GPT. Wrap any tool whose output must be machine-readable:

```yaml
constitution:
  rules:
    - require_json
```

### Tokens are still tracked, but free

`response.tokens_used` is reported by Ollama; the Thought Trail still captures it. `max_tokens` rules still fire. The cost is just zero — useful for capacity planning even though there's no bill.

### Latency profile

A typical Ollama think call on a laptop is **2–6 seconds** for a 7B model, much more for a 70B. The live ticker on `ormica dashboard` makes this very visible — and if anything, more interesting to watch than a cloud model that returns in 400ms.

## 5. Recommended starting model by task shape

| Task shape | Try |
|---|---|
| Triage / classification, no tools | `llama3.2:3b` |
| Tool use, moderate reasoning | `qwen2.5:14b` or `mistral-nemo` |
| Long-form writing | `qwen2.5:14b-instruct` |
| Best-quality, you have the RAM | `qwen2.5:32b-instruct` or `llama3.1:70b` |

You can mix models per node via a `Router` — see [Async and routing](../async-and-routing.md).

## 6. Running the SaaS helpdesk example fully local

```bash
# In examples/saas_helpdesk/ormica.yaml, change:
brain:
  type: ollama
  model: qwen2.5:14b
# (and delete the `replies:` block)

cd examples/saas_helpdesk
python run.py
```

Every ticket now goes through a model running on your laptop. The persisted traces still work, the live dashboard still works, the per-department rules still bite.

## 7. When you do want to swap back to cloud

The brain seam is one config line. Change `type: ollama` to `type: claude` (or `openai`, `gemini`, `groq`, …) and set the appropriate env var. The colony, the rules, the tools, the traces — none of it changes.

## Related

- [LLM providers](../llm-providers.md) — full matrix of every supported brain.
- [SaaS helpdesk example](../../../examples/saas_helpdesk/README.md) — drop-in colony to point at Ollama.
- [Writing tools](../writing-tools.md) — and why model choice matters for tool use.
- [Slack integration](./slack.md) · [Email integration](./email.md) — pair local Ollama with notification channels for a fully self-hosted stack.
