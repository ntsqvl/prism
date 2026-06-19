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

async def run_chief_procurement_agent_band(chat_id, workflow_id, agent_evaluations_and_history):
    system_prompt = """
    You are the Chief Procurement Agent. Review the evaluations from Finance, Tech, Legal, and Security, 
    along with the conflict resolution discussion within the Band room.
    
    You must output a JSON object with exactly these keys:
    - "ranked_vendors": An array of vendor names from best to worst.
    - "justifications": A dictionary where the keys are vendor names and values are a one-sentence justification.
    - "selected_vendor": The name of the top-ranked vendor.
    
    Wrap your final decision in a JSON code block.
    """
    
    print(f"Running Chief Procurement Agent for workflow {workflow_id}...")
    response_text = ask_reasoning_model(system_prompt, agent_evaluations_and_history, model_name="openai/gpt-5-5")
    
    if not response_text:
        return

    try:
        final_decision = json.loads(response_text)
    except Exception as e:
        print("Failed to parse JSON:", e)
        # If it's not JSON, it might be a discussion message
        content = response_text
    else:
        content = f"🏁 **Final Procurement Decision**\n\n```json\n{json.dumps(final_decision, indent=2)}\n```"
        
    async with httpx.AsyncClient() as client:
        payload = {
            "content": content
        }
        url = f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/messages"
        response = await client.post(url, headers=HEADERS, json=payload)
        
        if response.status_code == 201:
            print("Successfully posted final decision to Band!")
        else:
            print(f"Failed to post to Band: {response.status_code}")

async def participate_in_debate(chat_id, conflict_context):
    """Participates in an ongoing debate to provide guidance."""
    system_prompt = """
    You are the Chief Procurement Agent. There is a conflict between specialist agents.
    Provide a brief, high-level guidance message to help them align, or ask for more specific evidence.
    Keep your response concise and professional.
    """
    
    response_text = ask_reasoning_model(system_prompt, conflict_context)
    
    async with httpx.AsyncClient() as client:
        payload = {"content": f"⚖️ **Chief's Guidance:** {response_text}"}
        url = f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/messages"
        await client.post(url, headers=HEADERS, json=payload)

if __name__ == "__main__":
    dummy_chat = "chat-uuid"
    dummy_workflow = "wf-test-123"
    dummy_history = "Finance says Vendor A is cheap. Security says Vendor A is risky."
    asyncio.run(run_chief_procurement_agent_band(dummy_chat, dummy_workflow, dummy_history))