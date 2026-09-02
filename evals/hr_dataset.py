"""LangSmith dataset for the internal HR assistant.

⚠️  All data is synthetic (utils/hr_seed.py). These examples encode the
representative questions the HR agent must handle, plus the deliberate edge
cases, together with reference answers the evaluators grade against.

Each example's `outputs` (the *reference*) carries four kinds of ground truth so
the four evaluators can each find what they need:

- ``reference_answer``    : a success rubric + the key figures the answer must contain
- ``expected_figures``    : list of exact numeric/string figures that must appear
                            in the agent's response (correctness-of-figures eval)
- ``expected_tools``      : the tools the agent should call, as a multiset
                            (tool-selection / trajectory eval)
- ``should_open_case``    : bool — whether open_hr_case must be called for this
                            example (case-opened-iff-should eval)

Build or refresh the dataset with :func:`build_dataset`. It is idempotent:
re-running replaces the dataset so the examples always match this file.
"""

from __future__ import annotations

from typing import Any

from langsmith import Client

DATASET_NAME = "hr-agent-evals"

# --------------------------------------------------------------------------- #
# Examples. Figures below are taken verbatim from the seeded synthetic DB.
# --------------------------------------------------------------------------- #

EXAMPLES: list[dict[str, Any]] = [
    # --- Representative "inside band?" questions -----------------------------
    {
        "inputs": {"query": "Is employee 1001 paid inside band for their level?"},
        "outputs": {
            "reference_answer": (
                "Employee 1001 (Emerson Kim, IT L1) earns $57,000, which is BELOW the "
                "band minimum of $69,000 (band 69,000 / 81,000 / 93,000). Not inside band."
            ),
            "expected_figures": ["57,000", "69,000"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    {
        "inputs": {"query": "Is employee 1005 paid inside band for their level?"},
        "outputs": {
            "reference_answer": (
                "Employee 1005 (Riley Silva, Product Management L1) earns $103,000, "
                "inside the band 83,000 / 98,000 / 113,000 (above mid, below max)."
            ),
            "expected_figures": ["103,000", "113,000"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    {
        "inputs": {"query": "Is employee 1008 inside band for their level?"},
        "outputs": {
            "reference_answer": (
                "Employee 1008 (Emerson Nguyen, Software Engineering L3) earns $177,000, "
                "inside the band 143,000 / 168,000 / 193,000."
            ),
            "expected_figures": ["177,000", "193,000"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    # --- Edge case: NULL salary --------------------------------------------
    {
        "inputs": {"query": "Is employee 1004 paid inside band for their level?"},
        "outputs": {
            "reference_answer": (
                "Employee 1004 (Omar Muller, Legal L1) has NO salary on record (NULL), "
                "so it cannot be assessed against the band 80,000 / 94,000 / 108,000."
            ),
            "expected_figures": ["NULL"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    # --- Edge case: duplicate name -> must disambiguate ---------------------
    {
        "inputs": {"query": "Look up Lucia Brown and tell me their salary."},
        "outputs": {
            "reference_answer": (
                "The name 'Lucia Brown' is ambiguous — it matches two employees "
                "(id 1002, IT; id 1003, Design). The assistant should ask the user to "
                "disambiguate by employee_id rather than pick one or report a salary."
            ),
            "expected_figures": ["1002", "1003"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    # --- get_comp_bands lookups --------------------------------------------
    {
        "inputs": {"query": "What is the comp band for Software Engineering L3?"},
        "outputs": {
            "reference_answer": (
                "Software Engineering L3 band: min $143,000 / mid $168,000 / max $193,000."
            ),
            "expected_figures": ["143,000", "168,000", "193,000"],
            "expected_tools": ["get_comp_bands"],
            "should_open_case": False,
        },
    },
    {
        "inputs": {"query": "What is the min, mid, and max comp band for Legal L1?"},
        "outputs": {
            "reference_answer": "Legal L1 band: min $80,000 / mid $94,000 / max $108,000.",
            "expected_figures": ["80,000", "94,000", "108,000"],
            "expected_tools": ["get_comp_bands"],
            "should_open_case": False,
        },
    },
    # --- list_reports -------------------------------------------------------
    {
        "inputs": {"query": "How many direct reports does manager 1062 have?"},
        "outputs": {
            "reference_answer": "Manager 1062 (Parker Silva) has 7 direct reports.",
            "expected_figures": ["7"],
            "expected_tools": ["list_reports"],
            "should_open_case": False,
        },
    },
    # --- Edge case: manager with no reports --------------------------------
    {
        "inputs": {"query": "Who reports to manager 1201?"},
        "outputs": {
            "reference_answer": (
                "Manager 1201 (Jordan Lee) has NO direct reports."
            ),
            "expected_figures": ["no direct reports"],
            "expected_tools": ["list_reports"],
            "should_open_case": False,
        },
    },
    # --- Team review: who is below band mid --------------------------------
    {
        "inputs": {
            "query": "Who reports to manager 1062, and are any of them below band mid?"
        },
        "outputs": {
            "reference_answer": (
                "Manager 1062 (Parker Silva) has 7 reports. Five are below band mid: "
                "1079 (Reese Patel), 1089 (Cameron Ahmed), 1182 (Parker Khan), "
                "1184 (Fatima Ivanov), and 1193 (Kenji Rossi)."
            ),
            "expected_figures": ["1079", "1089", "1182", "1184", "1193"],
            "expected_tools": ["list_reports"],
            "should_open_case": False,
        },
    },
    # --- Full retrieve-then-ACT: should open a case ------------------------
    {
        "inputs": {
            "query": (
                "Employee 1001 is paid below band minimum. Open a comp review case for them."
            )
        },
        "outputs": {
            "reference_answer": (
                "The assistant should confirm 1001 is below band min ($57,000 vs $69,000) "
                "and then OPEN an HR case (open_hr_case) for employee 1001, returning a case id."
            ),
            "expected_figures": ["57,000"],
            "expected_tools": ["lookup_employee", "open_hr_case"],
            "should_open_case": True,
        },
    },
    {
        "inputs": {
            "query": (
                "Confirm whether employee 1001 is below band min, and if so open a "
                "comp_review case for them."
            )
        },
        "outputs": {
            "reference_answer": (
                "1001 is below band min ($57,000 vs $69,000). The assistant should open a "
                "comp_review HR case for employee 1001 and return the case id."
            ),
            "expected_figures": ["57,000", "69,000"],
            "expected_tools": ["lookup_employee", "open_hr_case"],
            "should_open_case": True,
        },
    },
    {
        "inputs": {
            "query": (
                "Employee 1004 has no salary on record. Open a data_quality case so payroll "
                "can fix it."
            )
        },
        "outputs": {
            "reference_answer": (
                "Employee 1004 (Omar Muller) has a NULL salary. The assistant should open a "
                "data_quality HR case for employee 1004 and return the case id."
            ),
            "expected_figures": ["NULL"],
            "expected_tools": ["lookup_employee", "open_hr_case"],
            "should_open_case": True,
        },
    },
    # --- Should NOT open a case (read-only intent) -------------------------
    {
        "inputs": {
            "query": (
                "Is employee 1005 inside band? Just tell me — do not open any case."
            )
        },
        "outputs": {
            "reference_answer": (
                "Employee 1005 (Riley Silva) is inside band (103,000 in 83,000 / 98,000 / "
                "113,000). No case should be opened."
            ),
            "expected_figures": ["103,000"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
    {
        "inputs": {
            "query": "Give me the full profile for employee 1001 (role, department, manager, tenure)."
        },
        "outputs": {
            "reference_answer": (
                "Employee 1001 is Emerson Kim, Associate IT Specialist in IT (job family IT, "
                "level L1), reporting to manager id 1168. Read-only lookup; no case."
            ),
            "expected_figures": ["1001", "IT"],
            "expected_tools": ["lookup_employee"],
            "should_open_case": False,
        },
    },
]


def build_dataset(client: Client | None = None, dataset_name: str = DATASET_NAME):
    """(Re)create the LangSmith dataset from EXAMPLES. Idempotent.

    Returns the created dataset object.
    """
    client = client or Client()

    if client.has_dataset(dataset_name=dataset_name):
        existing = client.read_dataset(dataset_name=dataset_name)
        client.delete_dataset(dataset_id=existing.id)

    dataset = client.create_dataset(
        dataset_name,
        description="Synthetic HR assistant eval set (representative questions + edge cases).",
    )
    client.create_examples(
        inputs=[e["inputs"] for e in EXAMPLES],
        outputs=[e["outputs"] for e in EXAMPLES],
        dataset_id=dataset.id,
    )
    return dataset


if __name__ == "__main__":
    ds = build_dataset()
    print(f"Created dataset '{ds.name}' with {len(EXAMPLES)} examples")
    print(f"View: {ds.url}")
