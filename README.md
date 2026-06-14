

# Status
Mock API is live. Persons 3, 4, and 5 can start building immediately — no Band credentials needed.

# Base URL
http://localhost:8000        # local dev

## Setup

```bash
# Clone the repo and go to the backend folder
git clone https://github.com/ntsqvl/prism.git
cd prism

# Install dependencies (reads pyproject.toml — no uv add needed)
uv sync

# Copy the env file — confirm MOCK_MODE=true is set
cp .env.example .env          # Mac/Linux
copy .env.example .env        # Windows Command Prompt

# Start the server
uv run uvicorn main:app --reload
```

Server runs at `http://localhost:8000`. Then run the sanity checks below.

# Quick Sanity Check
Run these in order to confirm everything works before you build:
bash
# 1. Health check
curl http://localhost:8000/health

# 2. Start a mock evaluation
curl -X POST "http://localhost:8000/api/start-evaluation?vendor_name=TestVendor"
# → copy the workflow_id from the response

# 3. Poll status (run a few times, 2s apart — watch the stage change)
curl http://localhost:8000/api/workflow-status/wf-YOUR-ID-HERE

# 4. See the full schema reference
curl http://localhost:8000/api/mock-schema

Notes

The mock workflow takes ~30 seconds to run through all stages end to end — this is intentional so the frontend has time to show live updates
All fields that appear in the mock will appear in the real data with the same names and types — nothing will be renamed when we switch to live agents
audit_log is an array of timestamped strings — Person 5, this is what powers the timeline/audit trail view
Person 2 will flip MOCK_MODE=false once Band agent keys are sorted — your code doesn't change when that happens

# The Two Endpoints You Actually Need
Person 5 (Frontend)
Start an evaluation:
POST /api/start-evaluation?vendor_name=Vendor+A

Returns:
json{ "workflow_id": "wf-abc12345", "mode": "mock", "status": "started" }

Poll for status (every 2 seconds):

GET /api/workflow-status/wf-abc12345 (change according to what you get)

The response evolves over ~30 seconds through every stage: 
intake → evaluation → conflict_check → stakeholder_alignment → escalated → complete. 

Agent scores trickle in one by one, the conflict appears mid-way, discussion messages populate, and the final recommendation lands at the end. Build your UI against this — it's the real shape of the data.

# See the full agreed schema with sample data:
GET /api/mock-schema
Bookmark this. It's the contract everyone builds against.

# Persons 3 & 4 (Agent Builders)
When your agents produce a result, POST it here directly — no Band setup required yet:
POST /api/submit-evaluation
json{
  "workflow_id": "wf-abc12345",
  "agent_name": "financial_agent",
  "score": 95,
  "verdict": "approved",
  "note": "Lowest TCO among all vendors."
}
agent_name must be exactly one of:

financial_agent
security_agent
legal_agent
technical_agent

verdict must be exactly one of: approved / rejected / flagged
score is an integer 0–100.
Once all 4 agents have submitted, conflict detection runs automatically. You'll see workflow_stage move to conflict_check then stakeholder_alignment in the status response.

# Full Workflow Shape
intake
  └─ evaluation          ← agent scores trickle in here
       └─ conflict_check ← auto-runs when all 4 are in
            ├─ stakeholder_alignment  ← conflict exists, agents debate
            │    └─ escalated         ← human reviewer needed
            └─ decision               ← no conflict, straight to recommendation
                 └─ complete


# overall_status values
ValueMeaningstartedWorkflow just createdconflict_detectedAt least one approve vs. one rejectescalated_to_procurementHuman reviewer must approveawaiting_decisionAll agents in, no conflictcompleteFinal recommendation is settimed_outAgents didn't respond in time

# Conflict Detection Rule (important for Persons 3 & 4)
A conflict is triggered when at least one agent verdicts rejected while at least one other verdicts approved for the same vendor. So for the demo to reliably show the conflict:

financial_agent → approved
security_agent → rejected

That's it. The conflict type (Cost vs Compliance) and severity (high — score gap ≥ 50) are derived automatically.

# Human Reviewer Endpoint (Person 5)
When overall_status is escalated_to_procurement, show the approval button. Clicking it calls:
POST /api/resolve-conflict/wf-abc12345?resolution=escalated_to_procurement

# Final Recommendation (Person 4 — Chief Procurement Agent)
After all conflicts are resolved, the Chief Procurement Agent POSTs its final ranking here:
POST /api/set-final-recommendation/wf-abc12345
json{
  "ranked_vendors": ["Vendor C", "Vendor B", "Vendor A"],
  "justifications": {
    "Vendor C": "Balanced cost and compliance — no major red flags.",
    "Vendor B": "Strong compliance; cost high but acceptable.",
    "Vendor A": "De-prioritized: data residency failure outweighs cost advantage."
  },
  "selected_vendor": "Vendor C"
}
