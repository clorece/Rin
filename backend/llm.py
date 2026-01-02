import os
import time
import abc
import traceback
from PIL import Image
import io
import re

# Providers
import google.generativeai as genai
import ollama

# ==============================================================================
# ABSTRACT PROVIDER
# ==============================================================================
class AIProvider(abc.ABC):
    @abc.abstractmethod
    def is_active(self):
        pass

    @abc.abstractmethod
    def analyze_image(self, image_bytes, user_context):
        """Returns { "reaction": "Emoji", "description": "Text" }"""
        pass

    @abc.abstractmethod
    def chat_response(self, history, user_message, user_context):
        """Returns text response string"""
        pass

# ==============================================================================
# GEMINI PROVIDER (CLOUD)
# ==============================================================================
class GeminiProvider(AIProvider):
    def __init__(self):
        self.model = None
        self.api_key = self._load_api_key()
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-flash-latest')
                print("Gemini Provider Initialized.")
            except Exception as e:
                print(f"Gemini Init Error: {e}")

    def _load_api_key(self):
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            # File fallback
            base_dir = os.path.join(os.path.dirname(__file__), "..")
            for fname in ["GEMINI_API_KEY.dev.txt", "GEMINI_API_KEY.txt"]:
                try:
                    path = os.path.join(base_dir, fname)
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            match = re.search(r"AIza[0-9A-Za-z-_]{35}", f.read())
                            if match: return match.group(0)
                except: pass
        return key

    def is_active(self):
        return self.model is not None

    def analyze_image(self, image_bytes, user_context):
        if not self.model: return self._error("No API Key")
        
        try:
            image = Image.open(io.BytesIO(image_bytes))
            prompt = (
                f"You are Thea, a witty digital companion.{user_context} "
                "Look at this screen. "
                "1. REACT to it like a friend. "
                "2. Do NOT just describe it. Speak TO the user. "
                "3. Keep it short (1 sentence). "
                "4. Choose a relevant Emoji. "
                "Output: EMOJI | REACTION"
            )
            response = self.model.generate_content([prompt, image])
            return self._parse_reaction(response.text)
        except Exception as e:
            self._log_error(e)
            return self._error("Vision Error")

    def chat_response(self, history, user_message, user_context):
        if not self.model: return "I need a GEMINI_API_KEY to speak."
        
        try:
            system = f"System: You are Thea, a witty companion.{user_context} Be concise."
            chat = self.model.start_chat(history=history or [])
            response = chat.send_message(f"{system}\nUser: {user_message}")
            return response.text
        except Exception as e:
            print(f"Chat Error: {e}")
            return "I'm having trouble connecting to Google."

    def _parse_reaction(self, text):
        text = text.strip()
        if "|" in text:
            parts = text.split("|", 1)
            return {"reaction": parts[0].strip(), "description": parts[1].strip()}
        return {"reaction": "👀", "description": text}

    def _error(self, msg):
        return {"reaction": "😵", "description": msg}

    def _log_error(self, e):
        try:
            log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "error.log")
            with open(log_path, "a") as f:
                f.write(f"\n[{time.ctime()}] Gemini Error: {str(e)}\n{traceback.format_exc()}")
        except: pass

# ==============================================================================
# OLLAMA PROVIDER (LOCAL)
# ==============================================================================
class OllamaProvider(AIProvider):
    def __init__(self):
        self.model_name = "llama3.2-vision" # Default try
        self.active = False
        try:
            # Check availability
            ollama.list()
            self.active = True
            print(f"Ollama Provider Initialized (Targeting {self.model_name})")
        except Exception as e:
            print(f"Ollama Init Failed (Is it running?): {e}")

    def is_active(self):
        return self.active

    def analyze_image(self, image_bytes, user_context):
        if not self.active: return {"reaction": "🔌", "description": "Ollama is not running."}
        
        try:
            # Ollama Python client takes path or bytes? 
            # Actually simplest is to write temp file or pass base64 if supported.
            # The library supports 'images': [bytes]
            
            prompt = (
                f"You are Thea.{user_context} "
                "React to this screen. Short sentence. Emoji."
                "Format: EMOJI | REACTION"
            )
            
            response = ollama.chat(model=self.model_name, messages=[
                {
                    'role': 'user',
                    'content': prompt,
                    'images': [image_bytes]
                }
            ])
            return self._parse_reaction(response['message']['content'])
        except Exception as e:
            print(f"Ollama Vision Error: {e}")
            return {"reaction": "😵", "description": "I can't see clearly (Ollama Error)."}

    def chat_response(self, history, user_message, user_context):
        if not self.active: return "Ollama is offline."
        
        try:
            # Convert history to Ollama format if needed (list of dicts is standard)
            msgs = []
            if history:
                msgs = history # Assuming compatible structure
            
            msgs.append({'role': 'system', 'content': f"You are Thea.{user_context} Be concise."})
            msgs.append({'role': 'user', 'content': user_message})
            
            response = ollama.chat(model=self.model_name, messages=msgs)
            return response['message']['content']
        except Exception as e:
            return f"Ollama Error: {e}"

    def _parse_reaction(self, text):
        # Same parsing logic
        text = text.strip()
        if "|" in text:
            parts = text.split("|", 1)
            return {"reaction": parts[0].strip(), "description": parts[1].strip()}
        return {"reaction": "🤖", "description": text}

# ==============================================================================
# MAIN BRAIN CLASS
# ==============================================================================
class TheaMind:
    def __init__(self):
        self.gemini = GeminiProvider()
        self.ollama = OllamaProvider()
        self.provider = None
        
        # Load profile to check preference
        self.profile = self.load_user_profile_data()
        self._select_provider()

    def load_user_profile_data(self):
        profile = {}
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        for fname in ["user_profile.dev.txt", "user_profile.txt"]:
            try:
                path = os.path.join(base_dir, fname)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            if "=" in line and not line.strip().startswith("#"):
                                k, v = line.strip().split("=", 1)
                                if v.strip(): profile[k.strip()] = v.strip()
                    break
            except: pass
        return profile

    def load_user_context_string(self):
        p = self.load_user_profile_data() # Reload freshness
        ctx = ""
        if p.get("Username"): ctx += f" User: {p['Username']}."
        if p.get("DateOfBirth"): ctx += f" Birthday: {p['DateOfBirth']}."
        if p.get("Interests"): ctx += f" Interests: {p['Interests']}."
        return ctx

    def _select_provider(self):
        pref = self.profile.get("AIProvider", "Auto").lower()
        
        if pref == "local" or pref == "ollama":
            self.provider = self.ollama
        elif pref == "cloud" or pref == "gemini":
            self.provider = self.gemini
        else:
            # Auto: Prefer Local if Active, else Gemini
            if self.ollama.is_active():
                self.provider = self.ollama
            else:
                self.provider = self.gemini
        
        print(f"Selected AI Provider: {self.provider.__class__.__name__}")

    def analyze_image(self, image_bytes):
        return self.provider.analyze_image(image_bytes, self.load_user_context_string())

    def chat_response(self, history, user_message):
        return self.provider.chat_response(history, user_message, self.load_user_context_string())

# Singleton
mind = TheaMind()
