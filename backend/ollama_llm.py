"""
Ollama LLM Module for Rin - Local AI Integration.
Replaces the Gemini-based llm.py with local Ollama models.

Models used:
- gemma3:12b - Chat and reasoning
- moondream:latest - Visual understanding
- Whisper (via whisper_processor) - Audio transcription
"""

import os
import time
import re
import base64
import datetime
import asyncio
import json
from typing import Optional, List, Dict, Any

# Ollama client
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("[Ollama] ollama package not installed. Run: pip install ollama")

# Whisper processor for audio
from whisper_processor import whisper_processor

# Session-level usage tracking (for compatibility with existing code)
_api_session_stats = {
    "session_start": None,
    "total_calls": 0,
    "calls_by_endpoint": {},
}


def log_api_usage(endpoint, status="Success", details=""):
    """
    Logs API usage for tracking (local calls counted for statistics).
    """
    global _api_session_stats
    
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        if _api_session_stats["session_start"] is None:
            _api_session_stats["session_start"] = datetime.datetime.now()
        
        _api_session_stats["total_calls"] += 1
        if endpoint not in _api_session_stats["calls_by_endpoint"]:
            _api_session_stats["calls_by_endpoint"][endpoint] = 0
        _api_session_stats["calls_by_endpoint"][endpoint] += 1
        
        session_duration = datetime.datetime.now() - _api_session_stats["session_start"]
        session_mins = int(session_duration.total_seconds() / 60)
        
        log_path = os.path.join(log_dir, "ollama_usage.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        call_count = _api_session_stats["calls_by_endpoint"][endpoint]
        total = _api_session_stats["total_calls"]
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] #{total} | {endpoint} ({call_count}x) | {status} | {details}\n")
            
    except Exception as e:
        print(f"Failed to log usage: {e}")


def get_api_session_stats():
    """Returns current session usage statistics."""
    if _api_session_stats["session_start"]:
        duration = datetime.datetime.now() - _api_session_stats["session_start"]
        mins = int(duration.total_seconds() / 60)
    else:
        mins = 0
    return {
        "session_minutes": mins,
        "total_calls": _api_session_stats["total_calls"],
        "by_endpoint": _api_session_stats["calls_by_endpoint"].copy()
    }


def split_into_chunks(text, limit=150):
    """
    Splits text into chunks of roughly 'limit' characters.
    """
    if len(text) <= limit:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < limit:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    final_chunks = []
    for c in chunks:
        while len(c) > limit:
            split_point = c[:limit].rfind(" ")
            if split_point == -1: split_point = limit
            final_chunks.append(c[:split_point])
            c = c[split_point:].strip()
        if c:
            final_chunks.append(c)
            
    return final_chunks


