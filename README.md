# Modular Workshops

This repository contains hands-on tutorials for learning LangChain, LangGraph, and Deep Agents.

This is a condensed version of LangChain Academy, intended to be run in a session with a LangChain engineer. If you're interested in going into more depth, or working through tutorials on your own, check out [LangChain Academy](https://academy.langchain.com/courses/intro-to-langgraph)! LangChain Academy has helpful pre-recorded videos from our LangChain engineers.

## Workshop Sessions

**Workshop 1** covers the internal HR assistant end to end:

- `modules/01_deep_agents.ipynb` — **Deep Agents**: build the retrieve-then-act HR agent (tools, subagents, memory, middleware, HITL, AGENTS.md + skills).
- `modules/03_langsmith.ipynb` — **LangSmith**: prompt engineering, tracing, offline/online evaluations, and the CI promotion gate for that agent.

The remaining modules — `modules/02_deploy_and_govern.ipynb` (Deploy + Govern) and `modules/04_engine.ipynb` (Engine) — will be covered in a later session.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment variables
cp .env.example .env
# Edit .env and fill in your keys
```

| Key | Required for | Get one |
|-----|--------------|---------|
| `OPENAI_API_KEY` | All modules (default model) | <https://platform.openai.com> |
| `LANGSMITH_API_KEY` | Modules 2 & 3 (recommended for all) | <https://smith.langchain.com> |
| `LANGSMITH_API_KEY_GATEWAY` / `WORKSPACE_ID` | Module 2 §1 (LangSmith Gateway policies) | same key as `LANGSMITH_API_KEY`; workspace ID from LangSmith Settings → Workspace |
| `TAVILY_API_KEY` | Modules 2 & 4 (web search tool) | <https://tavily.com> |

> **Module 1 (Deep Agents)** uses a fully-synthetic HR database — no external data or web search. It's generated locally by `utils/hr_seed.py` (the notebook's first cell seeds `hr.db`). All employee data is fake.

```bash
# 3. Start Jupyter
uv run jupyter notebook
```

Open whichever module(s) your recipe calls for.

## Switching Models

All modules import `model` from `utils/models.py`. Change one line there to swap providers — no notebook edits required.

```python
# utils/models.py

# OpenAI (default)
model = init_chat_model("openai:gpt-5.6-terra", use_responses_api=True)

# Anthropic
# model = init_chat_model("anthropic:claude-sonnet-4-5")

# Azure OpenAI
# from langchain_openai import AzureChatOpenAI
# model = AzureChatOpenAI(azure_deployment="gpt-5.6-terra", streaming=True)

# AWS Bedrock
# from langchain_aws import ChatBedrockConverse
# model = ChatBedrockConverse(provider="anthropic", model_id="...")
```

`utils/models.py` also ships a commented-out **LangSmith Gateway** block. Module 2 (Deploy + Govern) §1.4 walks through flipping the default to it so every model call (notebooks *and* the deployed agent) is routed through the gateway and subject to workspace policies.

## Deploy + Govern (Module 2)

Module 2 (`modules/02_deploy_and_govern.ipynb`) first creates a workspace-level **LangSmith Gateway** policy (PII / secrets redaction), routes the model through the gateway, then deploys the agent at `agents/deep_agent/` to LangSmith via the `langgraph` CLI (installed by `uv sync`). The deploy config is `langgraph.json` at the workshop root.

Because `agents/deep_agent/agent.py` imports `model` from `utils.models`, whichever block is active in `utils/models.py` at deploy time is what ships — flip on the gateway block and the deployed agent inherits it with no extra flags.

Your `LANGSMITH_API_KEY` must have deployment permissions (use a `lsv2_sk_...` service key). The gateway block reads `LANGSMITH_API_KEY_GATEWAY` (the same key under a non-reserved name, since `langgraph deploy` strips `LANGSMITH_API_KEY` during upload).

## Evals + CI Promotion Gate (Module 3)

Module 3 (`modules/03_langsmith.ipynb`) builds an offline eval suite for the HR agent in the `evals/` package:

- **Dataset** (`evals/hr_dataset.py`) — ~15 examples covering the representative questions and every deliberate edge case (below-band-min, null salary, duplicate name, manager with no reports), each with reference answers.
- **Four evaluators** (`evals/hr_evaluators.py`) — figure correctness, tool selection/trajectory, `open_hr_case`-iff-it-should, and an LLM-as-judge on helpfulness.
- **Tag registry** — evaluators are registered with tags so a pipeline discovers them **by tag** (`get_evaluators_by_tag("ci")`) instead of a hardcoded list.
- **CI gate** — `evals/run_evals.py` discovers the `ci`-tagged evaluators, runs the experiment, and exits non-zero when a gated score drops below a configurable threshold. `.github/workflows/evals.yml` runs it on every PR, so it acts as a promotion gate.

```bash
# Run the gate locally exactly as CI does:
uv run python -m evals.run_evals --tag ci --threshold 0.8 \
    --gate-keys figure_correctness,tool_selection,case_opened_correctly
