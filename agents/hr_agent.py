"""Shared HR assistant agent used by Module 1 (Deep Agents) and Module 3 (LangSmith).

⚠️  ALL DATA IS SYNTHETIC — see utils/hr_seed.py.

This is the minimal useful Deep Agent for the workshop: an internal HR assistant
that answers employee questions by querying a transactional HR database and then
taking an action. It is a **retrieve-then-act** agent (look up facts in SQLite,
then optionally open an HR case), NOT a RAG-over-documents agent.

Tools
-----
- lookup_employee(employee_id | name) -> role, department, manager, location,
  tenure, salary_band, salary
- list_reports(manager_id)            -> direct reports
- get_comp_bands(job_family, level)   -> band min / mid / max
- open_hr_case(employee_id, category, summary) -> case id   (the "act" step)

It deliberately omits HITL and FilesystemBackend so evaluation runs in Module 3
don't pause or leak files to disk.

    from agents.hr_agent import build_hr_agent
    agent = build_hr_agent()
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from deepagents import create_deep_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from utils.models import model, judge_model
from utils.hr_seed import DB_PATH, seed_hr_db

# Resolve the DB relative to the repo root so it works from notebooks (run in
# modules/) and from the repo root alike.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DB_FILE = _REPO_ROOT / DB_PATH


def _ensure_db() -> str:
    """Seed the synthetic HR DB on first use if it isn't present yet."""
    if not _DB_FILE.exists():
        seed_hr_db(_DB_FILE)
    return str(_DB_FILE)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_ensure_db())
    conn.row_factory = sqlite3.Row
    return conn


def _tenure_years(hire_date: str) -> float:
    hd = date.fromisoformat(hire_date)
    return round((date(2025, 6, 1) - hd).days / 365.25, 1)


