import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("google_api_key")

if api_key:
    genai.configure(api_key=api_key)
    models = genai.list_models()
    print("Available Gemini Models:")
    print("-" * 50)
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(f"✓ {m.name}")
else:
    print("API key not found")
