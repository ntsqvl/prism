import json
import requests
from llm_client import ask_reasoning_model

def run_legal_agent(workflow_id, contract_text):
    system_prompt = """
    You are the Corporate Counsel evaluating a vendor contract. 
    Analyze the following text for liability, termination provisions, and SLAs.
    You must output a JSON object with exactly these keys:
    - "score": An integer from 0 to 100 representing contractual safety.
    - "verdict": Must be EXACTLY one of: "approved", "rejected", or "flagged".
    - "note": A one-sentence explanation of your decision.
    """
    
    print("Running Legal Agent...")
    response_text = ask_reasoning_model(system_prompt, contract_text, model_name="anthropic/claude-opus-4-8")
    
    try:
        evaluation = json.loads(response_text)
    except Exception as e:
        print("Failed to parse JSON:", e)
        return
    
    evaluation["workflow_id"] = workflow_id
    evaluation["agent_name"] = "legal_agent"
    
    print(f"\nAI generated this evaluation:\n{json.dumps(evaluation, indent=2)}\n")
    
    try:
        requests.post("http://localhost:8000/api/submit-evaluation", json=evaluation)
        print("Successfully submitted to the server!")
    except requests.exceptions.ConnectionError:
        print("Server is not running on localhost:8000. Data was generated but not sent.")

if __name__ == "__main__":
    dummy_workflow = "wf-test-123" 
    dummy_contract = "Liability is capped at 12 months of fees. Termination requires 30 days notice."
    run_legal_agent(dummy_workflow, dummy_contract)