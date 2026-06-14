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