#!/usr/bin/env bash
set -euo pipefail

# 1. Install uv, then build the exact locked environment.
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --frozen

# 2. Generate .env for the langgraph CLI by overlaying any injected Codespaces
#    secrets onto the committed template. Notebooks read injected env vars directly.
python3 - <<'PY'
import os

keys = [
    "OPENAI_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGSMITH_API_KEY_GATEWAY",
    "WORKSPACE_ID",
    "TAVILY_API_KEY",
]
try:
    template = open(".env.example").read().splitlines()
except FileNotFoundError:
    template = [f"{key}=" for key in keys]

seen, out = set(), []
for line in template:
    key = (
        line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#")
        else None
    )
    if key in keys:
        if key in seen:
            continue
        out.append(f"{key}={os.environ.get(key, '')}")
        seen.add(key)
    else:
        out.append(line)
for key in keys:
    if key not in seen:
        out.append(f"{key}={os.environ.get(key, '')}")

open(".env", "w").write("\n".join(out) + "\n")
PY
