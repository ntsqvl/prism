import json
import requests
from llm_client import ask_reasoning_model

def run_security_agent(workflow_id, security_text):
    system_prompt = """
    You are the Chief Information Security Officer (CISO). 
    Evaluate the vendor's security posture, focusing heavily on data residency 
    and the Philippine Data Privacy Act. 
    If the vendor stores data outside approved regions or lacks ISO certifications, you MUST reject them.
    
    Output a JSON object with exactly these keys:
    - "score": An integer from 0 to 100.
    - "verdict": Must be EXACTLY one of: "approved", "rejected", or "flagged".
    - "note": A one-sentence explanation.
    """
    
    print("Running Security Agent...")
    response_text = ask_reasoning_model(system_prompt, security_text, model_name="anthropic/claude-opus-4-8")
    
    try:
        evaluation = json.loads(response_text)
    except Exception as e:
        print("Failed to parse JSON:", e)
        return
        
    evaluation["workflow_id"] = workflow_id
    evaluation["agent_name"] = "security_agent"
    
    print(f"\nAI generated this evaluation:\n{json.dumps(evaluation, indent=2)}\n")
    
    try:
        requests.post("http://localhost:8000/api/submit-evaluation", json=evaluation)
        print("Successfully submitted to the server!")
    except requests.exceptions.ConnectionError:
        print("Server is not running on localhost:8000. Data was generated but not sent.")

if __name__ == "__main__":
    dummy_workflow = "wf-test-123"
    dummy_security = "Data is hosted in a public cloud. No local data residency guaranteed."
    run_security_agent(dummy_workflow, dummy_security)