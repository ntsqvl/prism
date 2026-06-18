# New Endpoints Guide — Role 2 Additions

## Overview

Two new endpoints have been added to support:
1. **Document upload** — For vendor contracts/documents (Person 1 integration)
2. **Evaluation retry** — For re-triggering agent assessments

---

## 1. Upload Vendor Document

**Purpose:** Upload vendor contracts/documents for vectorization by the vector database.

### Endpoint
```
POST /api/upload-vendor-document/{workflow_id}
```

### Parameters
- `workflow_id` (path) — The evaluation workflow ID
- `file` (form data) — The document file (PDF, TXT, or DOCX)

### Supported File Types
- `.pdf` — PDF documents
- `.txt` — Text files
- `.docx` — Word documents

### Example Usage

```bash
# Using curl
curl -X POST "http://localhost:8000/api/upload-vendor-document/wf-68dd3e54" \
  -F "file=@contract.pdf"

# Using Python requests
import requests

with open("contract.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(
        "http://localhost:8000/api/upload-vendor-document/wf-68dd3e54",
        files=files
    )
    print(response.json())
```

### Response (Success)
```json
{
  "status": "ok",
  "filename": "contract.pdf",
  "stored_path": "vendor_documents/wf-68dd3e54_abc12def.pdf",
  "message": "Document uploaded successfully. Notify Role 1 to vectorize."
}
```

### Response (Error — Invalid File Type)
```json
{
  "detail": "Unsupported file type. Allowed: {'.pdf', '.txt', '.docx'}"
}
```

### What Happens Behind the Scenes
1. File is validated (extension check)
2. Saved locally to `./vendor_documents/` with unique filename
3. Metadata stored (filename, path, size, timestamp)
4. Logged to workflow's audit trail
5. **Role 1** can now call `/api/vendor-documents/{workflow_id}` to fetch and vectorize

---

## 2. Fetch Uploaded Documents

**Purpose:** Role 1 uses this to retrieve all uploaded documents for a workflow for vectorization.

### Endpoint
```
GET /api/vendor-documents/{workflow_id}
```

### Example Usage

```bash
curl http://localhost:8000/api/vendor-documents/wf-68dd3e54 | jq .
```

### Response
```json
{
  "workflow_id": "wf-68dd3e54",
  "vendor_name": "CloudSecure Inc.",
  "documents": [
    {
      "filename": "contract.pdf",
      "stored_path": "vendor_documents/wf-68dd3e54_abc12def.pdf",
      "uploaded_at": "2026-06-18T11:25:52.310630",
      "size_bytes": 245678
    },
    {
      "filename": "compliance_report.txt",
      "stored_path": "vendor_documents/wf-68dd3e54_def34ghi.txt",
      "uploaded_at": "2026-06-18T11:26:15.412891",
      "size_bytes": 52100
    }
  ],
  "message": "Pass stored_path to your vectorization pipeline."
}
```

---

## 3. Retry Agent Evaluation

**Purpose:** Reset an agent's evaluation to allow them to re-evaluate based on new information or corrections.

### Endpoint
```
POST /api/retry-evaluation/{workflow_id}/{agent_name}
```

### Parameters
- `workflow_id` (path) — The evaluation workflow ID
- `agent_name` (path) — One of: `financial_agent`, `technical_agent`, `legal_agent`, `security_agent`

### When to Use
- Agent detected an error in their evaluation
- New vendor information became available mid-review
- You need to reset conflict status and re-evaluate
- Manual correction flow

### Example Usage

```bash
# Reset financial_agent
curl -X POST "http://localhost:8000/api/retry-evaluation/wf-68dd3e54/financial_agent"

# Reset security_agent
curl -X POST "http://localhost:8000/api/retry-evaluation/wf-68dd3e54/security_agent"
```

### Response (Success)
```json
{
  "status": "ok",
  "agent_name": "financial_agent",
  "message": "Evaluation reset. financial_agent should re-submit."
}
```

### Response (Error — Agent Not Found)
```json
{
  "detail": "Workflow not found"
}
```

### Response (Error — Agent Hasn't Evaluated Yet)
```json
{
  "detail": "financial_agent has not evaluated yet"
}
```

