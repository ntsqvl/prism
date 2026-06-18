"""
context_discovery.py
────────────────────
Step 4 — Context Discovery Agent

Runs after all vendor documents are extracted and chunked.
Reads a sample of chunks across all vendors in the cycle and:
  - Classifies software category (OPERATIONAL / BUSINESS / MISSION_CRITICAL)
  - Classifies data sensitivity (INTERNAL / CUSTOMER_PII / FINANCIAL)
  - Identifies document types for each uploaded file
  - Estimates contract value from pricing references
  - Produces a confidence score and evidence trail

Uses Featherless AI with a Qwen Instruct model via JSON mode.

Batching strategy (for models with limited context windows):
  Chunks are split into batches of CONTEXT_BATCH_SIZE (configurable in .env).
  Each batch produces a partial result. Results are merged at the end:
    - software_category_code  → highest severity wins
    - data_sensitivity_code   → highest sensitivity wins
    - confidence_score        → averaged across batches
    - evidence_sources        → all combined
    - document_classifications → combined, deduplicated by file_path
    - estimated_contract_value → first non-null value
    - discovery_summary       → taken from highest-confidence batch
"""

import json
import logging
from openai import OpenAI
from core.config import settings

logger = logging.getLogger(__name__)


def _get_featherless_client() -> OpenAI:
    """Lazily construct and return an OpenAI client for Featherless.

    This avoids creating the client at import time (which fails in tests
    when credentials are not set). The client is created on-demand when the
    agent is actually invoked.
    """
    if not settings.FEATHERLESS_API_KEY and not settings.OPENAI_API_KEY and not settings.AIML_API_KEY:
        raise RuntimeError("No Featherless/OpenAI API key configured for context discovery agent")

    api_key = settings.FEATHERLESS_API_KEY or settings.OPENAI_API_KEY or settings.AIML_API_KEY
    base_url = settings.FEATHERLESS_BASE_URL or settings.AIML_BASE_URL

    return OpenAI(api_key=api_key, base_url=base_url)


# ── Classification Criteria (injected verbatim into the system prompt) ────────

