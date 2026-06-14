import httpx
import os
from dotenv import load_dotenv

# Force load the .env file
load_dotenv()

BAND_REST_URL = os.getenv("THENVOI_REST_URL", "https://app.band.ai")
API_KEY = os.getenv("THENVOI_AGENT_API_KEY")

# --- DEBUGGER: This will print to your terminal so we know if it loaded ---
if API_KEY:
    print(f"🔒 SUCCESS: API Key loaded (starts with {API_KEY[:5]}...)")
else:
    print("❌ ERROR: API Key is NONE. Python cannot find the .env file!")

# Swap to X-API-Key format just in case Band prefers it over Bearer token
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}
async def verify_auth():
    async with httpx.AsyncClient() as client:

        response = await client.get(
            f"{BAND_REST_URL}/api/v1/agent/me",
            headers=HEADERS,
        )

        print("AUTH STATUS:", response.status_code)
        print(response.text)

        response.raise_for_status()

        return response.json()
    
async def create_evaluation_room(vendor_name: str):
    async with httpx.AsyncClient() as client:
        url = f"{BAND_REST_URL}/api/v1/agent/chats"

        response = await client.post(
            url,
            headers={"X-API-Key": API_KEY},
            json={
                "chat": {
                    "title": f"Evaluation: {vendor_name}"
                }
            }
        )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        response.raise_for_status()

        data = response.json()
        return data["data"]["id"]  

async def add_participant(chat_id: str, agent_handle: str):
    """Adds a specific agent to the chat room."""
    async with httpx.AsyncClient() as client:
        payload = {
            "participant_handle": agent_handle 
        }
        response = await client.post(f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/participants", headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()

async def trigger_workflow(chat_id: str, vendor_name: str):
    """Sends the initial message to kick off the agents."""
    async with httpx.AsyncClient() as client:
        # We explicitly @mention the agents so Band routes the message to them
        payload = {
            "content": f"A new vendor proposal for '{vendor_name}' has been loaded. @FinanceAgent extract the TCO and pricing matrix. @SecurityAgent review the data privacy clauses.",
            # Commma-separated list of the exact display names to mention
            "recipients": "FinanceAgent, SecurityAgent" 
        }
        response = await client.post(f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/messages", headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()
    
async def get_chat_messages(chat_id: str):
    """Fetches the message history of the chat room."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BAND_REST_URL}/api/v1/agent/chats/{chat_id}/messages", headers=HEADERS)
        response.raise_for_status()
        return response.json()  