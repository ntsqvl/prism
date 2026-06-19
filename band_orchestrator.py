import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from band_client import (
    create_evaluation_room,
    add_participant,
    trigger_workflow,
    get_chat_messages,
    HEADERS,
    BAND_REST_URL
)
import httpx

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BandOrchestrator:
    def __init__(self, workflow_id: str, vendor_name: str, agent_handles: Dict[str, str]):
        self.workflow_id = workflow_id
        self.vendor_name = vendor_name
        self.agent_handles = agent_handles
        self.chat_id = None
        self.evaluations = {}
        self.is_running = True

    async def setup_room(self):
        """Creates the Band room and adds participants."""
        try:
            self.chat_id = await create_evaluation_room(self.vendor_name)
            logger.info(f"Created Band room: {self.chat_id}")

            # Add all agents as participants
            tasks = [add_participant(self.chat_id, handle) for handle in self.agent_handles.values()]
            await asyncio.gather(*tasks)
            logger.info(f"Added agents to room: {list(self.agent_handles.values())}")

            return self.chat_id
        except Exception as e:
            logger.error(f"Failed to setup Band room: {e}")
            raise

    async def start_workflow(self, context_summary: str):
        """Triggers the evaluation workflow by mentioning specialist agents."""
        if not self.chat_id:
            raise ValueError("Room not setup. Call setup_room() first.")

        specialist_mentions = [
            self.agent_handles["financial_agent"],
            self.agent_handles["technical_agent"],
            self.agent_handles["legal_agent"],
            self.agent_handles["security_agent"]
        ]
        
        content = (
            f"🚀 **New Vendor Evaluation Started**\n"
            f"**Vendor:** {self.vendor_name}\n"
            f"**Workflow ID:** {self.workflow_id}\n\n"
            f"**Context Summary:** {context_summary}\n\n"
            f"Attention specialist agents: {' '.join(specialist_mentions)}\n"
            f"Please review the vendor documents and post your evaluation in JSON format including `score`, `verdict`, and `note`."
        )

        async with httpx.AsyncClient() as client:
            payload = {
                "content": content,
                "recipients": ",".join([h.strip("@") for h in specialist_mentions])
            }
            response = await client.post(
                f"{BAND_REST_URL}/api/v1/agent/chats/{self.chat_id}/messages",
                headers=HEADERS,
                json=payload
            )
            response.raise_for_status()
            logger.info("Triggered specialist agent evaluation")

    async def poll_and_process(self, on_evaluation_received, on_conflict_detected, on_final_decision):
        """Polls Band room for agent responses and processes them."""
        processed_message_ids = set()
        
        while self.is_running:
            try:
                messages_data = await get_chat_messages(self.chat_id)
                messages = messages_data.get("data", []) if isinstance(messages_data, dict) else []

                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id in processed_message_ids:
                        continue
                    
                    sender_handle = msg.get("sender", {}).get("handle", "")
                    content = msg.get("content", "")

                    # Identify which agent sent the message
                    agent_key = None
                    for key, handle in self.agent_handles.items():
                        if handle == sender_handle:
                            agent_key = key
                            break
                    
                    if agent_key:
                        try:
                            # Attempt to parse JSON evaluation
                            clean_content = content.strip().strip("`").replace("json\n", "").replace("json", "")
                            eval_data = json.loads(clean_content)
                            
                            if "score" in eval_data and "verdict" in eval_data:
                                logger.info(f"Received evaluation from {agent_key}")
                                self.evaluations[agent_key] = eval_data
                                await on_evaluation_received(agent_key, eval_data)
                                
                        except json.JSONDecodeError:
                            # Not a JSON evaluation, could be a discussion message
                            logger.info(f"Received discussion message from {agent_key}")
                            pass

                    processed_message_ids.add(msg_id)

                # Check if all specialists have responded
                specialists = ["financial_agent", "technical_agent", "legal_agent", "security_agent"]
                if all(s in self.evaluations for s in specialists):
                    # Trigger conflict detection logic
                    await on_conflict_detected(self.evaluations)
                    
                    # If final decision received, we can stop
                    if "chief_procurement_agent" in self.evaluations:
                        await on_final_decision(self.evaluations["chief_procurement_agent"])
                        self.is_running = False

                await asyncio.sleep(5) # Poll every 5 seconds
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(10)

    async def initiate_debate(self, conflict_type: str, involved_agents: List[str], reason: str):
        """Starts a debate thread in Band between conflicting agents."""
        mentions = [self.agent_handles[a] for a in involved_agents]
        content = (
            f"⚠️ **Conflict Detected: {conflict_type}**\n"
            f"Involved Agents: {' '.join(mentions)}\n\n"
            f"**Reason:** {reason}\n\n"
            f"Agents, please discuss your findings and try to reach an alignment. "
            f"{self.agent_handles['chief_procurement_agent']} will mediate if necessary."
        )
        
        async with httpx.AsyncClient() as client:
            payload = {
                "content": content,
                "recipients": ",".join([h.strip("@") for h in mentions])
            }
            await client.post(
                f"{BAND_REST_URL}/api/v1/agent/chats/{self.chat_id}/messages",
                headers=HEADERS,
                json=payload
            )
            logger.info(f"Initiated debate for {conflict_type}")