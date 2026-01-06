"""
Semantic Layer - Local feature extraction from raw observations.
Extracts structured information without any AI calls.

This layer converts raw sensor data (title, audio, screen) into
semantic features that can be matched against knowledge bases.
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import numpy as np


@dataclass
class ParsedTitle:
    """Structured representation of a parsed window title."""
    raw_title: str
    app_name: Optional[str] = None
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    project_name: Optional[str] = None
    url_domain: Optional[str] = None
    platform: Optional[str] = None  # YouTube, GitHub, etc.
    content_title: Optional[str] = None  # Video name, page title, etc.


@dataclass 
class AudioFeatures:
    """Structured representation of audio analysis."""
    has_audio: bool = False
    volume_level: float = 0.0  # 0.0 to 1.0
    is_silent: bool = True
    is_music_like: bool = False  # Broad frequency spread
    is_speech_like: bool = False  # Concentrated in voice frequencies
    volume_delta: float = 0.0  # Change since last sample


@dataclass
class VisualFeatures:
    """Structured representation of visual analysis."""
    is_stable: bool = True  # Low pixel change
    is_video_playing: bool = False  # High continuous change
    change_percentage: float = 0.0
    dominant_change_region: Optional[str] = None  # top, bottom, center, etc.


@dataclass
class ContextFeatures:
    """Combined semantic features from all sources."""
    title: ParsedTitle
    audio: AudioFeatures
    visual: VisualFeatures
    timestamp: float = 0.0
    
    # Derived classifications
    activity_type: Optional[str] = None  # coding, browsing, media, gaming, etc.
    is_passive: bool = False  # User consuming, not creating
    is_focused: bool = False  # User deeply engaged
    

class TitleParser:
    """Parse window titles into structured components."""
    
    # Common app title patterns
    PATTERNS = {
        "vscode": {
            "regex": r"^(.+?) - (.+?) - Visual Studio Code$",
            "groups": {"file": 1, "project": 2}
        },
        "chrome_youtube": {
            "regex": r"^(.+?) - YouTube",
            "groups": {"content": 1},
            "platform": "YouTube"
        },
        "chrome_github": {
            "regex": r"^(.+?) · GitHub",
            "groups": {"content": 1},
            "platform": "GitHub"
        },
        "chrome_generic": {
            "regex": r"^(.+?) - Google Chrome$",
            "groups": {"content": 1}
        },
        "discord": {
            "regex": r"^(.+?) - Discord$",
            "groups": {"channel": 1}
        },
        "spotify": {
            "regex": r"^(.+?) - (.+?)$",  # Song - Artist
            "groups": {"song": 1, "artist": 2},
            "platform": "Spotify"
        }
    }
    
    # Known file extensions
    FILE_EXTENSIONS = {
        ".py": "Python",
        ".js": "JavaScript", 
        ".ts": "TypeScript",
        ".tsx": "React TypeScript",
        ".jsx": "React JavaScript",
        ".html": "HTML",
        ".css": "CSS",
        ".json": "JSON",
        ".md": "Markdown",
        ".cpp": "C++",
        ".c": "C",
        ".rs": "Rust",
        ".go": "Go",
        ".java": "Java"
    }
    
    # URL domain patterns
    URL_DOMAINS = {
        "youtube": "YouTube",
        "github": "GitHub",
        "stackoverflow": "Stack Overflow",
        "reddit": "Reddit",
        "twitter": "Twitter",
        "twitch": "Twitch",
        "discord": "Discord"
    }
    
    def parse(self, title: str, app_name: str = "") -> ParsedTitle:
        """Parse a window title into structured components."""
        result = ParsedTitle(raw_title=title)
        
        if not title:
            return result
        
        title_lower = title.lower()
        app_lower = app_name.lower() if app_name else ""
        
        # Extract app name from title or use provided
        result.app_name = app_name or self._extract_app_name(title)
        
        # Check for file patterns
        file_match = re.search(r'(\w+\.(\w+))', title)
        if file_match:
            result.file_name = file_match.group(1)
            ext = "." + file_match.group(2).lower()
            if ext in self.FILE_EXTENSIONS:
                result.file_extension = ext
        
        # Check for URL/platform patterns
        for domain, platform in self.URL_DOMAINS.items():
            if domain in title_lower:
                result.platform = platform
                result.url_domain = domain
                break
        
        # Extract content title (what the user is looking at)
        if " - " in title:
            parts = title.split(" - ")
            # Usually the first part is the content name
            if len(parts) >= 2:
                result.content_title = parts[0].strip()
        
        # Check for VS Code project pattern
        if "visual studio code" in title_lower:
            match = re.search(r'^(.+?) - (.+?) - Visual Studio Code', title)
            if match:
                result.file_name = match.group(1)
                result.project_name = match.group(2)
        
        return result
    
    def _extract_app_name(self, title: str) -> Optional[str]:
        """Extract app name from title if not provided."""
        # Common patterns: "Content - AppName" or "AppName - Content"
        if " - " in title:
            parts = title.split(" - ")
            # Last part is often the app name
            last_part = parts[-1].strip()
            # Check if it looks like an app name (capitalized, short)
            if len(last_part) < 30 and last_part[0].isupper():
                return last_part
        return None


class AudioAnalyzer:
    """Analyze audio features locally without AI."""
    
    def __init__(self):
        self.last_volume = 0.0
        self.volume_history: List[float] = []
        self.history_max = 100
    
    def analyze(self, audio_bytes: Optional[bytes], sample_rate: int = 44100) -> AudioFeatures:
        """Analyze audio bytes and extract features."""
        result = AudioFeatures()
        
        if not audio_bytes or len(audio_bytes) < 100:
            result.is_silent = True
            return result
        
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            
            if len(audio_data) == 0:
                return result
            
            # Normalize to -1.0 to 1.0
            audio_data = audio_data / 32768.0
            
            # Calculate volume (RMS)
            rms = np.sqrt(np.mean(audio_data ** 2))
            result.volume_level = min(1.0, rms * 10)  # Scale for visibility
            result.has_audio = result.volume_level > 0.01
            result.is_silent = result.volume_level < 0.02
            
            # Calculate volume delta
            result.volume_delta = result.volume_level - self.last_volume
            self.last_volume = result.volume_level
            
            # Store in history
            self.volume_history.append(result.volume_level)
            if len(self.volume_history) > self.history_max:
                self.volume_history.pop(0)
            
            # Frequency analysis for music vs speech detection
            if len(audio_data) >= 1024 and result.has_audio:
                result.is_music_like, result.is_speech_like = self._analyze_frequency(
                    audio_data, sample_rate
                )
            
        except Exception as e:
            print(f"[Semantic] Audio analysis error: {e}")
        
        return result
    
    def _analyze_frequency(self, audio_data: np.ndarray, sample_rate: int) -> tuple:
        """Simple frequency analysis to distinguish music from speech."""
        try:
            # Use FFT to get frequency spectrum
            fft = np.abs(np.fft.rfft(audio_data[:4096]))
            freqs = np.fft.rfftfreq(4096, 1/sample_rate)
            
            # Voice frequencies: 80-1100 Hz (fundamental + harmonics)
            voice_mask = (freqs >= 80) & (freqs <= 1100)
            voice_energy = np.sum(fft[voice_mask])
            
            # Music has broader frequency distribution
            total_energy = np.sum(fft)
            
            if total_energy > 0:
                voice_ratio = voice_energy / total_energy
                # High voice ratio = speech-like
                is_speech = voice_ratio > 0.5
                # Broad distribution = music-like
                is_music = voice_ratio < 0.4 and total_energy > 100
                return is_music, is_speech
            
        except Exception:
            pass
        
        return False, False


class VisualAnalyzer:
    """Analyze visual features from screen captures."""
    
    def __init__(self):
        self.last_frame_hash = None
        self.change_history: List[float] = []
        self.history_max = 20
    
    def analyze(self, current_diff: float, previous_diff: float = 0.0) -> VisualFeatures:
        """
        Analyze visual change patterns.
        Uses pre-computed diff values from main.py's visual difference calculation.
        """
        result = VisualFeatures()
        result.change_percentage = current_diff
        
        # Track history
        self.change_history.append(current_diff)
        if len(self.change_history) > self.history_max:
            self.change_history.pop(0)
        
        # Determine stability
        result.is_stable = current_diff < 2.0
        
        # Detect video playback (consistent moderate-high change)
        if len(self.change_history) >= 5:
            recent_avg = np.mean(self.change_history[-5:])
            recent_std = np.std(self.change_history[-5:])
            
            # Video: consistently changing (avg > 3%) but not erratically (std < 10%)
            result.is_video_playing = recent_avg > 3.0 and recent_std < 15.0
        
        return result


class SemanticLayer:
    """
    Main semantic layer that combines all analyzers.
    Extracts structured features from raw observation data.
    """
    
    def __init__(self):
        self.title_parser = TitleParser()
        self.audio_analyzer = AudioAnalyzer()
        self.visual_analyzer = VisualAnalyzer()
    
    def extract_features(self, 
                        window_title: str,
                        app_name: str = "",
                        audio_bytes: Optional[bytes] = None,
                        visual_diff: float = 0.0,
                        has_keyboard_input: bool = False,
                        has_mouse_input: bool = False) -> ContextFeatures:
        """
        Extract all semantic features from observation data.
        Returns a structured ContextFeatures object.
        """
        import time
        
        # Parse title
        title_features = self.title_parser.parse(window_title, app_name)
        
        # Analyze audio
        audio_features = self.audio_analyzer.analyze(audio_bytes)
        
        # Analyze visual
        visual_features = self.visual_analyzer.analyze(visual_diff)
        
        # Combine into context
        context = ContextFeatures(
            title=title_features,
            audio=audio_features,
            visual=visual_features,
            timestamp=time.time()
        )
        
        # Derive activity type
        context.activity_type = self._classify_activity(
            title_features, audio_features, visual_features,
            has_keyboard_input, has_mouse_input
        )
        
        # Determine if passive (consuming content)
        context.is_passive = (
            visual_features.is_video_playing or
            (audio_features.is_music_like and not has_keyboard_input) or
            title_features.platform in ["YouTube", "Twitch", "Netflix"]
        )
        
        # Determine if focused (deep work)
        context.is_focused = (
            has_keyboard_input and
            not audio_features.has_audio and
            visual_features.is_stable and
            title_features.file_extension in TitleParser.FILE_EXTENSIONS
        )
        
        return context
    
    def _classify_activity(self,
                          title: ParsedTitle,
                          audio: AudioFeatures,
                          visual: VisualFeatures,
                          has_kb: bool,
                          has_mouse: bool) -> str:
        """Classify the activity type based on features."""
        
        # Coding
        if title.file_extension and title.file_extension in TitleParser.FILE_EXTENSIONS:
            return "coding"
        
        # Media consumption
        if title.platform in ["YouTube", "Twitch", "Netflix"]:
            return "media"
        if visual.is_video_playing and audio.is_music_like:
            return "media"
        
        # Music
        if title.platform == "Spotify" or (audio.is_music_like and not visual.is_video_playing):
            return "music"
        
        # Social/Communication
        if title.platform in ["Discord", "Slack"] or title.app_name in ["Discord", "Slack"]:
            return "communication"
        
        # Research/Browsing
        if title.platform in ["GitHub", "Stack Overflow"]:
            return "research"
        if title.url_domain and has_mouse and not has_kb:
            return "browsing"
        
        # Gaming (high visual change, possibly audio, but no typing)
        if visual.is_video_playing and audio.has_audio and not has_kb:
            return "gaming"
        
        # Default
        return "general"


# Singleton instance
semantic_layer = SemanticLayer()
