import sys
import os

# Add backend to path so we can import llm
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from llm import mind, OllamaProvider, GeminiProvider

print("=== Thea AI Provider Verification ===")
print(f"Active Provider: {mind.provider.__class__.__name__}")

# Check logic
if isinstance(mind.provider, GeminiProvider):
    print(" [INFO] Using Cloud (Gemini)")
    if not mind.provider.api_key:
        print(" [WARN] Gemini selected but NO API Key found!")

elif isinstance(mind.provider, OllamaProvider):
    print(" [INFO] Using Local (Ollama)")
    if mind.provider.is_active():
        print(" [SUCCESS] Ollama is running and detected.")
        print("Testing minimal chat...")
        try:
            resp = mind.chat_response([], "Hello")
            print(f"Response: {resp}")
        except Exception as e:
            print(f" [FAIL] Chat failed: {e}")
    else:
        print(" [FAIL] Ollama selected but NOT reachable. Is 'ollama serve' running?")
else:
    print(" [ERROR] Unknown provider state.")
