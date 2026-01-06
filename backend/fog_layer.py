"""
Fog Layer - Episodic aggregation for observations.

Instead of processing every observation in real-time, the Fog Layer
accumulates observations into "Episodes" (5-10 minute windows) and
processes them as coherent units.

This dramatically reduces Gemini calls by:
1. Batching similar observations together
2. Only surfacing significant episode transitions
3. Providing richer context when analysis IS needed
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from collections import deque
from enum import Enum

from semantic_layer import ContextFeatures, semantic_layer


class EpisodeState(Enum):
    """State of an episode."""
    ACTIVE = "active"       # Currently accumulating
    CLOSED = "closed"       # Ready for processing
    PROCESSED = "processed" # Already sent for analysis


@dataclass
class EpisodeObservation:
    """A single observation within an episode."""
    timestamp: float
    window_title: str
    app_name: str
    features: ContextFeatures
    has_image: bool = False
    has_audio: bool = False


@dataclass
class Episode:
    """
    An episode is a coherent window of user activity.
    Episodes group related observations together.
    """
    id: str
    start_time: float
    end_time: Optional[float] = None
    state: EpisodeState = EpisodeState.ACTIVE
    
    # Primary context (what defines this episode)
    primary_app: Optional[str] = None
    primary_activity: Optional[str] = None
    primary_platform: Optional[str] = None
    
    # Observations within this episode
    observations: List[EpisodeObservation] = field(default_factory=list)
    
    # Aggregated features
    total_duration: float = 0.0
    keyboard_active: bool = False
    mouse_active: bool = False
    is_passive: bool = False
    is_focused: bool = False
    
    # For Gemini processing
    selected_image_bytes: Optional[bytes] = None
    selected_audio_bytes: Optional[bytes] = None
    
    @property
    def observation_count(self) -> int:
        return len(self.observations)
    
    @property
    def duration_minutes(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) / 60.0
        return (time.time() - self.start_time) / 60.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of this episode for logging/processing."""
        return {
            "id": self.id,
            "duration_minutes": round(self.duration_minutes, 1),
            "observations": self.observation_count,
            "app": self.primary_app,
            "activity": self.primary_activity,
            "platform": self.primary_platform,
            "passive": self.is_passive,
            "focused": self.is_focused
        }


