# Autonomous Vendor Selection & Governance Platform
## System Documentation — Database Schema & Process Flow

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Database Tables — Function & Purpose](#database-tables)
   - [Reference Tables](#reference-tables)
   - [Configuration Tables](#configuration-tables)
   - [Runtime Tables](#runtime-tables)
   - [Agent Output Tables](#agent-output-tables)
3. [Full Process Flow — Input to Output](#full-process-flow)
   - [Stage 0: Enterprise Registration](#stage-0-enterprise-registration)
   - [Stage 1: Procurement Cycle Creation & Document Upload](#stage-1-procurement-cycle-creation--document-upload)
   - [Stage 2: Context Discovery](#stage-2-context-discovery)
   - [Stage 3: Regulation Detection & Checklist Assembly](#stage-3-regulation-detection--checklist-assembly)
   - [Stage 4: Parallel Agent Analysis](#stage-4-parallel-agent-analysis)
   - [Stage 5: Conflict Detection & Reconciliation](#stage-5-conflict-detection--reconciliation)
   - [Stage 6: Final Recommendation](#stage-6-final-recommendation)
4. [Table Relationship Map](#table-relationship-map)

---

## System Overview

The Autonomous Vendor Selection & Governance Platform evaluates software vendor proposals on behalf of enterprises. It ingests vendor-submitted PDF documents, discovers procurement context autonomously, applies applicable country and industry regulations, and produces a ranked vendor recommendation with full audit traceability.

**The only required user inputs are:**
- Company name, country, and industry (one-time registration)
- RFP title
- Vendor PDF documents

Everything else — regulatory context, document classification, compliance checking, scoring, conflict resolution, and final ranking — is performed autonomously by agents.

---

## Database Tables

The 21 tables are organized into four functional groups.

---

### Reference Tables

These tables are seeded once and rarely change. They represent the system's built-in knowledge about the world — software types, data sensitivity levels, regulations, and document types.

---

#### `software_category`

**Function:** Stores the three classification levels of software procurement — Operational Tool, Business System, and Mission Critical.

**How it is used:** The Context Discovery Agent writes to `cycle_context` referencing this table after determining what kind of software is being procured. It drives how deep each agent evaluates and which regulations apply.

| Code | Name | Example |
|---|---|---|
| OPERATIONAL | Operational Tool | Attendance system, payroll, scheduling |
| BUSINESS | Business System | CRM, ERP, document management |
| MISSION_CRITICAL | Mission Critical | Core banking, payment gateway, fraud detection |

---

#### `data_sensitivity`

**Function:** Stores the three levels of data classification — Internal, Customer PII, and Financial.

**How it is used:** Like `software_category`, this is referenced by `cycle_context` after the Context Discovery Agent reads vendor documents and determines what kind of data the system will handle. Higher sensitivity levels trigger stricter regulatory requirements.

| Code | Name | Example |
|---|---|---|
| INTERNAL | Internal Data Only | Employee records, schedules |
| CUSTOMER_PII | Customer Information | Names, contacts, customer profiles |
| FINANCIAL | Financial Data | Transactions, account balances, payments |

---

#### `regulation_framework`

**Function:** The self-building knowledge base of procurement regulations. Stores every known country and industry regulatory framework the system is aware of, including which type of software and data sensitivity it applies to.

**How it is used:** When a procurement cycle starts, the system queries this table using the enterprise's country and industry alongside the discovered software category and data sensitivity to automatically determine which regulations apply. If a country and industry combination is not yet in this table, the Context Discovery Agent queries an AI model to discover the applicable regulations and populates the table — so it only grows smarter over time.

| Column | Purpose |
|---|---|
| `country_code` | NULL means global standard (e.g., ISO 27001) |
| `industry_code` | NULL means applies to all industries |
| `software_category_code` | NULL means applies regardless of software type |
| `data_sensitivity_code` | NULL means applies regardless of data sensitivity |

---

#### `regulation_rule`

**Function:** Stores specific, plain-English rules per regulation per agent type. These are the actual instructions injected into agent prompts at runtime.

**How it is used:** When an agent is assembled for a cycle, the system queries this table for all rules matching the applicable regulations and the agent's type (financial, legal, security, technical). The results are appended to the agent's system prompt so it knows exactly what to check for this specific enterprise and procurement.

---

#### `document_type`

**Function:** Registry of all known document types the system can expect from vendors.

**How it is used:** Two ways. First, when vendors upload documents, the Context Discovery Agent classifies each file against this registry and updates `vendor_document.document_type_code`. Second, the system queries this table to build the baseline document checklist — any row where `is_baseline = TRUE` is always expected from every vendor regardless of regulation or policy.

| `is_baseline` | Meaning |
|---|---|
| TRUE | Always required — Technical Proposal, Pricing Schedule, Company Profile, References |
| FALSE | Required only when triggered by regulation or policy |

---

#### `regulation_document_requirement`

**Function:** Maps which document types each regulation requires vendors to submit.

**How it is used:** Part of the document checklist query. When a PH banking enterprise runs a cycle that triggers `BSP_CIRCULAR_982`, this table tells the system that a `SECURITY_QUESTIONNAIRE` and `DATA_RESIDENCY_DECL` are mandatory for that regulation — and that missing either one results in disqualification.

---

### Configuration Tables

These tables hold enterprise-specific settings. Most are populated automatically by the system at registration or cycle creation. The enterprise user does not manually configure these.

---

#### `enterprise`

**Function:** One row per company using the platform.

**How it is used:** The top of the data hierarchy. Every procurement cycle, vendor, and agent finding traces back to an enterprise row. At registration, the system reads `country_code` and `industry_code` to auto-detect applicable regulations.

---

#### `enterprise_regulation`

**Function:** Links an enterprise to the regulations that apply to them.

**How it is used:** Auto-populated by the system at registration — the enterprise never manually configures this. When a new enterprise registers as a Philippine bank, the system queries `regulation_framework` and inserts matching rows here automatically. The `added_by` column records whether it was system-detected, agent-discovered, or admin-added manually.

---

#### `procurement_policy`

**Function:** Stores an enterprise's own internally written procurement policy, uploaded as a PDF.

**How it is used:** Optional. If an enterprise uploads their procurement policy, the raw extracted text is stored here. The Policy Parser Agent reads `raw_text` and populates the three policy sub-tables below. If no policy is uploaded, the system still works using baseline and regulation-driven rules only.

---

#### `policy_document_requirement`

**Function:** Additional document requirements extracted from the enterprise's own procurement policy — beyond what regulations already mandate.

**How it is used:** Stacks on top of baseline and regulation document requirements when building the vendor checklist. Supports conditional requirements via `contract_value_threshold` — for example, audited financial statements only required for contracts above PHP 10 million.

---

#### `policy_evaluation_rule`

**Function:** Additional agent evaluation rules extracted from the enterprise's procurement policy.

**How it is used:** Appended to agent prompts alongside regulation rules. For example, a policy rule like "Flag any vendor whose payment terms exceed 60 days" gets injected into the Financial Agent's prompt for every cycle that enterprise runs.

---

#### `policy_weight_config`

**Function:** Stores how much weight each agent's score carries in the final vendor ranking for this enterprise.

**How it is used:** Read by the Chief Procurement Agent when calculating final scores. A banking enterprise might weight security at 40% while a logistics company weights financial at 40%. Defaults to equal 25% per agent if no policy is uploaded.

---

### Runtime Tables

These tables are created and updated during an active procurement cycle.

---

#### `procurement_cycle`

**Function:** One row per RFP process an enterprise runs.

**How it is used:** The parent container for everything in one procurement run. All vendors, documents, findings, conflicts, and the final recommendation reference a `cycle_id`. The user creates this row by entering an RFP title and uploading documents. Everything else is derived.

---

#### `cycle_context`

**Function:** Stores what the Context Discovery Agent learned about the procurement by reading the uploaded documents. Replaces any need for the user to manually classify the procurement.

**How it is used:** Written by the Context Discovery Agent before any specialist agent runs. Contains the discovered software type, data sensitivity level, estimated contract value, and the agent's confidence in its conclusions. If `confidence_score` is below 0.80, `requires_confirmation` is set to TRUE and the user is shown a one-click confirmation screen. Above 0.80, the system proceeds fully automatically.

| Column | Purpose |
|---|---|
| `software_type` | Human-readable description, e.g., "HR Management System" |
| `software_category_code` | Structured classification for regulation queries |
| `data_sensitivity_code` | Drives which privacy and security regulations apply |
| `estimated_contract_value` | Extracted from pricing documents, triggers policy thresholds |
| `evidence_sources` | JSONB log of which document and page led to each conclusion |
| `confidence_score` | 0.0 to 1.0 — below 0.80 triggers user confirmation |

---

#### `vendor`

**Function:** One row per vendor participating in a cycle.

**How it is used:** Tracks each vendor's submission status and completeness. `completeness_score` is calculated after the system checks submitted documents against the required checklist. A vendor at 75% means one required document is missing. `submission_status` flips to `disqualified` automatically if a dealbreaker document is absent.

---

#### `vendor_document`

**Function:** One row per uploaded PDF per vendor.

**How it is used:** This is the ingestion pipeline's primary table. When a vendor's documents are uploaded, each file gets a row here. `extraction_status` tracks the pipeline state from `pending` through `extracted` or `ocr_required` to `failed`. The Context Discovery Agent updates `document_type_code` after classifying each document.

| `extraction_status` | Meaning |
|---|---|
| pending | Uploaded, not yet processed |
| extracted | Text successfully extracted, ready for agents |
| ocr_required | Scanned PDF, needs OCR before extraction |
| failed | Extraction failed, needs manual attention |

---

#### `document_chunk`

**Function:** The extracted text of each document broken into smaller pieces with metadata about where each piece came from.

**How it is used:** Instead of agents reading entire 100-page documents (expensive and hitting context limits), agents retrieve only relevant chunks. The Legal Agent queries for chunks containing "termination," "liability," and "indemnification" — receiving 5 to 10 relevant pages instead of 100. When an agent writes a finding, it references `evidence_chunk_id` so the audit trail can point to the exact page in the source document.

---

### Agent Output Tables

These tables are written by agents during and after the evaluation pipeline.

---

#### `agent_finding`

**Function:** Every specific finding any agent produces, per vendor. The richest and most important table in the system.

**How it is used:** Each specialist agent writes one or more rows here after analyzing a vendor. Contains the normalized score, severity classification, plain-English summary, evidence quote, and source page reference. The Chief Procurement Agent reads all findings across all vendors to produce the final ranking. The audit trail reads from here to answer "why did the system rank Vendor B above Vendor A."

| Column | Purpose |
|---|---|
| `agent_type` | financial / legal / security / technical / context_discovery |
| `dimension` | The specific aspect evaluated — TCO, data_residency, termination_clause |
| `regulation_code` | Which regulation triggered this finding (NULL if baseline check) |
| `score` | 0 to 100 normalized score for this dimension |
| `severity` | low / medium / high / critical |
| `is_dealbreaker` | TRUE causes automatic disqualification regardless of other scores |
| `evidence_chunk_id` | Links to exact chunk in source document |

---

#### `agent_conflict`

**Function:** Cases where two agents produced contradictory assessments of the same vendor.

**How it is used:** Band detects conflicts by comparing findings across agents for the same vendor — specifically when one agent scores high and another raises a dealbreaker flag for the same vendor. This is the core multi-agent value: a vendor that looks financially optimal but fails security compliance is caught here rather than passing through. The Chief Procurement Agent addresses each conflict explicitly in the recommendation.

**Example conflict:** Financial Agent ranks Vendor A first for cost. Security Agent flags Vendor A for missing data residency declaration — a dealbreaker under BSP Circular 982. Band stores this conflict and routes it to the Chief Procurement Agent for resolution.

---

#### `recommendation`

**Function:** The final output of the entire evaluation cycle. One row per completed procurement cycle.

**How it is used:** Written by the Chief Procurement Agent after receiving all findings and resolved conflicts. Contains the ranked vendor list with scores and justifications, an executive summary in plain language, trade-off notes explaining ranking decisions, and a confidence score. If `confidence_score` falls below the threshold or `requires_escalation` is TRUE, Band routes the full decision package to a human procurement lead for review before finalization.

| Column | Purpose |
|---|---|
| `vendor_ranking` | JSONB ordered list of vendors with scores and justifications |
| `executive_summary` | Plain-language explanation for non-technical decision makers |
| `tradeoff_notes` | Explicit notes on conflicts — "Vendor A cheapest but disqualified for BSP non-compliance" |
| `confidence_score` | System's overall confidence in the recommendation |
| `requires_escalation` | TRUE triggers human review before the recommendation is released |

---

#### `audit_log`

**Function:** An append-only timestamped record of every significant event in the system. Never updated — only inserted.

**How it is used:** Three purposes. First, transparency — the procurement team can replay exactly what happened and why. Second, regulatory compliance — regulated enterprises (banks especially) must prove their vendor selection process was auditable and traceable to satisfy BSP, DPA, and other regulatory requirements. Third, debugging — during development, if an agent produces a wrong output, the audit log shows exactly what input it received and what it produced.

| `event_type` values | Meaning |
|---|---|
| document_ingested | A vendor PDF was uploaded and extracted |
| agent_started | A specialist agent began evaluating a vendor |
| agent_completed | A specialist agent finished and wrote findings |
| context_discovered | Context Discovery Agent completed classification |
| conflict_detected | Band identified a cross-agent contradiction |
| conflict_resolved | Chief Procurement Agent resolved a conflict |
| escalated | Confidence threshold not met, routed to human |
| recommendation_generated | Final ranked output was produced |
| user_confirmed | User confirmed context discovery classification |

---

## Full Process Flow

### What the user inputs:
1. Company name, country, and industry (one-time at registration)
2. RFP title (one field)
3. Vendor PDF documents (upload)

### What the system does with that:

---

### Stage 0: Enterprise Registration

**User input:** Company name, country, industry

**System actions:**
1. Creates a row in `enterprise`
2. Queries `regulation_framework` using `country_code` and `industry_code`
3. If matching regulations exist in the table, inserts them into `enterprise_regulation` automatically
4. If no matching regulations exist (new country or industry combo), the Context Discovery Agent queries an AI model to discover applicable frameworks, populates `regulation_framework` and `regulation_rule`, then links them to the enterprise via `enterprise_regulation`
5. If enterprise uploads a procurement policy PDF, the Policy Parser Agent reads it and populates `procurement_policy`, `policy_document_requirement`, `policy_evaluation_rule`, and `policy_weight_config`

**Tables written:** `enterprise`, `enterprise_regulation`, `regulation_framework` (if new), `regulation_rule` (if new), `procurement_policy` (if uploaded), `policy_*` tables

---

### Stage 1: Procurement Cycle Creation & Document Upload

**User input:** RFP title, vendor PDF documents

**System actions:**
1. Creates a row in `procurement_cycle` with the RFP title linked to the enterprise
2. For each vendor, creates a row in `vendor`
3. For each uploaded PDF, creates a row in `vendor_document` with `extraction_status = pending`
4. Ingestion pipeline runs on each document:
   - If text-extractable: direct PDF to text extraction
   - If scanned or image-based: OCR first, then text extraction
   - Updates `vendor_document.extracted_text` and sets `extraction_status = extracted`
5. Text is chunked into sections with page and heading metadata, written to `document_chunk`
6. Writes `document_ingested` events to `audit_log` for each file processed

**Tables written:** `procurement_cycle`, `vendor`, `vendor_document`, `document_chunk`, `audit_log`

---

### Stage 2: Context Discovery

**Agent:** Context Discovery Agent

**What triggers it:** All vendor documents have been ingested and chunked

**What the agent does:** Reads a representative sample of chunks from across all vendor documents and determines:
- What kind of software is being procured
- What data the system will handle
- What regulations are likely applicable based on document contents
- What document types were submitted by each vendor
- Approximate contract value range from pricing documents

**System actions:**
1. Assembles a prompt containing sample chunks from all vendor documents
2. Context Discovery Agent returns structured JSON with classifications and evidence citations
3. System writes results to `cycle_context`
4. Updates `vendor_document.document_type_code` for each classified document
5. If `confidence_score >= 0.80`, proceeds automatically
6. If `confidence_score < 0.80`, sets `requires_confirmation = TRUE` and shows user a one-click confirmation screen

**Tables written:** `cycle_context`, `vendor_document` (document_type_code updated), `agent_finding` (context_discovery type), `audit_log`

---

### Stage 3: Regulation Detection & Checklist Assembly

**What triggers it:** `cycle_context` is written and confirmed (automatically or by user)

**System actions:**

**Regulation detection query:**
```
Applicable regulations =
  enterprise's country + industry (from enterprise_regulation)
  filtered by discovered software_category and data_sensitivity
  from cycle_context
```

**Document checklist assembly query:**
```
Required documents =
  Baseline documents (is_baseline = TRUE from document_type)
  + Regulation-required documents (from regulation_document_requirement
    for all applicable regulations)
  + Policy-required documents (from policy_document_requirement
    where contract_value threshold is met)
```

**Completeness check:**
- System compares required documents against submitted `vendor_document` rows
- Calculates `vendor.completeness_score` as a percentage
- Vendors missing dealbreaker documents are flagged as `disqualified`
- Vendors missing non-dealbreaker documents are flagged as `incomplete` but continue in evaluation

**Tables read:** `enterprise_regulation`, `regulation_framework`, `cycle_context`, `document_type`, `regulation_document_requirement`, `policy_document_requirement`, `vendor_document`

**Tables written:** `vendor` (completeness_score, submission_status updated), `audit_log`

---

### Stage 4: Parallel Agent Analysis

**What triggers it:** Document checklist is assembled and vendor completeness is assessed

**Agents run in parallel for each vendor:**

**Financial Analysis Agent (The CFO Advisor)**
- Retrieves chunks from `PRICING_SCHEDULE` and `TECH_PROPOSAL` documents
- Prompt injected with: baseline financial evaluation instructions + regulation rules for financial agent + policy evaluation rules for financial agent
- Evaluates: pricing structure, hidden fees, implementation costs, TCO, payment terms
- Writes one `agent_finding` row per dimension evaluated per vendor

**Legal Risk Agent (The Corporate Counsel)**
- Retrieves chunks from `CONTRACT` and `SLA_DRAFT` documents
- Prompt injected with: baseline legal instructions + regulation rules for legal agent (DPA clauses, BSP audit rights, GDPR requirements if applicable) + policy rules
- Evaluates: liability clauses, termination terms, indemnification, SLA adequacy, governing law
- Writes one `agent_finding` row per dimension per vendor

**Security & Compliance Agent (The CISO)**
- Retrieves chunks from `SECURITY_QUESTIONNAIRE`, `DPA_AGREEMENT`, `PENTEST_REPORT`, `ISO_CERTIFICATE`
- Prompt injected with: baseline security instructions + regulation rules for security agent (BSP data residency, ISO 27001, PCI-DSS if applicable) + policy rules
- Evaluates: cybersecurity controls, data residency, privacy commitments, regulatory certifications
- Writes one `agent_finding` row per dimension per vendor

**Technical Evaluation Agent (The Enterprise Architect)**
- Retrieves chunks from `TECH_PROPOSAL` and `BCP_PLAN` documents
- Prompt injected with: baseline technical instructions + regulation rules for technical agent (BSP uptime SLA, BCP requirements if applicable) + policy rules
- Evaluates: integration capabilities, scalability, implementation complexity, support commitments, disaster recovery
- Writes one `agent_finding` row per dimension per vendor

Each agent writes `agent_started` and `agent_completed` events to `audit_log`.

**Tables read:** `document_chunk`, `regulation_rule`, `policy_evaluation_rule`, `enterprise_regulation`, `cycle_context`

**Tables written:** `agent_finding`, `audit_log`

---

### Stage 5: Conflict Detection & Reconciliation

**What triggers it:** All four specialist agents have completed findings for all vendors

**Band's role:** Band reads all `agent_finding` rows for the cycle and detects contradictions by comparing:
- A vendor with a high score from one agent and a dealbreaker flag from another agent
- Agents disagreeing on vendor ranking by more than a defined threshold
- A finding that contradicts a regulation requirement (e.g., agent scores vendor positively on data handling but regulation rule states data residency declaration is missing)

**For each conflict detected:**
1. Band writes a row to `agent_conflict` with `resolution_status = pending`
2. The conflicting findings and their evidence are routed to the Chief Procurement Agent
3. Chief Procurement Agent reasons through the conflict using the supporting evidence
4. If resolvable: writes `resolution_notes` and sets `resolution_status = resolved`
5. If not resolvable: sets `resolution_status = escalated`, triggers human review

**Example:**
```
Financial Agent:  Vendor A ranked #1 — lowest 3-year TCO
Security Agent:   Vendor A flagged CRITICAL — no data residency declaration
                  (BSP Circular 982 dealbreaker)

Band detects contradiction → writes to agent_conflict
Chief Procurement Agent resolves:
  "Vendor A disqualified despite lowest cost.
   BSP Circular 982 compliance is non-negotiable.
   Vendor B promoted to #1 despite higher TCO."
```

**Tables read:** `agent_finding`, `regulation_rule`, `enterprise_regulation`

**Tables written:** `agent_conflict`, `audit_log`

---

### Stage 6: Final Recommendation

**Agent:** Chief Procurement Agent

**What triggers it:** All conflicts are resolved or escalated

**What the agent does:**
1. Reads all `agent_finding` rows for the cycle across all vendors
2. Reads all resolved `agent_conflict` rows
3. Reads `policy_weight_config` for scoring weights (defaults to 25% per agent if none set)
4. Calculates weighted scores per vendor:
   ```
   final_score = (financial_score × financial_weight)
               + (legal_score × legal_weight)
               + (security_score × security_weight)
               + (technical_score × technical_weight)
   ```
   Disqualified vendors are excluded from ranking regardless of score
5. Produces ranked vendor list with justification per vendor
6. Writes executive summary in plain language for non-technical decision makers
7. Writes trade-off notes explicitly addressing any conflicts and disqualifications
8. Calculates overall `confidence_score`
9. If `confidence_score < threshold` or any unresolved escalations exist, sets `requires_escalation = TRUE`

**System actions:**
1. Writes final output to `recommendation`
2. If `requires_escalation = FALSE`: recommendation is released to the procurement team
3. If `requires_escalation = TRUE`: recommendation is held and routed to human procurement lead for review
4. Writes `recommendation_generated` event to `audit_log`

**Tables read:** `agent_finding`, `agent_conflict`, `policy_weight_config`, `vendor`, `cycle_context`

**Tables written:** `recommendation`, `audit_log`

---

### Final Output Delivered to Procurement Team

```
VENDOR EVALUATION REPORT
RFP: HR Management System 2025
Enterprise: TechCorp Philippines
Cycle ID: [uuid]
Generated: [timestamp]

EXECUTIVE SUMMARY
Based on evaluation of 4 vendor proposals against financial, legal,
security, and technical dimensions under applicable Philippine
regulations (DPA, BSP Circular 982, ISO 27001)...

VENDOR RANKING
#1 — Vendor B  (Score: 87/100)
     Financial: 82 | Legal: 91 | Security: 88 | Technical: 85
     Justification: Strongest compliance posture with competitive TCO...

#2 — Vendor C  (Score: 74/100)
     Financial: 78 | Legal: 70 | Security: 72 | Technical: 76
     Justification: Good technical fit but SLA terms require negotiation...

#3 — Vendor D  (Score: 61/100)
     Financial: 71 | Legal: 55 | Security: 60 | Technical: 58
     Justification: Below threshold on legal terms and scalability...

DISQUALIFIED
Vendor A — Critical: No data residency declaration submitted.
           Automatic disqualification under BSP Circular 982.
           (Despite ranking #1 on financial score at 94/100)

TRADE-OFF NOTES
Vendor A was the most cost-effective option (94/100 financial score)
but was disqualified for failing a mandatory BSP regulatory requirement.
Vendor B is recommended as primary. Consider negotiating on pricing
to close the cost gap with Vendor A's original offer.

AUDIT TRAIL
Full agent findings, evidence citations, conflict log,
and approval history available in the platform.
```

---

## Table Relationship Map

```
enterprise
    │
    ├── enterprise_regulation ──── regulation_framework
    │                                      │
    │                               regulation_rule
    │                               regulation_document_requirement
    │
    ├── procurement_policy
    │       │
    │       ├── policy_document_requirement
    │       ├── policy_evaluation_rule
    │       └── policy_weight_config
    │
    └── procurement_cycle
            │
            ├── cycle_context ──── software_category
            │                └─── data_sensitivity
            │
            ├── vendor
            │     │
            │     ├── vendor_document ──── document_type
            │     │         │
            │     │         └── document_chunk
            │     │
            │     └── agent_finding ──── document_chunk
            │                    └───── regulation_framework
            │
            ├── agent_conflict
            ├── recommendation
            └── audit_log
```

---

*Document generated for internal development reference — Autonomous Vendor Selection & Governance Platform*
