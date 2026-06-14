"""
Vendor Selection & Governance API
Person 2 — Band Orchestration Engineer

SET MOCK_MODE=true in .env to run without Band (unblocks teammates).
SET MOCK_MODE=false when real agents are ready.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum
import uuid
from datetime import datetime
import asyncio
import json
import os

# ---------------------------------------------------------------------------
# Toggle: flip to False once real agents exist
# ---------------------------------------------------------------------------
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

if not MOCK_MODE:
    from band_client import (
        create_evaluation_room,
        add_participant,
        trigger_workflow,
        get_chat_messages,
    )

# ===========================================================================
# App
# ===========================================================================

app = FastAPI(title="Vendor Selection & Governance API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================================================
# Models  (shared by mock + real paths)
# ===========================================================================

class WorkflowStage(str, Enum):
    INTAKE              = "intake"
    EVALUATION          = "evaluation"
    CONFLICT_CHECK      = "conflict_check"
    STAKEHOLDER_ALIGN   = "stakeholder_alignment"
    DECISION            = "decision"
    ESCALATED           = "escalated"
    COMPLETE            = "complete"


class Verdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED  = "flagged"


class ConflictType(str, Enum):
    COST_VS_COMPLIANCE      = "Cost vs Compliance"
    COST_VS_LEGAL           = "Cost vs Legal Risk"
    COST_VS_TECHNICAL       = "Cost vs Technical Fit"
    TECH_VS_COMPLIANCE      = "Technical Fit vs Compliance"
    TECH_VS_LEGAL           = "Technical Fit vs Legal Risk"
    LEGAL_VS_COMPLIANCE     = "Legal Risk vs Compliance"


class ConflictStatus(str, Enum):
    OPEN                    = "open"
    RESOLVED                = "resolved"
    ESCALATED_TO_PROCUREMENT = "escalated_to_procurement"


class AgentEvaluation(BaseModel):
    score: int                        # 0–100
    verdict: Verdict
    note: str


class DiscussionMessage(BaseModel):
    agent: str
    message: str
    timestamp: str


class ConflictDetail(BaseModel):
    exists: bool = False
    type: Optional[ConflictType] = None
    severity: Optional[str] = None    # "low" | "medium" | "high"
    description: Optional[str] = None
    involved_agents: List[str] = []
    discussion: List[DiscussionMessage] = []
    status: Optional[ConflictStatus] = None


class FinalRecommendation(BaseModel):
    ranked_vendors: List[str]
    justifications: Dict[str, str]
    selected_vendor: str


class WorkflowStatus(BaseModel):
    workflow_id: str
    vendor_name: str
    workflow_stage: WorkflowStage
    overall_status: str
    agent_evaluations: Dict[str, Optional[AgentEvaluation]]
    conflict: ConflictDetail
    final_recommendation: Optional[FinalRecommendation]
    last_updated: str
    audit_log: List[str] = []


# Submitted by agents via POST /api/submit-evaluation
class EvaluationSubmission(BaseModel):
    workflow_id: str
    agent_name: str   # "financial_agent" | "security_agent" | "legal_agent" | "technical_agent"
    score: int
    verdict: Verdict
    note: str


# ===========================================================================
# In-memory store
# ===========================================================================

ACTIVE_WORKFLOWS: Dict[str, WorkflowStatus] = {}

AGENT_DOMAIN_MAP = {
    "financial_agent": "Cost",
    "technical_agent": "Technical Fit",
    "legal_agent":     "Legal Risk",
    "security_agent":  "Compliance",
}

CONFLICT_TYPE_MAP = {
    frozenset(["financial_agent", "security_agent"]): ConflictType.COST_VS_COMPLIANCE,
    frozenset(["financial_agent", "legal_agent"]):    ConflictType.COST_VS_LEGAL,
    frozenset(["financial_agent", "technical_agent"]): ConflictType.COST_VS_TECHNICAL,
    frozenset(["technical_agent", "security_agent"]): ConflictType.TECH_VS_COMPLIANCE,
    frozenset(["technical_agent", "legal_agent"]):    ConflictType.TECH_VS_LEGAL,
    frozenset(["legal_agent", "security_agent"]):     ConflictType.LEGAL_VS_COMPLIANCE,
}

# ===========================================================================
# Helpers
# ===========================================================================

def _log(workflow: WorkflowStatus, msg: str):
    entry = f"[{datetime.now().isoformat()}] {msg}"
    workflow.audit_log.append(entry)
    print(entry)


def _detect_conflict(workflow: WorkflowStatus) -> Optional[ConflictDetail]:
    """
    Conflict rule: at least one agent 'rejected' while at least one other 'approved'.
    Severity: score gap >= 50 → high, 25-49 → medium, < 25 → low.
    """
    evals = {k: v for k, v in workflow.agent_evaluations.items() if v is not None}
    approved = [k for k, v in evals.items() if v.verdict == Verdict.APPROVED]
    rejected = [k for k, v in evals.items() if v.verdict == Verdict.REJECTED]

    if not approved or not rejected:
        return None

    # Build list of conflicting pairs
    conflict_types = []
    involved = set()
    max_gap = 0

    for a in approved:
        for r in rejected:
            pair = frozenset([a, r])
            ctype = CONFLICT_TYPE_MAP.get(pair)
            if ctype:
                conflict_types.append(ctype)
            involved.update([a, r])
            gap = abs(evals[a].score - evals[r].score)
            max_gap = max(max_gap, gap)

    severity = "high" if max_gap >= 50 else "medium" if max_gap >= 25 else "low"

    return ConflictDetail(
        exists=True,
        type=conflict_types[0] if conflict_types else None,
        severity=severity,
        description=f"Conflicting verdicts between {', '.join(involved)}.",
        involved_agents=list(involved),
        discussion=[],
        status=ConflictStatus.OPEN,
    )


# ===========================================================================
# MOCK data  (used when MOCK_MODE=true)
# ===========================================================================

MOCK_EVALUATIONS = {
    "financial_agent": AgentEvaluation(score=95, verdict=Verdict.APPROVED,
        note="Lowest TCO among all vendors."),
    "security_agent":  AgentEvaluation(score=40, verdict=Verdict.REJECTED,
        note="Fails data residency requirements under the Data Privacy Act."),
    "legal_agent":     AgentEvaluation(score=82, verdict=Verdict.APPROVED,
        note="Acceptable contractual risk; SLA terms are standard."),
    "technical_agent": AgentEvaluation(score=90, verdict=Verdict.APPROVED,
        note="Strong integration support and modern API surface."),
}

MOCK_DISCUSSION = [
    DiscussionMessage(agent="financial_agent",
        message="Vendor A offers 30% lower TCO than alternatives.",
        timestamp=datetime.now().isoformat()),
    DiscussionMessage(agent="security_agent",
        message="Vendor A does not meet data residency requirements under the Data Privacy Act.",
        timestamp=datetime.now().isoformat()),
    DiscussionMessage(agent="chief_procurement_agent",
        message="Given regulatory exposure, compliance risk outweighs cost savings. Recommend de-prioritizing Vendor A.",
        timestamp=datetime.now().isoformat()),
]

MOCK_FINAL = FinalRecommendation(
    ranked_vendors=["Vendor C", "Vendor B", "Vendor A"],
    justifications={
        "Vendor C": "Balanced cost and compliance — no major red flags across all domains.",
        "Vendor B": "Strong compliance posture; cost flagged as high but acceptable.",
        "Vendor A": "De-prioritized: Security rejection on data residency outweighs cost advantage.",
    },
    selected_vendor="Vendor C",
)


async def _run_mock_workflow(workflow_id: str):
    """Simulates the full workflow in stages with delays so the frontend sees live updates."""
    wf = ACTIVE_WORKFLOWS[workflow_id]

    # Stage 1 — evaluation (agents trickle in)
    await asyncio.sleep(2)
    wf.workflow_stage = WorkflowStage.EVALUATION
    wf.last_updated = datetime.now().isoformat()
    _log(wf, "Stage: evaluation")

    agent_order = ["financial_agent", "technical_agent", "legal_agent", "security_agent"]
    for agent in agent_order:
        await asyncio.sleep(2)
        wf.agent_evaluations[agent] = MOCK_EVALUATIONS[agent]
        wf.last_updated = datetime.now().isoformat()
        _log(wf, f"Evaluation received: {agent} → {MOCK_EVALUATIONS[agent].verdict}")

    # Stage 2 — conflict check
    await asyncio.sleep(1)
    wf.workflow_stage = WorkflowStage.CONFLICT_CHECK
    wf.last_updated = datetime.now().isoformat()
    _log(wf, "Stage: conflict_check")

    conflict = _detect_conflict(wf)
    if conflict:
        wf.conflict = conflict
        wf.overall_status = "conflict_detected"
        _log(wf, f"Conflict detected: {conflict.type} (severity={conflict.severity})")

        # Stage 3 — stakeholder alignment (debate)
        await asyncio.sleep(1)
        wf.workflow_stage = WorkflowStage.STAKEHOLDER_ALIGN
        wf.last_updated = datetime.now().isoformat()
        _log(wf, "Stage: stakeholder_alignment — agents debating")

        for msg in MOCK_DISCUSSION:
            await asyncio.sleep(2)
            wf.conflict.discussion.append(msg)
            wf.last_updated = datetime.now().isoformat()
            _log(wf, f"Discussion: [{msg.agent}] {msg.message[:60]}...")

        wf.conflict.status = ConflictStatus.ESCALATED_TO_PROCUREMENT
        wf.workflow_stage = WorkflowStage.ESCALATED
        wf.overall_status = "escalated_to_procurement"
        wf.last_updated = datetime.now().isoformat()
        _log(wf, "Conflict escalated to human reviewer")

    # Stage 4 — decision (final recommendation)
    await asyncio.sleep(2)
    wf.workflow_stage = WorkflowStage.DECISION
    wf.final_recommendation = MOCK_FINAL
    wf.overall_status = "complete"
    wf.last_updated = datetime.now().isoformat()
    _log(wf, f"Final decision: {MOCK_FINAL.selected_vendor}")

    wf.workflow_stage = WorkflowStage.COMPLETE
    wf.last_updated = datetime.now().isoformat()
    _log(wf, "Workflow complete")


# ===========================================================================
# REAL Band polling (used when MOCK_MODE=false)
# ===========================================================================

async def _poll_band_room(workflow_id: str, chat_id: str):
    wf = ACTIVE_WORKFLOWS[workflow_id]
    max_attempts = 40

    for attempt in range(max_attempts):
        await asyncio.sleep(3)
        try:
            messages_data = await get_chat_messages(chat_id)
            messages = messages_data.get("data", []) if isinstance(messages_data, dict) else []

            seen_agents = {e["agent_name"] for e in []}  # track what we've parsed

            for msg in messages:
                sender_name = msg.get("sender", {}).get("name", "")
                content = msg.get("content", "{}")

                agent_key = None
                if sender_name == "FinanceAgent":    agent_key = "financial_agent"
                elif sender_name == "SecurityAgent": agent_key = "security_agent"
                elif sender_name == "LegalAgent":    agent_key = "legal_agent"
                elif sender_name == "TechAgent":     agent_key = "technical_agent"

                if agent_key and wf.agent_evaluations.get(agent_key) is None:
                    try:
                        clean = content.strip().strip("`").removeprefix("json\n")
                        data = json.loads(clean)
                        wf.agent_evaluations[agent_key] = AgentEvaluation(
                            score=data["score"],
                            verdict=Verdict(data["verdict"]),
                            note=data.get("note", data.get("comment", "")),
                        )
                        wf.last_updated = datetime.now().isoformat()
                        _log(wf, f"Parsed Band message: {agent_key}")
                    except Exception as e:
                        _log(wf, f"Failed to parse {sender_name}: {e}")

            # Check if all 4 agents have responded
            all_done = all(wf.agent_evaluations.get(k) is not None
                           for k in AGENT_DOMAIN_MAP)
            if all_done:
                conflict = _detect_conflict(wf)
                if conflict:
                    wf.conflict = conflict
                    wf.overall_status = "conflict_detected"
                    wf.workflow_stage = WorkflowStage.STAKEHOLDER_ALIGN
                    _log(wf, "All agents responded — conflict detected")
                else:
                    wf.overall_status = "complete"
                    wf.workflow_stage = WorkflowStage.DECISION
                    _log(wf, "All agents responded — no conflict")
                wf.last_updated = datetime.now().isoformat()
                break

            _log(wf, f"Waiting for agents ({attempt + 1}/{max_attempts})")

        except Exception as e:
            _log(wf, f"Polling error: {e}")

    else:
        wf.overall_status = "timed_out"
        wf.last_updated = datetime.now().isoformat()
        _log(wf, "Workflow timed out waiting for agents")


# ===========================================================================
# Routes
# ===========================================================================

@app.get("/api/workflow-status/{workflow_id}", response_model=WorkflowStatus)
async def get_workflow_status(workflow_id: str):
    wf = ACTIVE_WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@app.get("/api/workflows")
async def list_workflows():
    """List all active workflows — useful for the dashboard overview."""
    return [
        {"workflow_id": wid, "vendor_name": wf.vendor_name,
         "overall_status": wf.overall_status, "workflow_stage": wf.workflow_stage}
        for wid, wf in ACTIVE_WORKFLOWS.items()
    ]


@app.post("/api/start-evaluation")
async def start_evaluation(vendor_name: str, background_tasks: BackgroundTasks):
    """
    Kick off a vendor evaluation workflow.
    In MOCK_MODE the whole thing runs locally with fake data.
    In real mode it creates a Band room and waits for agents.
    """
    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"

    wf = WorkflowStatus(
        workflow_id=workflow_id,
        vendor_name=vendor_name,
        workflow_stage=WorkflowStage.INTAKE,
        overall_status="started",
        agent_evaluations={k: None for k in AGENT_DOMAIN_MAP},
        conflict=ConflictDetail(),
        final_recommendation=None,
        last_updated=datetime.now().isoformat(),
        audit_log=[],
    )
    ACTIVE_WORKFLOWS[workflow_id] = wf
    _log(wf, f"Workflow created for vendor: {vendor_name} (mock={MOCK_MODE})")

    if MOCK_MODE:
        background_tasks.add_task(_run_mock_workflow, workflow_id)
        return {"workflow_id": workflow_id, "mode": "mock", "status": "started"}

    # Real Band path
    try:
        chat_id = await create_evaluation_room(vendor_name)
        _log(wf, f"Band room created: {chat_id}")

        await asyncio.gather(
            add_participant(chat_id, "@your-org/finance-agent"),
            add_participant(chat_id, "@your-org/security-agent"),
            add_participant(chat_id, "@your-org/legal-agent"),
            add_participant(chat_id, "@your-org/technical-agent"),
        )
        await trigger_workflow(chat_id, vendor_name)
        wf.workflow_stage = WorkflowStage.EVALUATION
        wf.last_updated = datetime.now().isoformat()

        background_tasks.add_task(_poll_band_room, workflow_id, chat_id)
        return {"workflow_id": workflow_id, "chat_id": chat_id, "mode": "live", "status": "started"}

    except Exception as e:
        _log(wf, f"Band setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit-evaluation")
async def submit_evaluation(submission: EvaluationSubmission):
    """
    Agents POST their results here directly (alternative to Band polling).
    Person 3 & 4 can use this endpoint while Band integration is being wired up.
    """
    wf = ACTIVE_WORKFLOWS.get(submission.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if submission.agent_name not in AGENT_DOMAIN_MAP:
        raise HTTPException(status_code=400,
            detail=f"Unknown agent. Must be one of: {list(AGENT_DOMAIN_MAP.keys())}")

    wf.agent_evaluations[submission.agent_name] = AgentEvaluation(
        score=submission.score,
        verdict=submission.verdict,
        note=submission.note,
    )
    wf.workflow_stage = WorkflowStage.EVALUATION
    wf.last_updated = datetime.now().isoformat()
    _log(wf, f"Direct submission: {submission.agent_name} → {submission.verdict} ({submission.score})")

    # Auto-detect conflict once all 4 are in
    all_done = all(wf.agent_evaluations.get(k) is not None for k in AGENT_DOMAIN_MAP)
    if all_done:
        wf.workflow_stage = WorkflowStage.CONFLICT_CHECK
        conflict = _detect_conflict(wf)
        if conflict:
            wf.conflict = conflict
            wf.overall_status = "conflict_detected"
            wf.workflow_stage = WorkflowStage.STAKEHOLDER_ALIGN
            _log(wf, f"Auto-conflict detected: {conflict.type}")
        else:
            wf.overall_status = "awaiting_decision"
            wf.workflow_stage = WorkflowStage.DECISION
            _log(wf, "All evaluations in — no conflict")

    return {"status": "ok", "workflow_stage": wf.workflow_stage}


@app.post("/api/resolve-conflict/{workflow_id}")
async def resolve_conflict(workflow_id: str, resolution: str = "escalated_to_procurement"):
    """Human reviewer resolves or escalates a conflict."""
    wf = ACTIVE_WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not wf.conflict.exists:
        raise HTTPException(status_code=400, detail="No conflict to resolve")

    wf.conflict.status = ConflictStatus(resolution)
    wf.workflow_stage = WorkflowStage.ESCALATED if resolution == "escalated_to_procurement" \
                        else WorkflowStage.DECISION
    wf.overall_status = resolution
    wf.last_updated = datetime.now().isoformat()
    _log(wf, f"Conflict resolved by human: {resolution}")
    return {"status": "ok"}


@app.post("/api/set-final-recommendation/{workflow_id}")
async def set_final_recommendation(workflow_id: str, recommendation: FinalRecommendation):
    """Chief Procurement Agent POSTs the final ranked vendor list here."""
    wf = ACTIVE_WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf.final_recommendation = recommendation
    wf.workflow_stage = WorkflowStage.COMPLETE
    wf.overall_status = "complete"
    wf.last_updated = datetime.now().isoformat()
    _log(wf, f"Final recommendation set: {recommendation.selected_vendor}")
    return {"status": "ok"}


@app.get("/api/mock-schema")
async def get_mock_schema():
    """
    Returns the full agreed schema with sample data.
    Share this URL with teammates so they know exactly what to build against.
    """
    return {
        "workflow_id": "wf-abc12345",
        "vendor_name": "CloudSecure Inc.",
        "workflow_stage": "stakeholder_alignment",
        "overall_status": "conflict_detected",
        "agent_evaluations": {
            "financial_agent": {"score": 95, "verdict": "approved",
                                "note": "Lowest TCO among all vendors."},
            "security_agent":  {"score": 40, "verdict": "rejected",
                                "note": "Fails data residency requirements."},
            "legal_agent":     {"score": 82, "verdict": "approved",
                                "note": "Acceptable contractual risk."},
            "technical_agent": {"score": 90, "verdict": "approved",
                                "note": "Strong integration support."},
        },
        "conflict": {
            "exists": True,
            "type": "Cost vs Compliance",
            "severity": "high",
            "description": "Financial approval conflicts with Security rejection.",
            "involved_agents": ["financial_agent", "security_agent"],
            "discussion": [
                {"agent": "financial_agent",
                 "message": "Vendor A offers 30% lower TCO than alternatives.",
                 "timestamp": "2026-06-14T10:00:00"},
                {"agent": "security_agent",
                 "message": "Vendor A does not meet data residency requirements.",
                 "timestamp": "2026-06-14T10:00:05"},
                {"agent": "chief_procurement_agent",
                 "message": "Given regulatory exposure, compliance risk outweighs cost savings.",
                 "timestamp": "2026-06-14T10:00:10"},
            ],
            "status": "escalated_to_procurement",
        },
        "final_recommendation": None,
        "last_updated": "2026-06-14T10:00:10",
        "audit_log": [
            "[2026-06-14T10:00:00] Workflow created for vendor: CloudSecure Inc.",
            "[2026-06-14T10:00:01] Stage: evaluation",
            "[2026-06-14T10:00:02] Evaluation received: financial_agent → approved",
            "[2026-06-14T10:00:03] Evaluation received: security_agent → rejected",
            "[2026-06-14T10:00:04] Conflict detected: Cost vs Compliance (severity=high)",
            "[2026-06-14T10:00:05] Stage: stakeholder_alignment — agents debating",
            "[2026-06-14T10:00:10] Conflict escalated to human reviewer",
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "mock_mode": MOCK_MODE, "active_workflows": len(ACTIVE_WORKFLOWS)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)