CLASSIFICATION_CRITERIA = """
═══════════════════════════════════════════════════════
SOFTWARE CATEGORY — DECISION RULES
═══════════════════════════════════════════════════════

You must assign exactly ONE of: OPERATIONAL | BUSINESS | MISSION_CRITICAL

MISSION_CRITICAL — assign this when ANY of the following are true:
  • The system directly processes real monetary transactions
    (payments, fund transfers, account debits/credits, settlements)
  • Downtime causes immediate, direct financial loss or regulatory breach
  • The system is a core banking platform, payment gateway, trading engine,
    fraud detection system, or insurance claims processor
  • The vendor's documents mention 99.99%+ uptime SLA requirements
  • The system is described as replacing or interfacing with a core ledger
  • Regulatory references cite BSP Circular 808/982, PCI-DSS, or SWIFT

BUSINESS — assign this when ALL of the following are true:
  • The system supports important business processes but has manual workarounds
    if it goes down for hours or even a day
  • Examples include: CRM, ERP, HRM with payroll (non-banking), document
    management, procurement platforms, inventory systems, legal case management
  • Data loss would be costly and disruptive but recoverable
  • The system integrates with core systems but is NOT itself a core system
  • Regulatory references cite ISO 27001, GDPR, DPA 2012 (data privacy only)

OPERATIONAL — assign this when ALL of the following are true:
  • The system supports internal operations with no direct revenue impact
  • Downtime is inconvenient but causes no financial or regulatory consequence
  • Examples include: attendance tracking, internal ticketing, scheduling,
    employee intranet, internal communications, office supply management
  • No customer data flows through the system
  • No financial transactions are processed

PRIORITY RULE: If evidence points to both BUSINESS and MISSION_CRITICAL,
choose MISSION_CRITICAL and reduce confidence_score by 0.10.
If you cannot determine the category from the documents, choose BUSINESS
and set confidence_score below 0.70 to trigger human confirmation.

═══════════════════════════════════════════════════════
DATA SENSITIVITY — DECISION RULES
═══════════════════════════════════════════════════════

You must assign exactly ONE of: INTERNAL | CUSTOMER_PII | FINANCIAL

FINANCIAL — assign this when ANY of the following are true:
  • The system stores, processes, or transmits financial transactions
  • Data includes: account balances, payment card numbers, loan details,
    credit scores, bank account numbers, transaction histories, fund flows
  • Documents reference PCI-DSS, BSP data residency for financial data,
    AMLA (Anti-Money Laundering Act), or similar financial data regulations
  • The system produces financial statements or audit trails with monetary values

CUSTOMER_PII — assign this when ALL of the following are true:
  • The system handles personal information about customers or employees
    (names, emails, phone numbers, addresses, government IDs, health records)
  • The data is NOT primarily financial in nature (if it is, use FINANCIAL)
  • Documents reference DPA 2012 (Philippine Data Privacy Act), GDPR,
    HIPAA, or similar personal data protection regulations

INTERNAL — assign this when ALL of the following are true:
  • The system handles only internal operational data
  • No customer-facing personal information is stored or processed
  • No financial transaction data flows through the system
  • Data is limited to: schedules, internal metrics, process logs,
    non-sensitive employee operational data (not payroll, not health)

PRIORITY RULE: If BOTH financial and PII data are present, choose FINANCIAL.
If you are uncertain between CUSTOMER_PII and FINANCIAL, choose FINANCIAL
and reduce confidence_score by 0.10.

═══════════════════════════════════════════════════════
DOCUMENT TYPE CLASSIFICATION
═══════════════════════════════════════════════════════

For each document file, classify it into ONE of these document_type_codes:

  TECH_PROPOSAL       — Technical proposal, system architecture, solution overview
  PRICING_SCHEDULE    — Pricing sheet, cost breakdown, commercial offer, quotation
  CONTRACT            — Draft contract, terms and conditions, master service agreement
  SLA_DRAFT           — Service level agreement, uptime commitments, support terms
  SECURITY_QUESTIONNAIRE — Security assessment, cybersecurity questionnaire, infosec form
  DPA_AGREEMENT       — Data processing agreement, data privacy addendum, GDPR DPA
  PENTEST_REPORT      — Penetration testing report, vulnerability assessment
  ISO_CERTIFICATE     — ISO 27001 certificate, SOC 2 report, compliance certification
  BCP_PLAN            — Business continuity plan, disaster recovery plan, DRP
  COMPANY_PROFILE     — Company background, about us, corporate profile
  REFERENCES          — Client references, case studies, past projects
  FINANCIAL_STATEMENTS — Audited financials, balance sheet, income statement
  DATA_RESIDENCY_DECL — Data residency declaration, data localisation statement
  UNKNOWN             — Cannot be determined from available content

If a file path or file name gives a strong signal (e.g. "pricing.pdf",
"contract_draft_v2.pdf"), use that signal alongside the content.
"""

# ── Output Schema ─────────────────────────────────────────────────────────────

OUTPUT_SCHEMA = """
═══════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════════

Return ONLY a valid JSON object. No markdown fences. No explanation before or after.
No trailing commas. The JSON must match this exact structure:

{
  "software_type": "<concise human-readable name, e.g. 'HR Management System'>",
  "software_category_code": "<OPERATIONAL | BUSINESS | MISSION_CRITICAL>",
  "data_sensitivity_code": "<INTERNAL | CUSTOMER_PII | FINANCIAL>",
  "estimated_contract_value": <number in PHP/local currency, or null if not found>,
  "discovery_summary": "<2-4 sentence plain English summary of what is being procured and why>",
  "confidence_score": <float 0.0 to 1.0>,
  "confidence_reasoning": "<one sentence explaining what drives the confidence score>",
  "evidence_sources": [
    {
      "conclusion": "<which specific conclusion this evidence supports>",
      "source_file": "<file path or file name>",
      "page": <integer page number, or null>,
      "quote": "<verbatim short excerpt from the document, max 40 words>"
    }
  ],
  "document_classifications": [
    {
      "file_path": "<exact file_path value as provided in the input>",
      "document_type_code": "<one of the valid codes above>",
      "classification_reasoning": "<one sentence explaining why."
    }
  ]
}

Scoring guidance for confidence_score:
  1.00 — All classifications are unambiguous with strong direct evidence
  0.90 — Strong evidence, minor ambiguity on one dimension
  0.80 — Reasonable evidence but some inference required
  0.70 — Limited evidence, significant inference — triggers human confirmation
  < 0.70 — Insufficient evidence — always triggers human confirmation

The system will automatically require human confirmation when confidence_score < 0.80.
"""

