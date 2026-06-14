# Vendor Governance API

> Mock API is **live**. Persons 3, 4, and 5 can start building immediately — no Band credentials needed.

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/ntsqvl/prism.git
cd prism

# 2. Install dependencies (reads pyproject.toml — no uv add needed)
uv sync

# 3. Copy the env file and confirm MOCK_MODE=true is set
cp .env.example .env        # Mac/Linux
copy .env.example .env      # Windows

# 4. Start the server
uv run uvicorn main:app --reload
```

Server runs at `http://localhost:8000`.

---

## Quick Sanity Check

Run these in order to confirm everything works before you build:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Start a mock evaluation
curl -X POST "http://localhost:8000/api/start-evaluation?vendor_name=TestVendor"
# → copy the workflow_id from the response

# 3. Poll status (run a few times, 2 seconds apart — watch the stage change)
curl http://localhost:8000/api/workflow-status/wf-YOUR-ID-HERE

# 4. See the full schema reference
curl http://localhost:8000/api/mock-schema
```

> **Notes**
> - The mock workflow takes ~30 seconds end to end — intentional so the frontend sees live updates
> - All field names are final — nothing will be renamed when we switch to live agents
> - `audit_log` is an array of timestamped strings — Person 5, this powers the timeline view
> - Person 2 will flip `MOCK_MODE=false` once Band agent keys are sorted — your code doesn't change

---

## Endpoints

### 👤 Person 5 — Frontend

**Start an evaluation**
```
POST /api/start-evaluation?vendor_name=Vendor+A
```
```json
{ "workflow_id": "wf-abc12345", "mode": "mock", "status": "started" }
```

**Poll for live status** (every 2 seconds)
GET /api/workflow-status/{workflow_id}

The response evolves through every stage over ~30 seconds:
`intake → evaluation → conflict_check → stakeholder_alignment → escalated → complete`

Agent scores trickle in one by one, the conflict appears mid-way, discussion messages populate, and the final recommendation lands at the end. Build your UI against this — it's the real shape of the data.

**Full schema reference**
GET /api/mock-schema

Bookmark this. It's the contract everyone builds against.

**Human reviewer — conflict escalation button**

When `overall_status` is `escalated_to_procurement`, show the approval button. It calls:
POST /api/resolve-conflict/{workflow_id}?resolution=escalated_to_procurement

---

### 🤖 Person 3 — financial_agent + technical_agent

POST each result as your agents produce them:

```bash
POST /api/submit-evaluation
```
```json
{
  "workflow_id": "wf-abc12345",
  "agent_name": "financial_agent",
  "score": 95,
  "verdict": "approved",
  "note": "Lowest TCO among all vendors."
}
```

---

### 🤖 Person 4 — legal_agent + security_agent + Chief Procurement Agent

POST each specialist result:

```bash
POST /api/submit-evaluation
```
```json
{
  "workflow_id": "wf-abc12345",
  "agent_name": "security_agent",
  "score": 40,
  "verdict": "rejected",
  "note": "Fails data residency requirements."
}
```

Once all 4 specialist agents have submitted, conflict detection runs automatically and `workflow_stage` moves to `conflict_check` then `stakeholder_alignment`.

Then your **Chief Procurement Agent** uses a separate endpoint:

```bash
POST /api/set-final-recommendation/{workflow_id}
```
```json
{
  "ranked_vendors": ["Vendor C", "Vendor B", "Vendor A"],
  "justifications": {
    "Vendor C": "Balanced cost and compliance — no major red flags.",
    "Vendor B": "Strong compliance; cost high but acceptable.",
    "Vendor A": "De-prioritized: data residency failure outweighs cost advantage."
  },
  "selected_vendor": "Vendor C"
}
```

---

## Reference

### agent_name values

| Agent | Person |
|---|---|
| `financial_agent` | Person 3 |
| `technical_agent` | Person 3 |
| `legal_agent` | Person 4 |
| `security_agent` | Person 4 |

### verdict values

| Value | Meaning |
|---|---|
| `approved` | Agent recommends this vendor |
| `rejected` | Agent recommends against |
| `flagged` | Borderline — noted but doesn't trigger conflict |

> `score` is an integer `0–100`. `verdict` and `agent_name` must match exactly as shown above.

### overall_status values

| Value | Meaning |
|---|---|
| `started` | Workflow just created |
| `conflict_detected` | At least one approve vs. one reject |
| `escalated_to_procurement` | Human reviewer must approve |
| `awaiting_decision` | All agents in, no conflict |
| `complete` | Final recommendation is set |
| `timed_out` | Agents didn't respond in time |

---

## Workflow Shape

intake

└─ evaluation               ← agent scores trickle in here
└─ conflict_check       ← auto-runs when all 4 are in
├─ stakeholder_alignment   ← conflict exists, agents debate
│    └─ escalated          ← human reviewer needed
└─ decision                ← no conflict, straight to recommendation
└─ complete

---

## Conflict Detection Rule

A conflict triggers when **at least one agent verdicts `rejected` while at least one other verdicts `approved`** for the same vendor.

For the demo to reliably show the conflict:
- `financial_agent` → `approved`
- `security_agent` → `rejected`

The conflict type (`Cost vs Compliance`) and severity (`high` — score gap ≥ 50) are derived automatically.