```

CI needs `OPENAI_API_KEY` and `LANGSMITH_API_KEY` as repo secrets (Settings → Secrets and variables → Actions).

## Engine (Module 4)

Module 4 (`modules/04_engine.ipynb`) introduces **LangSmith Engine** — it reads your deployed agent's production traces, clusters recurring failures into issues, diagnoses the root cause against your connected source code, and proposes fixes as GitHub PRs. It runs on the Module 2 deployment, driven through an *assistant* (a saved graph configuration) that swaps in a deliberately broken search tool so Engine has a clear, reproducible issue to find.

Engine's first analysis takes ~20 minutes, so it's best primed before a session. Needs the Module 2 deployment and a `LANGSMITH_API_KEY`.

## Project Structure

```
modular-workshops/
├── README.md                       (this file — recipes + setup)
├── pyproject.toml                  (shared dependencies)
├── .env.example
├── langgraph.json                  (registers agents/deep_agent for langgraph dev)
├── .github/workflows/evals.yml     (HR agent eval promotion gate — runs on PR)
├── utils/
│   └── hr_seed.py                  (seeds the synthetic HR database, hr.db)
├── agents/
│   ├── hr_agent.py                 (shared HR agent factory — Module 1 inlines the pattern, Module 3 imports it for traces/eval)
│   └── deep_agent/                 (deployable + governed agent for Module 2)
│       ├── agent.py
│       ├── AGENTS.md
│       └── skills/
│           ├── linkedin-post/SKILL.md
│           └── twitter-post/SKILL.md
├── evals/                          (HR agent eval suite — used by Module 3 §3 and CI)
│   ├── hr_dataset.py               (~15 examples: representative questions + edge cases)
│   ├── hr_evaluators.py            (4 tagged evaluators + tag registry)
│   ├── target.py                   (runs the agent, returns response + tool trajectory)
│   └── run_evals.py                (CI entrypoint: discover-by-tag + threshold gate)
├── images/                         (diagrams used by the notebooks)
└── modules/
    ├── 01_deep_agents.ipynb        (Module 1 — Deep Agents)          [Workshop 1]
    ├── 02_deploy_and_govern.ipynb  (Module 2 — Deploy + Govern)      [later]
    ├── 03_langsmith.ipynb          (Module 3 — LangSmith + Evals)    [Workshop 1]
    └── 04_engine.ipynb             (Module 4 — Engine)               [later]
```

## Common Issues

**`langgraph deploy` fails with 403 / permission denied**
Your API key is a personal token. Generate a service key (`lsv2_sk_...`) in LangSmith settings.

**Notebook can't find `utils` / `agents`**
Each module's setup cell prepends `project_root` (the workshop root) to `sys.path`. If you moved a notebook, update the `Path().resolve().parent` line to point at the workshop root.

## For LangChain Internal Users
Please refer to this linked [Notion document](https://app.notion.com/p/Modular-Workshops-37d808527b1780318063fd210446aa03?source=copy_link) for instructions on setup and usage.