@tool(parse_docstring=True)
def lookup_employee(employee_id: int | None = None, name: str | None = None) -> str:
    """Look up an employee by ID or name.

    Returns role, department, manager, location, tenure, salary band, and salary.
    Prefer employee_id when you have it — names may be ambiguous (more than one
    employee can share a name). If a name matches multiple people, all matches are
    returned so you can disambiguate by employee_id.

    Args:
        employee_id: The employee's numeric ID (most reliable).
        name: The employee's full name (may be ambiguous).
    """
    if employee_id is None and not name:
        return "Error: provide either employee_id or name."

    conn = _connect()
    try:
        if employee_id is not None:
            rows = conn.execute(
                "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM employees WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchall()

        if not rows:
            who = f"id={employee_id}" if employee_id is not None else f"name={name!r}"
            return f"No employee found for {who}."

        if len(rows) > 1:
            lines = [
                f"Ambiguous — {len(rows)} employees match {name!r}. "
                "Disambiguate by employee_id:"
            ]
            for r in rows:
                lines.append(
                    f"  - id={r['employee_id']}, {r['role']}, {r['department']}, "
                    f"{r['location']}"
                )
            return "\n".join(lines)

        r = rows[0]
        mgr = None
        if r["manager_id"] is not None:
            m = conn.execute(
                "SELECT name FROM employees WHERE employee_id = ?", (r["manager_id"],)
            ).fetchone()
            mgr = f"{m['name']} (id={r['manager_id']})" if m else f"id={r['manager_id']}"

        band = conn.execute(
            "SELECT band_min, band_mid, band_max FROM comp_bands "
            "WHERE job_family = ? AND level = ?",
            (r["job_family"], r["level"]),
        ).fetchone()
        band_str = (
            f"{band['band_min']:,}/{band['band_mid']:,}/{band['band_max']:,}"
            if band
            else "unknown"
        )
        salary_str = f"${r['salary']:,}" if r["salary"] is not None else "NULL (not on record)"

        return (
            f"employee_id: {r['employee_id']}\n"
            f"name: {r['name']}\n"
            f"role: {r['role']}\n"
            f"department: {r['department']}\n"
            f"job_family / level: {r['job_family']} / {r['level']}\n"
            f"manager: {mgr or 'none'}\n"
            f"location: {r['location']}\n"
            f"tenure: {_tenure_years(r['hire_date'])} years (hired {r['hire_date']})\n"
            f"salary_band (min/mid/max): {band_str}\n"
            f"salary: {salary_str}"
        )
    finally:
        conn.close()


@tool(parse_docstring=True)
def list_reports(manager_id: int) -> str:
    """List the direct reports of a manager.

    Args:
        manager_id: The manager's employee ID.
    """
    conn = _connect()
    try:
        mgr = conn.execute(
            "SELECT name FROM employees WHERE employee_id = ?", (manager_id,)
        ).fetchone()
        if mgr is None:
            return f"No employee found for manager id={manager_id}."

        rows = conn.execute(
            "SELECT employee_id, name, role, job_family, level, salary "
            "FROM employees WHERE manager_id = ? ORDER BY employee_id",
            (manager_id,),
        ).fetchall()

        if not rows:
            return f"{mgr['name']} (id={manager_id}) has no direct reports."

        lines = [f"{mgr['name']} (id={manager_id}) has {len(rows)} direct report(s):"]
        for r in rows:
            salary_str = f"${r['salary']:,}" if r["salary"] is not None else "NULL"
            lines.append(
                f"  - id={r['employee_id']}, {r['name']}, {r['role']} "
                f"({r['job_family']} {r['level']}), salary {salary_str}"
            )
        return "\n".join(lines)
    finally:
        conn.close()


@tool(parse_docstring=True)
def get_comp_bands(job_family: str, level: str) -> str:
    """Get the compensation band (min / mid / max) for a job family and level.

    Args:
        job_family: e.g. "Software Engineering", "Sales", "Finance".
        level: One of L1, L2, L3, L4, L5.
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT band_min, band_mid, band_max FROM comp_bands "
            "WHERE job_family = ? COLLATE NOCASE AND level = ? COLLATE NOCASE",
            (job_family, level),
        ).fetchone()
        if row is None:
            families = [
                r["job_family"]
                for r in conn.execute(
                    "SELECT DISTINCT job_family FROM comp_bands ORDER BY job_family"
                ).fetchall()
            ]
            return (
                f"No band for job_family={job_family!r}, level={level!r}. "
                f"Known families: {', '.join(families)}. Levels: L1-L5."
            )
        return (
            f"{job_family} {level} band: "
            f"min ${row['band_min']:,} / mid ${row['band_mid']:,} / max ${row['band_max']:,}"
        )
    finally:
        conn.close()


@tool(parse_docstring=True)
def open_hr_case(employee_id: int, category: str, summary: str) -> str:
    """Open an HR case for an employee (the "act" step — writes to the cases table).

    Use this only after you have looked up the relevant facts. Returns the new
    case id.

    Args:
        employee_id: The employee the case is about.
        category: Short category, e.g. "comp_review", "band_adjustment", "data_quality".
        summary: One or two sentences describing why the case is being opened.
    """
    conn = _connect()
    try:
        emp = conn.execute(
            "SELECT name FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        if emp is None:
            return f"Cannot open case: no employee with id={employee_id}."

        cur = conn.execute(
            "INSERT INTO cases (employee_id, category, summary, status, created_at) "
            "VALUES (?, ?, ?, 'open', ?)",
            (employee_id, category, summary, date(2025, 6, 1).isoformat()),
        )
        conn.commit()
        case_id = cur.lastrowid
        return (
            f"Opened case #{case_id} ({category}) for {emp['name']} (id={employee_id}), "
            f"status=open."
        )
    finally:
        conn.close()


HR_TOOLS = [lookup_employee, list_reports, get_comp_bands, open_hr_case]

HR_SYSTEM_PROMPT = (
    "You are an internal HR assistant. You answer employee and manager questions by "
    "querying the HR database, then take an action when asked.\n\n"
    "Guidelines:\n"
    "- Always look up facts with the tools before answering; never guess salaries, "
    "bands, or reporting lines.\n"
    "- Prefer employee_id over name. If a name matches multiple employees, ask the "
    "user to disambiguate rather than picking one.\n"
    "- When checking whether someone is 'inside band', compare their salary to the "
    "band min/mid/max for their job_family and level. If salary is NULL, say it "
    "cannot be assessed.\n"
    "- Only open an HR case (open_hr_case) when the user explicitly asks you to act, "
    "and only after you've confirmed the relevant facts."
)


def build_hr_agent():
    """Return a fresh HR deep agent.

    Each call returns a new agent with a fresh checkpointer, so eval runs don't
    share state. The synthetic HR DB is seeded on first tool use if missing.
    """
    return create_deep_agent(
        model=model,
        tools=HR_TOOLS,
        system_prompt=HR_SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )
def build_hr_agent_judge():
    return create_deep_agent(
        model=judge_model
    )