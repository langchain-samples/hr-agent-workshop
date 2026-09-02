"""Target function: run the HR agent on one dataset example.

Returns the fields every evaluator needs from a single agent run:

- ``response``    : the assistant's final message text
- ``trajectory``  : the ordered list of tool names the agent called

Keeping this in one place means the offline experiment scores the *same*
behavior the four evaluators inspect, from a single invocation per example.
"""

from __future__ import annotations

from typing import Any

from langsmith import uuid7

from agents.hr_agent import build_hr_agent

# One agent instance is fine — each call uses a fresh thread_id.
_agent = build_hr_agent()


def _extract_tool_calls(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            names.append(tc["name"])
    return names


def run_hr_agent(inputs: dict) -> dict:
    """Invoke the HR agent and return {response, trajectory}."""
    config = {"configurable": {"thread_id": str(uuid7())}}
    result = _agent.invoke(
        {"messages": [{"role": "user", "content": inputs["query"]}]},
        config=config,
    )
    return {
        "response": result["messages"][-1].text,
        "trajectory": _extract_tool_calls(result["messages"]),
    }