class FogLayer:
    """
    Manages episode accumulation and transitions.
    
    Key behaviors:
    - New episode starts when context changes significantly
    - Episodes close after max duration or on major context shift
    - Only closed episodes are sent for Gemini processing
    """
    
    def __init__(self,
                 max_episode_duration: float = 600.0,  # 10 minutes
                 min_episode_duration: float = 30.0,   # 30 seconds
                 context_change_threshold: float = 0.5):
        
        self.max_duration = max_episode_duration
        self.min_duration = min_episode_duration
        self.context_threshold = context_change_threshold
        
        self.current_episode: Optional[Episode] = None
        self.episode_history: deque[Episode] = deque(maxlen=50)
        self.pending_episodes: List[Episode] = []  # Ready for processing
        
        self._episode_counter = 0
    
    def add_observation(self,
                       window_title: str,
                       app_name: str,
                       features: ContextFeatures,
                       image_bytes: Optional[bytes] = None,
                       audio_bytes: Optional[bytes] = None) -> Optional[Episode]:
        """
        Add an observation to the current episode.
        
        Returns: The closed episode if one was just closed, None otherwise.
        """
        now = time.time()
        closed_episode = None
        
        # Create observation
        obs = EpisodeObservation(
            timestamp=now,
            window_title=window_title,
            app_name=app_name,
            features=features,
            has_image=image_bytes is not None,
            has_audio=audio_bytes is not None
        )
        
        # Check if we need a new episode
        needs_new_episode = False
        
        if self.current_episode is None:
            needs_new_episode = True
        else:
            # Check duration
            episode_duration = now - self.current_episode.start_time
            if episode_duration > self.max_duration:
                needs_new_episode = True
            
            # Check context change
            elif self._is_significant_change(features):
                # Only close if min duration met
                if episode_duration > self.min_duration:
                    needs_new_episode = True
        
        # Close current episode if needed
        if needs_new_episode and self.current_episode is not None:
            closed_episode = self._close_episode()
        
        # Start new episode if needed
        if self.current_episode is None:
            self._start_episode(obs, features)
        
        # Add observation to current episode
        self.current_episode.observations.append(obs)
        
        # Update aggregated features
        self._update_episode_aggregates(features)
        
        # Store representative samples for Gemini (if eventually needed)
        if image_bytes and self.current_episode.selected_image_bytes is None:
            self.current_episode.selected_image_bytes = image_bytes
        if audio_bytes and self.current_episode.selected_audio_bytes is None:
            self.current_episode.selected_audio_bytes = audio_bytes
        
        return closed_episode
    
    def force_close_current(self) -> Optional[Episode]:
        """Force close the current episode (e.g., on app shutdown)."""
        if self.current_episode:
            return self._close_episode()
        return None
    
    def get_pending_episodes(self) -> List[Episode]:
        """Get episodes ready for processing."""
        episodes = self.pending_episodes.copy()
        self.pending_episodes.clear()
        return episodes
    
    def get_current_episode_summary(self) -> Optional[Dict[str, Any]]:
        """Get summary of current episode."""
        if self.current_episode:
            return self.current_episode.get_summary()
        return None
    
    def _start_episode(self, first_obs: EpisodeObservation, features: ContextFeatures):
        """Start a new episode."""
        self._episode_counter += 1
        episode_id = f"ep_{self._episode_counter}_{int(time.time())}"
        
        self.current_episode = Episode(
            id=episode_id,
            start_time=time.time(),
            primary_app=first_obs.app_name,
            primary_activity=features.activity_type,
            primary_platform=features.title.platform
        )
        
        print(f"[Fog] Started episode {episode_id}: {first_obs.app_name}")
    
    def _close_episode(self) -> Episode:
        """Close the current episode and queue it."""
        episode = self.current_episode
        episode.end_time = time.time()
        episode.state = EpisodeState.CLOSED
        episode.total_duration = episode.end_time - episode.start_time
        
        # Add to history and pending
        self.episode_history.append(episode)
        self.pending_episodes.append(episode)
        
        print(f"[Fog] Closed episode {episode.id}: "
              f"{episode.observation_count} obs, "
              f"{episode.duration_minutes:.1f} min")
        
        self.current_episode = None
        return episode
    
    def _is_significant_change(self, features: ContextFeatures) -> bool:
        """Determine if the new observation is a significant context change."""
        if not self.current_episode:
            return True
        
        # App change is always significant
        if features.title.app_name and features.title.app_name != self.current_episode.primary_app:
            return True
        
        # Activity type change
        if features.activity_type != self.current_episode.primary_activity:
            return True
        
        # Platform change (e.g., YouTube to GitHub)
        if features.title.platform and features.title.platform != self.current_episode.primary_platform:
            return True
        
        # Passive → Active transition
        if self.current_episode.is_passive and not features.is_passive:
            return True
        
        return False
    
    def _update_episode_aggregates(self, features: ContextFeatures):
        """Update aggregated features of current episode."""
        ep = self.current_episode
        
        # Update passive/focused based on majority of observations
        if features.is_passive:
            ep.is_passive = True
        if features.is_focused:
            ep.is_focused = True
        
        # Update activity if more specific
        if features.activity_type and features.activity_type != "general":
            ep.primary_activity = features.activity_type
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fog layer statistics."""
        return {
            "total_episodes": self._episode_counter,
            "current_episode": self.current_episode.get_summary() if self.current_episode else None,
            "pending_count": len(self.pending_episodes),
            "history_count": len(self.episode_history)
        }


# Singleton instance
fog_layer = FogLayer()
