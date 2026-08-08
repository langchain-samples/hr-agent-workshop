# Test GitHub Codespaces

> [!IMPORTANT]
> This Codespaces configuration is experimental. It launches the `codex/add-codespaces-support` branch and does not change the default setup on `main`.

[![Open the experimental Codespace](https://github.com/codespaces/badge.svg)](https://codespaces.new/langchain-ai/modular-workshops?ref=codex/add-codespaces-support)

Use this guide for limited testing before the Codespaces setup is documented for workshop attendees. A GitHub account with access to Codespaces is required. Availability, usage quotas, and organization policies vary.

## What setup does

On first launch, the devcontainer:

1. Installs uv using Astral's installer.
2. Runs `uv sync --frozen` to create the exact locked `.venv`.
3. Configures VS Code to use `.venv/bin/python`.
4. Generates an ignored `.env` from `.env.example`, overlaying any recognized Codespaces secrets.

Notebooks can read injected Codespaces secrets directly from the environment. The generated `.env` is especially important for Module 3 because the `langgraph` CLI loads it.

## Test without secrets

1. Launch the Codespace with the badge above and wait for `postCreateCommand` to finish.
2. Confirm the terminal reports a successful frozen dependency sync.
3. Confirm VS Code selects `.venv/bin/python` as the notebook kernel. Select it manually if prompted.
4. Confirm `.env` contains one labeled, blank entry for each expected variable:
   - `OPENAI_API_KEY`
   - `LANGSMITH_API_KEY`
   - `LANGSMITH_API_KEY_GATEWAY`
   - `WORKSPACE_ID`
   - `TAVILY_API_KEY`
5. Open a notebook in `modules/` and confirm its imports succeed. Model calls are expected to fail until the required keys are configured.
6. Run `git status --short` and confirm `.env` is not listed.

## Test with Codespaces secrets

1. In GitHub, open **Settings → Codespaces → Secrets**.
2. Add the keys required by the modules you plan to test and scope them to this repository. Use the key table in the main README as the source of truth.
3. Create a new Codespace from the experimental badge above.
4. Confirm the generated `.env` still contains each expected variable exactly once and that configured entries are populated.
5. Run the selected notebooks and confirm model calls work without manually copying keys.
6. For Module 3, confirm the `langgraph` CLI can start the configured graph using the generated `.env`.

Never commit real keys. For a one-off test, you can instead add values to the generated `.env`; restart an active notebook kernel after changing them.

## Report results

Record the following in the draft pull request:

- Codespace creation and setup duration
- Whether `.venv` was selected automatically
- Notebook and Module 3 scenarios tested
- Any organization, proxy, or permissions issues
- Relevant setup errors with secret values removed

Delete the test Codespace when you no longer need it.

## Maintenance notes

| If you change | Also update | Why |
|---|---|---|
| A dependency | `uv.lock` | The devcontainer runs `uv sync --frozen`, so a stale lockfile causes setup to fail instead of silently resolving different versions. |
| An API key or environment variable name | `.env.example`, the `keys` list in `.devcontainer/setup.sh`, and the README key table | This keeps generated labels, injected Codespaces secrets, and attendee instructions aligned. |
| The supported Python version in `pyproject.toml` | The Python image tag in `.devcontainer/devcontainer.json` | The container Python version should satisfy the project requirement. |
| A required VS Code extension or setting | `customizations.vscode` in `.devcontainer/devcontainer.json` | Every tester receives the same editor setup. |

If Codespaces prebuilds are added later, keep `.env` generation in `postCreateCommand` so secrets remain per-user and are never baked into a shared prebuild.
