"""Seed a fully-synthetic HR database for the Deep Agents workshop.

⚠️  ALL DATA IS SYNTHETIC. It is generated deterministically by this script.
There is no real employee, salary, or personal information anywhere in here.

The database (SQLite, `hr.db` by default) backs a *retrieve-then-act* HR
assistant — an agent that looks facts up in a transactional store and then
takes an action (opening an HR case), NOT a RAG-over-documents agent.

Schema
------
job_families(job_family TEXT PK, description TEXT)
comp_bands(job_family TEXT, level TEXT, band_min INT, band_mid INT,
           band_max INT, PRIMARY KEY (job_family, level))
employees(employee_id INT PK, name TEXT, role TEXT, department TEXT,
          manager_id INT, location TEXT, hire_date TEXT, job_family TEXT,
          level TEXT, salary INT)     -- salary may be NULL
cases(case_id INT PK, employee_id INT, category TEXT, summary TEXT,
      status TEXT, created_at TEXT)   -- the "act" step writes here

Deliberate edge cases (used to exercise the agent's judgment)
------------------------------------------------------------
- One employee paid BELOW their band minimum.
- One manager with NO direct reports.
- A DUPLICATE name shared by two different employees (lookup by name is
  ambiguous and must be disambiguated by employee_id).
- One employee with a NULL salary (cannot be assessed against band).

Usage
-----
    from utils.hr_seed import seed_hr_db, DB_PATH
    seed_hr_db()          # (re)creates ./hr.db
    seed_hr_db("/tmp/x.db", force=True)

Run directly to (re)build the DB and print a summary:
    python -m utils.hr_seed
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = "hr.db"

# Deterministic so every workshop run gets the same data (and the same edge cases).
_SEED = 42

JOB_FAMILIES: list[tuple[str, str]] = [
    ("Software Engineering", "Builds and maintains software products."),
    ("Data Science", "Modeling, analytics, and machine learning."),
    ("Product Management", "Owns product strategy and roadmap."),
    ("Design", "Product, brand, and UX design."),
    ("Sales", "New business and account growth."),
    ("Marketing", "Demand generation, brand, and comms."),
    ("Customer Success", "Onboarding, retention, and support."),
    ("Finance", "Accounting, FP&A, and treasury."),
    ("People", "Recruiting, HR operations, and L&D."),
    ("Legal", "Contracts, compliance, and counsel."),
    ("IT", "Internal systems and helpdesk."),
    ("Operations", "Business operations and logistics."),
]

LEVELS = ["L1", "L2", "L3", "L4", "L5"]

# Base midpoint per level (USD). Each job family scales these by a multiplier.
_LEVEL_BASE_MID = {"L1": 85_000, "L2": 110_000, "L3": 140_000, "L4": 180_000, "L5": 230_000}

# Comp is family-dependent: engineering/data/product pay above ops/success, etc.
_FAMILY_MULTIPLIER = {
    "Software Engineering": 1.20,
    "Data Science": 1.18,
    "Product Management": 1.15,
    "Design": 1.00,
    "Sales": 1.05,
    "Marketing": 0.95,
    "Customer Success": 0.90,
    "Finance": 1.00,
    "People": 0.92,
    "Legal": 1.10,
    "IT": 0.95,
    "Operations": 0.90,
}

# role title per (family, level) — kept simple for the demo
_ROLE_STEM = {
    "Software Engineering": "Software Engineer",
    "Data Science": "Data Scientist",
    "Product Management": "Product Manager",
    "Design": "Designer",
    "Sales": "Account Executive",
    "Marketing": "Marketing Manager",
    "Customer Success": "Customer Success Manager",
    "Finance": "Finance Analyst",
    "People": "People Partner",
    "Legal": "Counsel",
    "IT": "IT Specialist",
    "Operations": "Operations Analyst",
}

_LEVEL_TITLE_PREFIX = {
    "L1": "Associate ",
    "L2": "",
    "L3": "Senior ",
    "L4": "Staff ",
    "L5": "Principal ",
}

LOCATIONS = [
    "New York, NY",
    "San Francisco, CA",
    "Austin, TX",
    "Chicago, IL",
    "Remote (US)",
    "London, UK",
    "Toronto, CA",
    "Berlin, DE",
]

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery",
    "Quinn", "Cameron", "Sydney", "Reese", "Harper", "Rowan", "Emerson", "Finley",
    "Dakota", "Skyler", "Kendall", "Parker", "Priya", "Wei", "Diego", "Amara",
    "Noor", "Kenji", "Lucia", "Omar", "Mei", "Sofia", "Ivan", "Fatima",
]
_LAST_NAMES = [
    "Chen", "Patel", "Garcia", "Nguyen", "Kim", "Johnson", "Smith", "Brown",
    "Okafor", "Rossi", "Muller", "Andersson", "Silva", "Ahmed", "Cohen", "Reyes",
    "Tanaka", "Novak", "Haddad", "Ivanov", "Costa", "Dubois", "Larsson", "Khan",
]


def _band_for(job_family: str, level: str) -> tuple[int, int, int]:
    """Return (band_min, band_mid, band_max) for a family+level."""
    mid = round(_LEVEL_BASE_MID[level] * _FAMILY_MULTIPLIER[job_family] / 1000) * 1000
    band_min = round(mid * 0.85 / 1000) * 1000
    band_max = round(mid * 1.15 / 1000) * 1000
    return band_min, mid, band_max


def _make_name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _role_title(job_family: str, level: str) -> str:
    return f"{_LEVEL_TITLE_PREFIX[level]}{_ROLE_STEM[job_family]}".strip()


def build_rows(n_employees: int = 200):
    """Build all table rows in memory (pure, no DB). Returns a dict of lists."""
    rng = random.Random(_SEED)

    comp_bands = []
    for family, _desc in JOB_FAMILIES:
        for level in LEVELS:
            band_min, band_mid, band_max = _band_for(family, level)
            comp_bands.append((family, level, band_min, band_mid, band_max))

    employees = []
    today = date(2025, 6, 1)  # fixed "today" so tenure is stable across runs

    # First pass: create everyone with a manager placeholder of None.
    for emp_id in range(1001, 1001 + n_employees):
        family = rng.choice([f for f, _ in JOB_FAMILIES])
        # Higher levels are rarer.
        level = rng.choices(LEVELS, weights=[30, 30, 22, 12, 6], k=1)[0]
        band_min, band_mid, band_max = _band_for(family, level)
        # Salary drawn around the band, mostly inside it.
        salary = int(rng.triangular(band_min * 0.95, band_max * 1.02, band_mid))
        salary = round(salary / 500) * 500
        hire_offset_days = rng.randint(30, 365 * 12)
        hire_date = (today - timedelta(days=hire_offset_days)).isoformat()
        employees.append(
            {
                "employee_id": emp_id,
                "name": _make_name(rng),
                "role": _role_title(family, level),
                "department": family,
                "manager_id": None,
                "location": rng.choice(LOCATIONS),
                "hire_date": hire_date,
                "job_family": family,
                "level": level,
                "salary": salary,
            }
        )

    # Assign managers: L4/L5 are candidate managers; everyone else reports to
    # someone senior in a matching or random department.
    senior = [e for e in employees if e["level"] in ("L4", "L5")]
    senior_ids = [e["employee_id"] for e in senior]
    for e in employees:
        if e["level"] in ("L4", "L5"):
            # Top of chain reports to another senior (or no one).
            candidates = [sid for sid in senior_ids if sid != e["employee_id"]]
            e["manager_id"] = rng.choice(candidates) if candidates and rng.random() < 0.7 else None
        else:
            e["manager_id"] = rng.choice(senior_ids)

    # ---- Deliberate edge cases -------------------------------------------
    by_id = {e["employee_id"]: e for e in employees}
    band_lookup = {(f, l): (mn, md, mx) for (f, l, mn, md, mx) in comp_bands}

    # (1) Below band minimum: force employee 1001 under their band_min.
    e1 = by_id[1001]
    mn, _md, _mx = band_lookup[(e1["job_family"], e1["level"])]
    e1["salary"] = mn - 12_000

    # (2) Manager with NO direct reports: create a dedicated senior manager and
    #     make sure nobody reports to them.
    lonely_id = 1001 + n_employees  # one past the normal range
    lonely_family = "Operations"
    lonely_level = "L4"
    lmn, lmd, lmx = band_lookup[(lonely_family, lonely_level)]
    employees.append(
        {
            "employee_id": lonely_id,
            "name": "Jordan Lee",
            "role": _role_title(lonely_family, lonely_level),
            "department": lonely_family,
            "manager_id": None,
            "location": "Remote (US)",
            "hire_date": (today - timedelta(days=500)).isoformat(),
            "job_family": lonely_family,
            "level": lonely_level,
            "salary": lmd,
        }
    )

    # (3) Duplicate name: give employee 1002 the exact same name as 1003.
    by_id[1002]["name"] = by_id[1003]["name"]

    # (4) NULL salary: employee 1004 has no salary on record.
    by_id[1004]["salary"] = None

    return {
        "job_families": [(f, d) for f, d in JOB_FAMILIES],
        "comp_bands": comp_bands,
        "employees": employees,
    }


def seed_hr_db(db_path: str | Path = DB_PATH, *, n_employees: int = 200, force: bool = True) -> str:
    """(Re)create the synthetic HR SQLite database. Returns the path as a str.

    Args:
        db_path: Where to write the SQLite file.
        n_employees: How many "normal" employees to generate (~200 default).
        force: If True (default), overwrite any existing file so re-runs are clean.
    """
    db_path = Path(db_path)
    if force and db_path.exists():
        db_path.unlink()

    data = build_rows(n_employees=n_employees)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            DROP TABLE IF EXISTS cases;
            DROP TABLE IF EXISTS employees;
            DROP TABLE IF EXISTS comp_bands;
            DROP TABLE IF EXISTS job_families;

            CREATE TABLE job_families (
                job_family  TEXT PRIMARY KEY,
                description TEXT
            );

            CREATE TABLE comp_bands (
                job_family TEXT NOT NULL,
                level      TEXT NOT NULL,
                band_min   INTEGER NOT NULL,
                band_mid   INTEGER NOT NULL,
                band_max   INTEGER NOT NULL,
                PRIMARY KEY (job_family, level)
            );

            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                role        TEXT NOT NULL,
                department  TEXT NOT NULL,
                manager_id  INTEGER,
                location    TEXT NOT NULL,
                hire_date   TEXT NOT NULL,
                job_family  TEXT NOT NULL,
                level       TEXT NOT NULL,
                salary      INTEGER
            );

            CREATE TABLE cases (
                case_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                category    TEXT NOT NULL,
                summary     TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                created_at  TEXT NOT NULL
            );
            """
        )

        cur.executemany(
            "INSERT INTO job_families (job_family, description) VALUES (?, ?)",
            data["job_families"],
        )
        cur.executemany(
            "INSERT INTO comp_bands (job_family, level, band_min, band_mid, band_max) "
            "VALUES (?, ?, ?, ?, ?)",
            data["comp_bands"],
        )
        cur.executemany(
            "INSERT INTO employees (employee_id, name, role, department, manager_id, "
            "location, hire_date, job_family, level, salary) "
            "VALUES (:employee_id, :name, :role, :department, :manager_id, :location, "
            ":hire_date, :job_family, :level, :salary)",
            data["employees"],
        )
        conn.commit()
    finally:
        conn.close()

    return str(db_path)