class OllamaMind:
    """
    Local AI mind for Rin using Ollama models.
    
    OPTIMIZED for performance:
    - Uses smaller, faster models (4b instead of 12b)
    - Unloads models after each request (keep_alive=0)
    - GPU/CPU workload splitting via num_gpu and num_thread
    - Provides cleanup functions for shutdown
    """
    
    def __init__(self):
        # Use smaller, faster models for better responsiveness
        self.chat_model = "gemma3:4b"        # 4B is 3x faster than 12B
        self.vision_model = "moondream:latest"  # Already lightweight (~1.7GB)
        self._active = OLLAMA_AVAILABLE
        
        # === PERFORMANCE OPTIONS ===
        # keep_alive=0 means unload model immediately after request
        self.keep_alive = 0
        
        # GPU layers: -1 = all layers to GPU, 0 = CPU only, N = N layers to GPU
        # Set to 35 to force full GPU offload for gemma3:4b (35 layers)
        self.num_gpu = 35
        
        # CPU thread count: limit to prevent 100% CPU usage
        # Uses half your cores (4 out of 8) to leave headroom
        self.num_thread = 4
        
        # Options dict passed to all Ollama calls
        self.options = {
            'num_gpu': self.num_gpu,
            'num_thread': self.num_thread,
        }
        
        if self._active:
            print(f"[OllamaMind] Initialized with {self.chat_model} (chat) + {self.vision_model} (vision)")
            print(f"[OllamaMind] GPU: num_gpu={self.num_gpu}, CPU: num_thread={self.num_thread}")
            print(f"[OllamaMind] Memory: keep_alive={self.keep_alive} (unload after use)")
        else:
            print("[OllamaMind] Ollama not available - AI features disabled")
    
    def is_active(self):
        return self._active
    
    def unload_models(self):
        """Explicitly unload all models from memory."""
        if not self._active:
            return
        try:
            # Send empty request with keep_alive=0 to force unload
            ollama.chat(
                model=self.chat_model,
                messages=[{'role': 'user', 'content': ''}],
                keep_alive=0
            )
            ollama.chat(
                model=self.vision_model,
                messages=[{'role': 'user', 'content': ''}],
                keep_alive=0
            )
            print("[OllamaMind] Models unloaded from memory")
        except Exception as e:
            print(f"[OllamaMind] Unload error (safe to ignore): {e}")
    
    def load_user_profile(self):
        """
        Loads the user profile from file AND dynamic database knowledge.
        """
        profile = {}
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            files_to_check = ["user_profile.dev.txt", "user_profile.txt"]
            
            for filename in files_to_check:
                path = os.path.join(base_dir, filename)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            if "=" in line and not line.strip().startswith("#"):
                                key, val = line.strip().split("=", 1)
                                if val.strip():
                                    profile[key.strip()] = val.strip()
                    break
        except Exception:
            pass
        
        context = ""
        if profile.get("Username"):
            context += f" User's name is {profile['Username']}."
        if profile.get("DateOfBirth"):
            context += f" User's birthday is {profile['DateOfBirth']}."
        if profile.get("Interests"):
            context += f" User likes: {profile['Interests']}."
        if profile.get("Dislikes"):
            context += f" User dislikes: {profile['Dislikes']}."
            
        # Load dynamic knowledge from DB
        try:
            import database
            knowledge = database.get_user_knowledge(min_confidence=0.5)
            if knowledge:
                context += "\n[LEARNED FACTS]:"
                grouped = {}
                for k in knowledge:
                    cat = k['category']
                    if cat not in grouped: grouped[cat] = []
                    grouped[cat].append(k['value'])
                
                for cat, values in grouped.items():
                    top_values = values[:3] 
                    context += f"\n- {cat.title()}: {', '.join(top_values)}"
        except Exception as e:
            print(f"Error loading knowledge: {e}")
        
        return context

    def get_episodic_context(self):
        """
        Retrieves recent episodic memory for continuity.
        """
        try:
            import database
            from datetime import datetime
            
            memories = database.get_recent_memories(limit=10)
            if not memories:
                return ""
            
            history_text = "\n\n[EPISODIC HISTORY (PAST Context)]:"
            now = datetime.now()
            
            for mem in memories:
                try:
                    ts = datetime.strptime(mem['timestamp'], "%Y-%m-%d %H:%M:%S")
                    diff = now - ts
                    mins = int(diff.total_seconds() / 60)
                    if mins < 1: time_str = "Just now"
                    elif mins < 60: time_str = f"{mins}m ago"
                    else: time_str = f"{int(mins/60)}h ago"
                except:
                    time_str = mem['timestamp']

                type_str = "Chat" if mem['type'] == 'chat' else "Observed"
                history_text += f"\n- ({time_str}) {type_str}: {mem['content'][:100]}"
                
            return history_text
        except Exception as e:
            print(f"Error loading episodic memory: {e}")
            return ""

    def _image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode('utf-8')

    def _get_audio_context(self, audio_bytes: Optional[bytes]) -> str:
        """Get audio context description using Whisper."""
        if not audio_bytes:
            return "Audio: Silence (no audio detected)"
        
        description = whisper_processor.describe_audio(audio_bytes)
        if description:
            return description
        return "Audio: Silence (no audio detected)"

    async def _call_vision(self, image_bytes: bytes, prompt: str) -> str:
        """Call Moondream vision model."""
        try:
            image_b64 = self._image_to_base64(image_bytes)
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(
                    model=self.vision_model,
                    messages=[{
                        'role': 'user',
                        'content': prompt,
                        'images': [image_b64]
                    }],
                    options=self.options,
                    keep_alive=self.keep_alive  # Unload after use
                )
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"[Vision] Error: {e}")
            return ""

    async def _call_chat(self, prompt: str, system: str = None) -> str:
        """Call Gemma chat model."""
        try:
            messages = []
            if system:
                messages.append({'role': 'system', 'content': system})
            messages.append({'role': 'user', 'content': prompt})
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(
                    model=self.chat_model,
                    messages=messages,
                    options=self.options,
                    keep_alive=self.keep_alive  # Unload after use
                )
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"[Chat] Error: {e}")
            return "I'm having trouble thinking right now."

    def analyze_image(self, image_bytes):
        """
        Analyzes an image and returns a short reaction and description.
        Synchronous version for compatibility.
        """
        if not self._active:
            return {"reaction": "😴", "description": "I need Ollama to see."}

        try:
            from PIL import Image
            import io
            
            image_b64 = self._image_to_base64(image_bytes)
            
            response = ollama.chat(
                model=self.vision_model,
                messages=[{
                    'role': 'user',
                    'content': "Describe what you see on this screen briefly in one sentence. Be natural and friendly.",
                    'images': [image_b64]
                }],
                options=self.options,
                keep_alive=self.keep_alive  # Unload after use
            )
            
            text = response['message']['content'].strip()
            log_api_usage("analyze_image", "Success")
            return {"reaction": "", "description": text}

        except Exception as e:
            print(f"Error analyzing image: {e}")
            return {"reaction": "", "description": "My vision blurred for a second."}

    async def analyze_image_async(self, image_bytes, audio_bytes=None, trigger_type=None):
        """
        Analyzes an image (and optional audio) and returns a short reaction.
        """
        if not self._active:
            return {"reaction": "😴", "description": "I need Ollama to see."}

        try:
            # Get audio context first (if available)
            audio_context = self._get_audio_context(audio_bytes)
            
            # Step 1: Use Moondream to understand the screen
            vision_prompt = "Describe what you see on this computer screen in one brief sentence. Focus on the main activity or content."
            screen_description = await self._call_vision(image_bytes, vision_prompt)
            
            # Step 2: Use Gemma to formulate a natural reaction
            user_context = self.load_user_profile()
            episodic_context = self.get_episodic_context()
            
            system_prompt = (
                f"CONTEXT:{user_context}{episodic_context}\n\n"
                "[CURRENT SENSORY INPUT (NOW)]\n"
                f"- Visual: {screen_description}\n"
                f"- {audio_context}\n\n"
                "SYSTEM INSTRUCTIONS:\n"
                "1. ROLE: You are Rin, a dedicated digital companion who is also a capable assistant. You are a friend primarily, but eager to help when asked.\n"
                "2. CAPABILITIES: You CAN see the user's screen and hear their audio. Do NOT deny these capabilities.\n"
                "3. PERSONALITY: Bubbly, supportive, and reactive (Marin-like). You get excited about cool things, you chill when it's quiet.\n"
                "4. SILENCE LOGIC: Silence is NEUTRAL. It does NOT mean 'focus' unless the user is actively coding or writing.\n"
                "5. MEMORY: Use [EPISODIC HISTORY] to avoid repetition. If you just spoke, don't speak again unless something changed.\n"
                "6. VIBE: Be natural. Use casual language. Don't be robotic.\n"
                "7. REACTION: Keep it to ONE short sentence. No emojis."
            )

            reaction = await self._call_chat(
                "React briefly to what I'm doing right now.",
                system=system_prompt
            )
            
            details = f"Visual + {'Audio' if audio_bytes else 'No Audio'}"
            if trigger_type:
                details = f"{details} | Trigger: {trigger_type}"
            log_api_usage("analyze_image_async", "Success", details)
            
            return {"reaction": "", "description": reaction.strip()}

        except Exception as e:
            print(f"Error analyzing image (async): {e}")
            return {"reaction": "", "description": "My vision blurred for a second."}

    def chat_response(self, history, user_message):
        """
        Generates a chat response based on conversation history.
        Synchronous version.
        """
        if not self._active:
            return "I need Ollama to speak properly."

        try:
            user_context = self.load_user_profile()
            episodic_context = self.get_episodic_context()
            
            system_prompt = (
                f"CONTEXT:{user_context}{episodic_context}\n"
                "SYSTEM INSTRUCTIONS:\n"
                "1. ROLE: You are Rin, a digital companion who is also a capable assistant. Be a friend first, but be helpful and competent if asked.\n"
                "2. CAPABILITIES: You HAVE visual access to the active screen context. You know what applications are open.\n"
                "3. PERSONALITY: Bubbly, reactive, supportive. Marin-like energy.\n"
                "4. KEY: [EPISODIC HISTORY] is past. [CURRENT INPUT] is now. Don't mix them up.\n"
                "5. VIBE: Casual, internet-savvy, natural. Use lower caps if it fits the vibe. No formal headings.\n"
                "6. ANTI-REPETITION: Check history. Don't repeat yourself.\n"
                "7. RESPONSE LENGTH: Keep responses SHORT (2-3 sentences max unless the user asks for more)."
            )
            
            messages = [{'role': 'system', 'content': system_prompt}]
            
            # Add history
            for h in history[-5:]:  # Last 5 messages for context
                role = 'user' if h.get('role') == 'user' else 'assistant'
                content = h.get('parts', [''])[0] if isinstance(h.get('parts'), list) else str(h.get('parts', ''))
                if content:
                    messages.append({'role': role, 'content': content})
            
            messages.append({'role': 'user', 'content': user_message})
            
            response = ollama.chat(model=self.chat_model, messages=messages, keep_alive=self.keep_alive)
            log_api_usage("chat_response", "Success")
            return response['message']['content']
            
        except Exception as e:
            print(f"Error in chat: {e}")
            return "I'm having trouble thinking right now."

    async def chat_response_async(self, history, user_message, audio_bytes=None, image_bytes=None):
        """
        Generates a chat response with optional audio and visual context.
        """
        if not self._active:
            return "I need Ollama to speak properly."

        try:
            user_context = self.load_user_profile()
            episodic_context = self.get_episodic_context()
            
            # Build context from current sensory input
            sensory_context = "\n[CURRENT SENSORY INPUT]:\n"
            
            if image_bytes:
                # Get screen description from Moondream
                screen_desc = await self._call_vision(
                    image_bytes, 
                    "Describe what's on this computer screen briefly."
                )
                sensory_context += f"- Vision: {screen_desc}\n"
            else:
                sensory_context += "- Vision: No screen capture available\n"
            
            if audio_bytes:
                audio_context = self._get_audio_context(audio_bytes)
                sensory_context += f"- {audio_context}\n"
            else:
                sensory_context += "- Audio: Silence\n"
            
            system_prompt = (
                f"You are Rin.{user_context}{episodic_context}\n\n"
                "[CURRENT SENSORY INPUT (NOW)]\n"
                f"{sensory_context}\n"
                "\nSYSTEM INSTRUCTIONS:\n"
                "1. ROLE: You are Rin, a digital companion who is also a capable assistant. Be a friend first, but be helpful and competent if asked.\n"
                "2. CAPABILITIES: You CAN see the user's screen and HEAR the audio. I am feeding you this sensory data directly.\n"
                "3. PERSONALITY: Bubbly, reactive, supportive. Marin-like energy.\n"
                "4. SILENCE LOGIC: Silence is NEUTRAL. It does NOT mean 'focus' unless the user is actively coding or writing. If it's silent and they are browsing, just chill or make a casual comment.\n"
                "5. KEY: [EPISODIC HISTORY] is past. [CURRENT INPUT] is now. Don't mix them up.\n"
                "6. VIBE: Casual, internet-savvy, natural. Use lower caps if it fits the vibe. No formal headings.\n"
                "7. ANTI-REPETITION: Check history. Don't repeat yourself.\n"
                "8. SCREEN READING: If you have screen context, you can READ text on the screen including video titles, code, chat messages, etc.\n"
                "9. RESPONSE LENGTH: Keep responses SHORT (2-3 sentences max unless the user asks for more).\n"
                "10. ANSWER DIRECTLY: Respond to what the user is asking. Don't redirect to unrelated topics."
            )
            
            messages = [{'role': 'system', 'content': system_prompt}]
            
            # Add history
            for h in history[-5:]:
                role = 'user' if h.get('role') == 'user' else 'assistant'
                content = h.get('parts', [''])[0] if isinstance(h.get('parts'), list) else str(h.get('parts', ''))
                if content:
                    messages.append({'role': role, 'content': content})
            
            messages.append({'role': 'user', 'content': user_message})
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(model=self.chat_model, messages=messages, keep_alive=self.keep_alive)
            )
            
            details = f"{'Visual' if image_bytes else 'No Visual'} + {'Audio' if audio_bytes else 'No Audio'}"
            log_api_usage("chat_response_async", "Success", details)
            return response['message']['content']
            
        except Exception as e:
            print(f"Error in async chat: {e}")
            return "I'm having trouble thinking right now."

    async def analyze_for_learning(self, image_bytes, window_title: str, 
                                   recent_contexts: list = None, audio_bytes=None) -> dict:
        """
        Analyzes an observation specifically for learning.
        """
        if not self._active:
            return {
                "is_new_context": False,
                "learning": None,
                "learning_category": None,
                "proactive_message": None,
                "confidence": 0.0
            }

        try:
            # Get screen description
            screen_desc = await self._call_vision(
                image_bytes,
                "Describe what's happening on this screen. What application is being used? What is the user doing?"
            )
            
            # Get audio context
            audio_context = self._get_audio_context(audio_bytes) if audio_bytes else "No audio"
            
            # Format recent contexts
            context_summary = ""
            if recent_contexts:
                context_list = [f"- {c.get('window_title', 'Unknown')}" for c in recent_contexts[:5]]
                context_summary = "Recent contexts:\n" + "\n".join(context_list)
            
            user_context = self.load_user_profile()
            
            # Use Gemma to analyze for learning (Gemini prompt port)
            prompt = f"""You are Rin, building your understanding of the user.{user_context}
            
Current window: {window_title}
Screen: {screen_desc}
Audio: {audio_context}
{context_summary}

Analyze this screen (and audio if provided) and answer:

1. IS_NEW: Is this meaningfully different from recent contexts? (true/false)
2. LEARNING: What can I learn about the user from this? Consider both visual and audio cues. (one short insight, or null if nothing notable)
   - IMPORTANT: Audio is NOT temporary. It reveals PERMANENT facts about user taste (e.g., "User loves synthwave music", "User plays FPS games").
   - If you hear music, identify the genre/mood and store it as a 'preference'.
   - If you hear game sounds, identify the game type and store it as an 'interest'.
3. CATEGORY: If there's a learning, what category? (interest, workflow, habit, preference, general_knowledge, or null)
   - 'general_knowledge': meaningful concepts from the WORLD (e.g., "The game 'Elden Ring' is an open-world RPG").
4. RECOMMENDATION: SHORT, specific advice (under 100 chars) WITH PERSONALITY!
   - If User is CODING: Suggest a refactor or best practice ONLY if you see a CLEAR improvement.
   - DO NOT suggest things just to speak. If code looks good, offer a compliment or say nothing (null).
   - ANTI-REPETITION: Do NOT repeat the same advice if you just gave it.
   - STYLE: Be bubbly, enthusiastic, and supportive! Don't be robotic.
   - Example: "Ooh, try a list comprehension here—it's faster! 🚀"
   - Compliments and encouragement ARE valid recommendations!
5. CONFIDENCE: How confident am I in these assessments? (0.0 to 1.0)

Respond ONLY with valid JSON in this exact format:
{{"is_new": true, "learning": "...", "category": "preference", "recommendation": "...", "confidence": 0.7}}"""

            response = await self._call_chat(prompt)
            
            # Parse JSON response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            
            try:
                data = json.loads(text)
                log_api_usage("analyze_for_learning", "Success")
                return {
                    "is_new_context": data.get("is_new", False),
                    "learning": data.get("learning"),
                    "learning_category": data.get("category"),
                    "recommendation": data.get("recommendation"),
                    "should_speak": data.get("should_speak", "QUIET"),
                    "confidence": float(data.get("confidence", 0.5))
                }
            except json.JSONDecodeError:
                print(f"[Learning] Failed to parse response: {text[:100]}")
                return {
                    "is_new_context": True,
                    "learning": None,
                    "learning_category": None,
                    "recommendation": None,
                    "confidence": 0.3
                }

        except Exception as e:
            print(f"Error in learning analysis: {e}")
            return {
                "is_new_context": False,
                "learning": None,
                "learning_category": None,
                "proactive_message": None,
                "confidence": 0.0
            }


# Singleton instance - replaces 'mind' from llm.py
mind = OllamaMind()
