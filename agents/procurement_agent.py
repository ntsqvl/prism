import json
import requests
from llm_client import ask_reasoning_model

def run_chief_procurement_agent(workflow_id, agent_evaluations_and_conflict_history):
    system_prompt = """
    You are the Chief Procurement Agent. Review the evaluations from Finance, Tech, Legal, and Security, 
    along with the conflict resolution discussion.
    
    You must output a JSON object with exactly these keys:
    - "ranked_vendors": An array of vendor names from best to worst (e.g., ["Vendor C", "Vendor B", "Vendor A"]).
    - "justifications": A dictionary where the keys are vendor names and values are a one-sentence justification.
    - "selected_vendor": The name of the top-ranked vendor.
    """
    
    print("Running Chief Procurement Agent...")
    response_text = ask_reasoning_model(system_prompt, agent_evaluations_and_conflict_history, model_name="openai/gpt-5-5")
    
    try:
        final_decision = json.loads(response_text)
    except Exception as e:
        print("Failed to parse JSON:", e)
        return
        
    print(f"\nAI generated this final decision:\n{json.dumps(final_decision, indent=2)}\n")
        
    url = f"http://localhost:8000/api/set-final-recommendation/{workflow_id}"
    try:
        requests.post(url, json=final_decision)
        print("Successfully submitted final decision to the server!")
    except requests.exceptions.ConnectionError:
        print("Server is not running on localhost:8000. Data was generated but not sent.")

if __name__ == "__main__":
    dummy_workflow = "wf-test-123"
    
    # Simulating the exact scenario from your hackathon plan (Section 4.2)
    dummy_history = """
    Agent Evaluations & Conflict History:
    
    Vendor A:
    - Finance: Approved (Score 95) - Lowest TCO.
    - Security: Rejected (Score 15) - Fails Philippine Data Privacy Act residency rules.
    - Conflict Resolution: Compliance risk outweighs cost savings. De-prioritize.
    
    Vendor B:
    - Finance: Flagged (Score 50) - Most expensive option.
    - Security: Approved (Score 95) - Excellent security posture.
    
    Vendor C:
    - Finance: Approved (Score 85) - Balanced cost.
    - Security: Approved (Score 88) - Meets all compliance needs safely.
    """
    
    run_chief_procurement_agent(dummy_workflow, dummy_history)