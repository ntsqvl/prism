#!/bin/bash

# Test script for new endpoints: upload-vendor-document and retry-evaluation

set -e

BASE_URL="http://localhost:8000"

echo "=== Testing New Endpoints ==="
echo ""

# 1. Create a workflow
echo "1️⃣  Starting workflow..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/start-evaluation?vendor_name=TestVendor")
WORKFLOW_ID=$(echo $RESPONSE | grep -o '"workflow_id":"[^"]*' | cut -d'"' -f4)
echo "   Workflow ID: $WORKFLOW_ID"
echo ""

# 2. Upload a document
echo "2️⃣  Uploading vendor document..."
echo "   Creating sample contract..."
cat > /tmp/sample_contract.txt << 'EOF'
VENDOR CONTRACT

Vendor Name: TestVendor
Service Level Agreement: 99.9% uptime
Data Residency: EU-only
Compliance: GDPR, ISO 27001
Cost: $50,000/year
EOF

UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/api/upload-vendor-document/$WORKFLOW_ID" \
  -F "file=@/tmp/sample_contract.txt")
echo "   Upload response:"
echo "   $UPLOAD_RESPONSE" | jq .
echo ""

# 3. Verify document was stored
echo "3️⃣  Retrieving uploaded documents..."
DOC_RESPONSE=$(curl -s "$BASE_URL/api/vendor-documents/$WORKFLOW_ID")
echo "   Documents:"
echo "   $DOC_RESPONSE" | jq .
echo ""

# 4. Wait for workflow to populate evaluations
echo "4️⃣  Waiting for agent evaluations (10 seconds)..."
sleep 10

# 5. Check current status
echo "5️⃣  Current workflow status:"
STATUS=$(curl -s "$BASE_URL/api/workflow-status/$WORKFLOW_ID")
echo "   Stage: $(echo $STATUS | jq -r '.workflow_stage')"
echo "   Overall Status: $(echo $STATUS | jq -r '.overall_status')"
echo ""

# 6. Retry an evaluation
echo "6️⃣  Retrying financial_agent evaluation..."
RETRY_RESPONSE=$(curl -s -X POST "$BASE_URL/api/retry-evaluation/$WORKFLOW_ID/financial_agent")
echo "   Retry response:"
echo "   $RETRY_RESPONSE" | jq .
echo ""

# 7. Verify the agent evaluation was reset
echo "7️⃣  Verifying agent evaluation was reset..."
STATUS_AFTER=$(curl -s "$BASE_URL/api/workflow-status/$WORKFLOW_ID")
FINANCIAL_EVAL=$(echo $STATUS_AFTER | jq '.agent_evaluations.financial_agent')
if [ "$FINANCIAL_EVAL" == "null" ]; then
    echo "   ✅ financial_agent evaluation successfully reset"
else
    echo "   ❌ financial_agent evaluation still exists"
fi
echo ""

# 8. Check audit log
echo "8️⃣  Audit log (last 5 entries):"
curl -s "$BASE_URL/api/workflow-status/$WORKFLOW_ID" | jq '.audit_log[-5:]'
echo ""

echo "=== All tests completed ==="