### What Happens Behind the Scenes
1. Agent's evaluation is cleared (set to `null`)
2. Conflict is cleared (will be re-detected when all 4 agents are back)
3. Workflow reverts to `evaluation` stage
4. Log entry added to audit trail
5. **Agent should re-submit their evaluation** via `POST /api/submit-evaluation`

### Workflow State After Retry

Before:
```
agent_evaluations: {
  financial_agent: { score: 95, verdict: "approved", note: "..." },
  security_agent: { score: 40, verdict: "rejected", note: "..." },
  ...
}
workflow_stage: conflict_check
overall_status: conflict_detected
```

After calling retry on `financial_agent`:
```
agent_evaluations: {
  financial_agent: null,  // ← Reset
  security_agent: { score: 40, verdict: "rejected", note: "..." },
  ...
}
workflow_stage: evaluation  // ← Back to evaluation
overall_status: evaluation_reset
conflict: ConflictDetail()  // ← Cleared
```

---

## Integration Guide for Each Role

### Role 1 (Vector DB / Person 1)
```
1. Frontend → POST /api/upload-vendor-document/{workflow_id}
2. Your service → GET /api/vendor-documents/{workflow_id}
3. Your service → Vectorize documents
4. Your service → Store in vector DB (Pinecone/Weaviate)
5. Agents access context via RAG in their system prompts
```

### Role 5 (Frontend)
```
1. Add file upload UI in vendor evaluation modal
2. On file select → POST /api/upload-vendor-document/{workflow_id}
3. Show upload success/error toast
4. Optionally poll /api/vendor-documents/{workflow_id} to show "documents ready"
5. Add "Retry Evaluation" button for conflict resolution flows
6. On click → POST /api/retry-evaluation/{workflow_id}/{agent_name}
```

### Role 2 (You)
```
✅ Upload endpoint: Complete
✅ Retry endpoint: Complete
✅ Document fetch endpoint: Complete
- Monitor audit logs for document uploads
- Handle Band integration when agents are live (MOCK_MODE=false)
```

---

## Testing

Run the included test script:
```bash
bash test_new_endpoints.sh
```

This will:
1. Create a workflow
2. Upload a sample contract
3. Verify document storage
4. Test retry mechanism
5. Validate audit trail

Expected output: All tests pass ✅

---

## File Storage Details

Documents are stored in `./vendor_documents/` directory with format:
```
{workflow_id}_{random_hex}.{extension}
```

Example:
```
vendor_documents/
  wf-68dd3e54_f64ed7a1.txt
  wf-68dd3e54_abc12def.pdf
  wf-9a2b8c41_xyz99abc.docx
```

For production, you may want to:
- Replace local storage with S3/GCS
- Add expiration policies
- Implement virus scanning
- Add access control

---

## Audit Trail Integration

Both new endpoints log to the workflow's `audit_log`:

```
[2026-06-18T11:25:52.310630] Document uploaded: sample_contract.txt (150 bytes)
[2026-06-18T11:26:02.432064] Retry requested for financial_agent (was: Verdict.APPROVED)
```

These appear in:
- `GET /api/workflow-status/{workflow_id}` → `audit_log` field
- Console output (useful for debugging)

---

## Error Handling

| Scenario | Status | Message |
|----------|--------|---------|
| Workflow not found | 404 | "Workflow not found" |
| Invalid file type | 400 | "Unsupported file type. Allowed: ..." |
| Upload I/O error | 500 | "Upload failed: ..." |
| Agent not found | 400 | "Unknown agent. Must be one of: ..." |
| Agent hasn't evaluated | 400 | "{agent_name} has not evaluated yet" |

---

## Next Steps

1. **Role 1:** Integrate `GET /api/vendor-documents/{workflow_id}` into your vectorization pipeline
2. **Role 5:** Add upload UI to vendor modal + retry buttons to conflict view
3. **Testing:** Run `test_new_endpoints.sh` with your own PDFs
4. **Deployment:** Once ready, deploy to Railway/Render

---

## Questions?

Check the main README.md or the inline code comments in `main.py` for more context.
