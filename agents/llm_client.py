import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

# Retrieve the API key
AIML_API_KEY = os.getenv("AIML_API_KEY")

# Initialize the official AI/ML API client
client = OpenAI(
    base_url="https://api.aimlapi.com/v1",
    api_key=AIML_API_KEY,
)

def ask_reasoning_model(system_prompt, user_content, model_name="openai/gpt-5-5"):
    """
    Sends a request to the AI/ML API reasoning models.
    Defaults to openai/gpt-5-5, but can be overridden.
    """
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            # Tells the model we want JSON
            response_format={"type": "json_object"}
        )
        
        # Get the raw text
        raw_text = response.choices[0].message.content
        
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        return clean_text
        
    except Exception as e:
        print(f"Error communicating with AI/ML API: {e}")
        return None