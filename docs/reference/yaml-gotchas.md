# YAML gotchas — things that bite once

A short reference for the corners of `ormica.yaml` and colony YAML where the
syntax does something non-obvious. Each one came out of real user feedback.

## `sense_prefixes` — quoting the bare-colon form

YAML's scanner treats a trailing colon at value position as a mapping key.
The list form is auto-absorbed by the loader; the single-value form needs
quotes:

```yaml
# ✅ List form works as-is — loader normalises [{topic: None}] back to "topic:"
sense_prefixes: [topic:, activity:]

# ✅ Single value works with quotes
sense_prefixes: "topic:"

# ❌ This is a YAML SCANNER error, not an ormica error — quote it
sense_prefixes: topic:
```

## `min_task_description` vs `min_runtime_task_description`

These look alike but inspect different fields. Easy to swap by mistake;
pick the one that matches what you actually want to reject.

- **`min_task_description`** reads the *spawn-time* `Node.task` string
  (set by a colony template's `task:` field). Use it to require that every
  agent node carry a meaningful role description.
- **`min_runtime_task_description`** reads the per-invocation description
  passed to `org.task(description=...)`. Use it to reject one-word briefs
  at submission time ("update the doc" → too vague to act on).

## `banned_words` — three matching behaviors

The factory family has three distinct semantics. Pick by use case:

```yaml
# Word-boundary (default) — "secret" matches "the secret formula"
# but NOT "secretary". Natural-language banlists.
- banned_words: [guaranteed, miracle, cure]

# Substring (opt-in) — for fragments embedded in larger strings
# (credential placeholders like INTERNAL_API_KEY, SKU prefixes).
- banned_words:
    words: [api_key, secret_token]
    match_mode: substring

# Stem + suffix expansion — "guarantee" catches "guaranteed",
# "guaranteeing", "guarantees" (one entry covers all inflections).
# Note: doesn't handle silent-e drop — "cure" misses "curing".
- banned_word_stems: [guarantee, miracle]
```

## `severity: soft` on any rule

Any rule spec accepts a sibling `severity:` key. Soft rules don't fail the
task — they fire a `rule.soft_violation` event and the action proceeds.
The violation lands in `Trace.warnings` so `ormica trace <id>` shows
"shipped with warnings."

```yaml
constitution:
  rules:
    - {max_response_tokens: 800, severity: soft}   # warn + record, no fail
    - max_response_tokens: 2000                    # hard cap (default)
```

## `ormica trace` truncates at 80 chars by default

The text format clips long fields (system prompts with injected stigma
signals, long banned-words descriptions). Use `--full` to see everything,
or `--width N` to pick a terminal-friendly width. `--format json` always
preserves full content.

```bash
ormica trace <task_id>                # text, truncated at 80
ormica trace <task_id> --full         # text, no truncation
ormica trace <task_id> --width 120    # text, wider window
ormica trace <task_id> --format json  # full content, machine-readable
```