def _summary(db_path: str | Path = DB_PATH) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        n_emp = cur.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        n_fam = cur.execute("SELECT COUNT(*) FROM job_families").fetchone()[0]
        n_band = cur.execute("SELECT COUNT(*) FROM comp_bands").fetchone()[0]
        n_case = cur.execute("SELECT COUNT(*) FROM cases").fetchone()[0]

        below = cur.execute(
            """
            SELECT e.employee_id, e.name, e.salary, b.band_min
            FROM employees e JOIN comp_bands b
              ON e.job_family = b.job_family AND e.level = b.level
            WHERE e.salary IS NOT NULL AND e.salary < b.band_min
            """
        ).fetchall()
        null_sal = cur.execute(
            "SELECT employee_id, name FROM employees WHERE salary IS NULL"
        ).fetchall()
        dupes = cur.execute(
            """
            SELECT name, COUNT(*) c FROM employees GROUP BY name HAVING c > 1
            """
        ).fetchall()
        no_reports = cur.execute(
            """
            SELECT employee_id, name FROM employees
            WHERE level IN ('L4','L5')
              AND employee_id NOT IN (SELECT manager_id FROM employees WHERE manager_id IS NOT NULL)
            """
        ).fetchall()
    finally:
        conn.close()

    lines = [
        "Synthetic HR database seeded (ALL DATA IS FAKE).",
        f"  employees:    {n_emp}",
        f"  job_families: {n_fam}",
        f"  comp_bands:   {n_band}",
        f"  cases:        {n_case}",
        "",
        "Edge cases present:",
        f"  below band min: {[(r['employee_id'], r['name']) for r in below]}",
        f"  null salary:    {[(r['employee_id'], r['name']) for r in null_sal]}",
        f"  duplicate name: {[(r['name'], r['c']) for r in dupes]}",
        f"  managers w/ no reports: {len(no_reports)} (e.g. {[(r['employee_id'], r['name']) for r in no_reports[:3]]})",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    path = seed_hr_db()
    print(f"Wrote {path}\n")
    print(_summary(path))
