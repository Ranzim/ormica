# Semantic memory — relevance recall across agents

The default mycelium is **key-value**: an agent must know the exact key to
recall something. Semantic memory adds **relevance recall** — an agent asks a
fuzzy question and gets back the most related knowledge *any* agent wrote,
without knowing the keys. This is the seam that turns "shared storage" into a
"shared brain."

It's built as a protocol extension, so nothing else changes: a searchable
backend is still a `Backend`, so all existing key-value code keeps working.

## Turn it on

Build the mycelium on `InMemorySemanticBackend`:

```python
from ormica.mycelium import Mycelium, InMemorySemanticBackend

memory = Mycelium(InMemorySemanticBackend())

memory.write("finding:1", "the flaky test is a race in the cache layer", author="a1")
memory.write("finding:2", "revenue grew on enterprise upsells", author="a2")

for m in memory.search("why is the test flaky", k=3):
    print(f"{m.score:.3f}  {m.entry.value}")
# 0.41  the flaky test is a race in the cache layer
```

Agents get a shortcut:

```python
hits = agent.recall_relevant("cache race condition", k=5)  # -> list[Match]
best = hits[0].entry.value if hits else None
```

`search`/`recall_relevant` return `Match(entry, score)` ordered most-relevant
first. Expired (TTL) entries are filtered out.

## The default embedder is lexical, not semantic

`InMemorySemanticBackend` uses `HashingEmbedder` by default — a deterministic,
zero-dependency **bag-of-words** embedder. It scores by *shared words*, so:

- ✅ "how do CPUs keep caches consistent" → finds "cache coherence protocol MESI"
- ❌ "web app vulnerability in auth" → will **miss** "SQL injection in login form"
  (no shared words)

That's the honest limit of the offline default — it exists so the seam is
testable without a model or network. For **true** semantics, use the built-in
`SentenceTransformerEmbedder`, behind the `memory` extra:

```bash
pip install ormica[memory]
```

```python
from ormica.mycelium import Mycelium, InMemorySemanticBackend, SentenceTransformerEmbedder

memory = Mycelium(InMemorySemanticBackend(embedder=SentenceTransformerEmbedder()))
# now "web app auth vulnerability" DOES find "SQL injection in a login form"
```

The default model is `all-MiniLM-L6-v2` (384-dim, small and fast); pass
`SentenceTransformerEmbedder("your-model")` for another. Any object with an
`embed(text) -> list[float]` method (and a `dim` attribute) satisfies the
`Embedder` protocol, so a bespoke or API-backed embedder drops in the same way.

## Going to a real vector store

`InMemorySemanticBackend` holds vectors in RAM — fine for a prototype, not for
scale or persistence. For production, implement the same `SearchableBackend`
protocol over a vector database (ChromaDB is the intended v0.4 backend):

```python
from ormica.mycelium import SearchableBackend, Match

class ChromaBackend:  # satisfies Backend + SearchableBackend
    def get(self, key): ...
    def set(self, entry): ...        # embed + upsert into the collection
    def delete(self, key): ...
    def items(self): ...
    def __contains__(self, key): ...
    def __len__(self): ...
    def search(self, query, k=5) -> list[Match]: ...   # collection.query(...)
```

`Mycelium` calls only those methods, so nothing above the backend changes.

## Related

- [Persistence](./persistence.md) — the `Backend` protocol these extend.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — auditing what agents recalled.