SYSTEM_PROMPT = f"""You are the Context Discovery Agent for an autonomous vendor procurement evaluation platform.

Your task is to analyze sample text chunks extracted from vendor-submitted PDF documents
and determine the procurement context for this evaluation cycle.

You are thorough, precise, and evidence-based. Every classification you make
must be supported by at least one piece of evidence from the provided chunks.
You never guess — if evidence is insufficient, you lower the confidence score.

{CLASSIFICATION_CRITERIA}

{OUTPUT_SCHEMA}
""".strip()


# ── Severity ordering for merge logic ─────────────────────────────────────────

_CATEGORY_RANK = {"OPERATIONAL": 0, "BUSINESS": 1, "MISSION_CRITICAL": 2}
_SENSITIVITY_RANK = {"INTERNAL": 0, "CUSTOMER_PII": 1, "FINANCIAL": 2}


# ── Main Agent Function ───────────────────────────────────────────────────────

def run_context_discovery_agent(sample_chunks: list[dict]) -> dict:
    """
    Analyze sample chunks and return structured procurement context.

    Splits chunks into batches of CONTEXT_BATCH_SIZE to stay within the
    model's context window. Each batch is sent as a separate API call.
    Results are merged into a single final classification.

    Args:
        sample_chunks: list of dicts, each containing:
            - content         (str)        — chunk text
            - page_start      (int)        — starting page in source document
            - section_heading (str | None) — detected section heading
            - file_path       (str)        — path of the source vendor_document

    Returns:
        Merged JSON dict matching the output schema.

    Raises:
        ValueError   — if the model returns unparseable JSON
        RuntimeError — if the API call fails
    """
    if not sample_chunks:
        raise ValueError("No chunks provided to context discovery agent")

    batch_size = settings.CONTEXT_BATCH_SIZE
    batches = [
        sample_chunks[i: i + batch_size]
        for i in range(0, len(sample_chunks), batch_size)
    ]

    logger.info(
        "Context discovery: %d chunks split into %d batch(es) of up to %d",
        len(sample_chunks),
        len(batches),
        batch_size,
    )

    partial_results: list[dict] = []
    client = _get_featherless_client()

    for batch_num, batch in enumerate(batches, start=1):
        logger.info("Processing batch %d/%d (%d chunks)", batch_num, len(batches), len(batch))
        result = _call_agent(client, batch, batch_num, len(batches))
        partial_results.append(result)

    # Single batch — return directly, no merge needed
    if len(partial_results) == 1:
        final_result = partial_results[0]
        # ADDED: explicitly calculate requires_confirmation
        final_result["requires_confirmation"] = final_result.get("confidence_score", 0) < 0.80
        return final_result

    return _merge_results(partial_results)


# ── Single batch API call ─────────────────────────────────────────────────────

def _call_agent(client: OpenAI, batch: list[dict], batch_num: int, total_batches: int) -> dict:
    """Send one batch to the model and return the parsed result."""
    chunks_text = _build_chunks_message(batch, batch_num, total_batches)

    try:
        response = client.chat.completions.create(
            model=settings.FEATHERLESS_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": chunks_text},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2500,
        )
    except Exception as exc:
        logger.error("Featherless API call failed on batch %d: %s", batch_num, exc)
        raise RuntimeError(f"Context discovery agent API error: {exc}") from exc

    raw_content = response.choices[0].message.content

    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Agent returned invalid JSON on batch %d: %s", batch_num, raw_content[:500])
        raise ValueError(f"Context discovery agent returned invalid JSON: {exc}") from exc

    _validate_result(result)

    logger.info(
        "Batch %d/%d complete — category=%s, sensitivity=%s, confidence=%.2f",
        batch_num,
        total_batches,
        result.get("software_category_code"),
        result.get("data_sensitivity_code"),
        result.get("confidence_score", 0),
    )

    return result


# ── Merge logic ───────────────────────────────────────────────────────────────

