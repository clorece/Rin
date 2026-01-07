"""
Whisper Processor for Rin - Local audio transcription.
Uses OpenAI Whisper for converting audio bytes to text.
"""

import io
import wave
import numpy as np
from typing import Optional

# Whisper will be loaded lazily to avoid slow startup
_whisper_model = None
_whisper_available = False

def _load_whisper():
    """Lazily load whisper model on first use."""
    global _whisper_model, _whisper_available
    
    if _whisper_model is not None:
        return _whisper_model
    
    try:
        import whisper
        # Use 'base' model - good balance of speed and accuracy
        # Runs well on CPU with Ryzen 7 5800X3D
        print("[Whisper] Loading base model (this may take a moment)...")
        _whisper_model = whisper.load_model("base")
        _whisper_available = True
        print("[Whisper] Model loaded successfully")
        return _whisper_model
    except ImportError:
        print("[Whisper] openai-whisper not installed. Audio transcription disabled.")
        print("[Whisper] Install with: pip install openai-whisper")
        _whisper_available = False
        return None
    except Exception as e:
        print(f"[Whisper] Failed to load model: {e}")
        _whisper_available = False
        return None


class WhisperProcessor:
    """Local audio transcription using OpenAI Whisper."""
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
    
    @property
    def model(self):
        """Lazy-load the whisper model."""
        if self._model is None:
            self._model = _load_whisper()
        return self._model
    
    @property
    def is_available(self) -> bool:
        """Check if whisper is available."""
        # Try to load if not yet attempted
        if self._model is None and not _whisper_available:
            self._model = _load_whisper()
        return self._model is not None
    
    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """
        Transcribe audio bytes (WAV format) to text.
        
        Args:
            audio_bytes: WAV file as bytes
            
        Returns:
            Transcribed text or None if transcription failed
        """
        if not self.is_available:
            return None
        
        if not audio_bytes:
            return None
        
        try:
            # Convert WAV bytes to numpy array
            wav_io = io.BytesIO(audio_bytes)
            with wave.open(wav_io, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                n_frames = wf.getnframes()
                audio_data = wf.readframes(n_frames)
            
            # Convert to float32 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # If stereo, convert to mono
            if n_channels == 2:
                audio_np = audio_np.reshape(-1, 2).mean(axis=1)
            
            # Resample to 16kHz if needed (Whisper expects 16kHz)
            if sample_rate != 16000:
                # Simple resampling using numpy
                duration = len(audio_np) / sample_rate
                target_length = int(duration * 16000)
                indices = np.linspace(0, len(audio_np) - 1, target_length).astype(int)
                audio_np = audio_np[indices]
            
            # Check for silence (skip transcription if too quiet)
            rms = np.sqrt(np.mean(audio_np**2))
            if rms < 0.01:  # Silence threshold
                return None
            
            # Transcribe
            result = self.model.transcribe(
                audio_np,
                language="en",  # Default to English, can be made configurable
                fp16=False,     # Use FP32 for CPU compatibility
                verbose=False
            )
            
            text = result.get("text", "").strip()
            
            # Skip if empty or just noise/music detected
            if not text or text.lower() in ["[music]", "(music)", "[silence]", ""]:
                return None
            
            print(f"[Whisper] Transcribed: {text[:50]}...")
            return text
            
        except Exception as e:
            print(f"[Whisper] Transcription failed: {e}")
            return None
    
    def describe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """
        Get a description of the audio content.
        Returns transcription if speech, or a description if music/ambient.
        """
        transcription = self.transcribe(audio_bytes)
        
        if transcription:
            return f"Audio: {transcription}"
        
        # If no speech detected, check if there's audio at all
        if audio_bytes:
            try:
                wav_io = io.BytesIO(audio_bytes)
                with wave.open(wav_io, 'rb') as wf:
                    audio_data = wf.readframes(wf.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(audio_np**2))
                
                if rms > 0.05:
                    return "Audio: Non-speech audio detected (music or ambient sounds)"
                elif rms > 0.01:
                    return "Audio: Quiet audio detected"
            except:
                pass
        
        return None


# Singleton instance
whisper_processor = WhisperProcessor()
