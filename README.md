# Modular Workshops

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/langchain-ai/modular-workshops)

This repository contains hands-on tutorials for learning LangChain, LangGraph, and Deep Agents.

This is a condensed version of LangChain Academy, intended to be run in a session with a LangChain engineer. If you're interested in going into more depth, or working through tutorials on your own, check out [LangChain Academy](https://academy.langchain.com/courses/intro-to-langgraph)! LangChain Academy has helpful pre-recorded videos from our LangChain engineers.

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
| `OPENAI_API_KEY` | Modules 1-4 (default model) | <https://platform.openai.com> |
| `LANGSMITH_API_KEY` | Modules 3 & 4 (recommended for all) | <https://smith.langchain.com> |
| `LANGSMITH_API_KEY_GATEWAY` / `WORKSPACE_ID` | Module 3 §1 (LangSmith Gateway policies) | same key as `LANGSMITH_API_KEY`; workspace ID from LangSmith Settings → Workspace |
| `TAVILY_API_KEY` | Modules 1 & 3 (web search tool) | <https://tavily.com> |

```bash
# 3. Start Jupyter
uv run jupyter notebook
```

Open whichever module(s) your recipe calls for.

## Running in Codespaces

For live workshops, GitHub Codespaces provides the locked project environment in a browser without requiring attendees to install Python, uv, or the repository locally. Use the **Open in GitHub Codespaces** badge at the top of this README to launch it.

A GitHub account with access to Codespaces is required. Availability, usage quotas, and organization policies vary, so keep the local setup above as a fallback for attendees whose accounts cannot create a Codespace.

On first launch, the devcontainer installs uv, runs `uv sync --frozen`, creates `.venv`, and generates an ignored `.env` from `.env.example`. VS Code is configured to use the `.venv` interpreter. If a notebook still prompts for a kernel, select `.venv/bin/python`.

### Configure keys

Use the key table under [Setup](#setup) to determine which keys your selected modules require. Never commit real keys to the repository.

- **Codespaces secrets:** Recommended for facilitators and repeat attendees. In GitHub, open **Settings → Codespaces → Secrets**, add the required secrets, scope them to this repository, and then launch the Codespace. The secrets are injected as environment variables and copied into the generated `.env` where needed.
- **Generated `.env`:** Convenient for a one-off session. Launch the Codespace, add the required values to the labeled entries in `.env`, and save the file. Restart an active notebook kernel after adding or changing keys.

Notebooks can read injected Codespaces secrets directly from the environment. The generated `.env` is especially important for Module 3 because the `langgraph` CLI loads it. The setup script overlays recognized Codespaces secrets onto `.env.example`, leaving every expected variable labeled even when its value is blank.

## Maintaining Codespaces

Most workshop changes require no Codespaces-specific work. Keep these files synchronized when the environment changes:

| If you change | Also update | Why |
|---|---|---|
| A dependency | `uv.lock` | The devcontainer runs `uv sync --frozen`, so a stale lockfile causes setup to fail instead of silently resolving different versions. |
| An API key or environment variable name | `.env.example`, the `keys` list in `.devcontainer/setup.sh`, and the key table above | This keeps the generated `.env`, injected Codespaces secrets, and attendee instructions aligned. |
| The supported Python version in `pyproject.toml` | The Python image tag in `.devcontainer/devcontainer.json` | The container Python version should satisfy the project requirement. |
| A required VS Code extension or setting | `customizations.vscode` in `.devcontainer/devcontainer.json` | Every attendee receives the same editor setup. |

If Codespaces prebuilds are added later, keep `.env` generation in `postCreateCommand` so secrets remain per-user and are never baked into a shared prebuild.

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

`utils/models.py` also ships a commented-out **LangSmith Gateway** block. Module 3 §1.4 walks through flipping the default to it so every model call (notebooks *and* the deployed agent) is routed through the gateway and subject to workspace policies.

## Deploy + Govern (Module 3)

Module 3 first creates a workspace-level **LangSmith Gateway** policy (PII / secrets redaction), routes the model through the gateway, then deploys the agent at `agents/deep_agent/` to LangSmith via the `langgraph` CLI (installed by `uv sync`). The deploy config is `langgraph.json` at the workshop root.

Because `agents/deep_agent/agent.py` imports `model` from `utils.models`, whichever block is active in `utils/models.py` at deploy time is what ships — flip on the gateway block and the deployed agent inherits it with no extra flags.

Your `LANGSMITH_API_KEY` must have deployment permissions (use a `lsv2_sk_...` service key). The gateway block reads `LANGSMITH_API_KEY_GATEWAY` (the same key under a non-reserved name, since `langgraph deploy` strips `LANGSMITH_API_KEY` during upload).

## Engine (Module 5)

Module 5 introduces **LangSmith Engine** — it reads your deployed agent's production traces, clusters recurring failures into issues, diagnoses the root cause against your connected source code, and proposes fixes as GitHub PRs. It runs on the Module 3 deployment, driven through an *assistant* (a saved graph configuration) that swaps in a deliberately broken search tool so Engine has a clear, reproducible issue to find.

Engine's first analysis takes ~20 minutes, so it's best primed before a session. Needs the Module 3 deployment and a `LANGSMITH_API_KEY`.

## Project Structure

```
modular-workshops/
├── README.md                       (this file — recipes + setup)
├── pyproject.toml                  (shared dependencies)
├── .env.example
├── langgraph.json                  (registers agents/deep_agent for langgraph dev)
├── utils/
├── agents/
│   ├── research_agent.py           (shared agent factory — Module 1 references, Module 4 imports for eval)
│   └── deep_agent/                 (deployable + governed agent for Module 3)
│       ├── agent.py
│       ├── AGENTS.md
│       └── skills/
│           ├── linkedin-post/SKILL.md
│           └── twitter-post/SKILL.md
├── images/                         (diagrams used by the notebooks)
└── modules/
    ├── 01_deep_agents.ipynb        (Module 1)
    ├── 02_langgraph.ipynb          (Module 2)
    ├── 03_deploy_and_govern.ipynb  (Module 3)
    └── 04_langsmith.ipynb          (Module 4)
```

## Common Issues

**`langgraph deploy` fails with 403 / permission denied**
Your API key is a personal token. Generate a service key (`lsv2_sk_...`) in LangSmith settings.

**Notebook can't find `utils` / `agents`**
Each module's setup cell prepends `project_root` (the workshop root) to `sys.path`. If you moved a notebook, update the `Path().resolve().parent` line to point at the workshop root.

## For LangChain Internal Users
Please refer to this linked [Notion document](https://app.notion.com/p/Modular-Workshops-37d808527b1780318063fd210446aa03?source=copy_link) for instructions on setup and usage.
