import json
import os
import asyncio
import httpx
from llm_client import ask_reasoning_model
from dotenv import load_dotenv

load_dotenv()

BAND_REST_URL = os.getenv("THENVOI_REST_URL", "https://app.band.ai")
API_KEY = os.getenv("THENVOI_AGENT_API_KEY")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

async def run_legal_agent_band(chat_id, workflow_id, contract_text):
    system_prompt = """
    You are the Corporate Counsel evaluating a vendor contract. 
    Analyze the following text for liability, termination provisions, and SLAs.
    You must output a JSON object with exactly these keys:
    - "score": An integer from 0 to 100 representing contractual safety.
    - "verdict": Must be EXACTLY one of: "approved", "rejected", or "flagged".
    - "note": A one-sentence explanation of your decision.
    """
    
    print(f"Running Legal Agent for workflow {workflow_id} in Band room {chat_id}...")
    response_text = ask_reasoning_model(system_prompt, contract_text, model_name="anthropic/claude-opus-4-8")
    
    if not response_text:
        print("Failed to get response from LLM")
        return

    try:
        evaluation = json.loads(response_text)
    except Exception as e:
        print("Failed to parse JSON:", e)
        return
    
    # Send evaluation to Band room
    content = f"```json\n{json.dumps(evaluation, indent=2)}\n```"
    
    async with httpx.AsyncClient() as client:
        payload = {
            "content": content,
            "recipients": "ChiefProcurementAgent" # Mention the decision maker
        }
        url = f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/messages"
        response = await client.post(url, headers=HEADERS, json=payload)
        
        if response.status_code == 201:
            print("Successfully sent evaluation to Band room!")
        else:
            print(f"Failed to send to Band: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # Example usage
    dummy_chat = "chat-uuid"
    dummy_workflow = "wf-test-123" 
    dummy_contract = "Liability is capped at 12 months of fees. Termination requires 30 days notice."
    asyncio.run(run_legal_agent_band(dummy_chat, dummy_workflow, dummy_contract))