def _merge_results(results: list[dict]) -> dict:
    """
    Merge partial batch results into one final classification.

    Rules:
      - software_category_code  → highest severity across all batches
      - data_sensitivity_code   → highest sensitivity across all batches
      - confidence_score        → average across all batches
      - estimated_contract_value → first non-null value found
      - discovery_summary       → from the highest-confidence batch
      - software_type           → from the highest-confidence batch
      - evidence_sources        → all combined
      - document_classifications → combined, last-write-wins per file_path
                                   (later batches see more of the doc, so they win)
    """
    logger.info("Merging %d batch results", len(results))

    # Highest-confidence batch drives the narrative fields
    best = max(results, key=lambda r: r.get("confidence_score", 0))

    # software_category_code — highest severity wins
    final_category = max(
        (r.get("software_category_code", "BUSINESS") for r in results),
        key=lambda c: _CATEGORY_RANK.get(c, 0),
    )

    # data_sensitivity_code — highest sensitivity wins
    final_sensitivity = max(
        (r.get("data_sensitivity_code", "INTERNAL") for r in results),
        key=lambda s: _SENSITIVITY_RANK.get(s, 0),
    )

    # confidence_score — average (reflects uncertainty across batches)
    scores = [r.get("confidence_score", 0.0) for r in results]
    final_confidence = round(sum(scores) / len(scores), 4)

    # estimated_contract_value — first non-null
    final_contract_value = next(
        (r.get("estimated_contract_value") for r in results if r.get("estimated_contract_value")),
        None,
    )

    # evidence_sources — combine all
    all_evidence = []
    for r in results:
        all_evidence.extend(r.get("evidence_sources", []))

    # document_classifications — deduplicate by file_path, last batch wins
    doc_classifications: dict[str, dict] = {}
    for r in results:
        for classification in r.get("document_classifications", []):
            fp = classification.get("file_path", "")
            doc_classifications[fp] = classification  # later batch overwrites earlier

    merged = {
        "software_type": best.get("software_type"),
        "software_category_code": final_category,
        "data_sensitivity_code": final_sensitivity,
        "estimated_contract_value": final_contract_value,
        "discovery_summary": best.get("discovery_summary"),
        "confidence_score": final_confidence,
        "confidence_reasoning": (
            f"Averaged across {len(results)} batches. "
            f"Best batch confidence: {best.get('confidence_score', 0):.2f}. "
            f"Category and sensitivity resolved to highest severity seen."
        ),
        "evidence_sources": all_evidence,
        "document_classifications": list(doc_classifications.values()),
    }

    logger.info(
        "Merge complete — category=%s, sensitivity=%s, confidence=%.2f, "
        "evidence_count=%d, doc_classifications=%d",
        merged["software_category_code"],
        merged["data_sensitivity_code"],
        merged["confidence_score"],
        len(all_evidence),
        len(doc_classifications),
    )

    return merged


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_chunks_message(batch: list[dict], batch_num: int, total_batches: int) -> str:
    lines = [
        f"Below are sample text chunks extracted from vendor-submitted PDF documents.",
        f"This is batch {batch_num} of {total_batches}. Analyze only these chunks.",
        "Return the context discovery JSON as instructed.\n",
    ]

    for i, chunk in enumerate(batch, start=1):
        heading = f" | Section: {chunk['section_heading']}" if chunk.get("section_heading") else ""
        lines.append(
            f"--- CHUNK {i} | File: {chunk['file_path']}"
            f" | Page: {chunk.get('page_start', '?')}{heading} ---"
        )
        lines.append(chunk["content"])
        lines.append("")

    return "\n".join(lines)


def _validate_result(result: dict) -> None:
    """
    Validate that the required fields are present and have valid values.
    Raises ValueError on any violation.
    """
    required_fields = [
        "software_type",
        "software_category_code",
        "data_sensitivity_code",
        "discovery_summary",
        "confidence_score",
        "evidence_sources",
        "document_classifications",
    ]
    for field in required_fields:
        if field not in result:
            raise ValueError(f"Agent response missing required field: '{field}'")

    valid_categories = {"OPERATIONAL", "BUSINESS", "MISSION_CRITICAL"}
    if result["software_category_code"] not in valid_categories:
        raise ValueError(
            f"Invalid software_category_code: '{result['software_category_code']}'. "
            f"Must be one of {valid_categories}"
        )

    valid_sensitivities = {"INTERNAL", "CUSTOMER_PII", "FINANCIAL"}
    if result["data_sensitivity_code"] not in valid_sensitivities:
        raise ValueError(
            f"Invalid data_sensitivity_code: '{result['data_sensitivity_code']}'. "
            f"Must be one of {valid_sensitivities}"
        )

    score = result.get("confidence_score")
    if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
        raise ValueError(
            f"confidence_score must be a float between 0.0 and 1.0, got: {score!r}"
        )
