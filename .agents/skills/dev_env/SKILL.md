---
name: dev_env
description: Configure and diagnose the Kaizen Harvester local runtime — uv workspace, LLM provider credentials, and GitHub API access.
---

# Kaizen Harvester Dev Environment Skill (`dev_env`)

## 🎯 Purpose

Configure the `uv` workspace, validate provider credentials, and confirm a **real** model call works
before any pipeline code is trusted.

> **Why this skill is strict about verification:** v1 shipped a database with one fabricated record
> because it authenticated against `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, neither of which exists
> here. Every run silently fell back to a mock LLM. Never accept "the tests pass" as evidence that a
> provider works.

---

## 🚀 Environment Setup

Python **3.13**, [`uv`](https://docs.astral.sh/uv/) workspace rooted at the repo root.

```bash
uv sync                  # creates .venv, installs workspace + dev groups
uv run pytest
uv run ruff check .
uv run ruff format .
```

Workspace members live under `projects/*`. Only `projects/p1-map` exists today.

---

## 🔑 Provider Reality

**There is no `OPENAI_API_KEY` and no `ANTHROPIC_API_KEY`.** Do not design around them.

| Provider | Env var | Base URL | Status |
|---|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | **set** |
| Ollama (local) | none needed | `http://localhost:11434/v1` | **running** |
| Gemini | `GOOGLE_API_KEY` | OpenAI-compat shim | **unset** — confirm before relying on it |
| Experiential Labs | `EXPLABS_API_KEY` | — | unset |

Local Ollama models: `qwen2.5-coder:7b`, `llama3.1:8b`, `mistral:7b`, `deepseek-r1:14b`, `gemma4:12b-mlx`.

All four are OpenAI-compatible — **one adapter with a swapped `base_url`, not four clients.**

`GITHUB_TOKEN` is **set** (lifts search from 10 to 30 req/min, Core to 5,000/hr).

---

## 🔍 Health Checks

Run these in order. Stop at the first failure.

```bash
# 1. Credentials present
echo "OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:+set}${OPENROUTER_API_KEY:-MISSING}"
echo "GITHUB_TOKEN:       ${GITHUB_TOKEN:+set}${GITHUB_TOKEN:-MISSING}"

# 2. Ollama reachable, and which models are actually pulled
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; print([m['name'] for m in json.load(sys.stdin)['models']])"

# 3. GitHub token works and shows real remaining quota
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['resources']; print({k: d[k] for k in ('core','search','graphql') if k in d})"

# 4. A REAL model call — the one that matters
uv run python -c "
from openai import OpenAI
c = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
r = c.chat.completions.create(model='qwen2.5-coder:7b',
    messages=[{'role':'user','content':'Reply with exactly: ALIVE'}], max_tokens=10)
print('OLLAMA:', r.choices[0].message.content)
"
```

**A health check has passed only when step 4 printed output from a live model.** Steps 1–3 prove
nothing about whether inference works.

---

## 🚨 Troubleshooting

| Symptom | Cause |
|---|---|
| Model call returns instantly with plausible text | You are talking to a mock. This is the v1 failure — find the fallback and delete it |
| `connection refused` on 11434 | Ollama not running: `ollama serve` |
| Model not in `/api/tags` | Not pulled: `ollama pull qwen2.5-coder:7b` |
| GitHub 403 with quota remaining | Secondary rate limit — you're bursting. Back off, don't retry harder |
| `search` quota drains fast | Expected: 30/min is the real ceiling on discovery breadth |
