"""
Knowledge Gate - The gatekeeper between observations and Gemini.

This layer checks all knowledge bases in priority order before
allowing a Gemini call. If the context is already known, it returns
cached/templated responses without any cloud API usage.

Priority Chain: User KB → Gemini KB → Core KB → (Unknown → Queue for Gemini)
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

import database
from semantic_layer import ContextFeatures
from fog_layer import Episode


class GateDecision(Enum):
    """Decision made by the Knowledge Gate."""
    KNOWN_USE_CACHE = "known_cache"      # Found in KB, use cached reaction
    KNOWN_USE_TEMPLATE = "known_template" # Found in KB, use template
    KNOWN_SKIP = "known_skip"            # Known but no reaction needed
    UNKNOWN_QUEUE = "unknown_queue"      # Unknown, queue for batch processing
    UNKNOWN_URGENT = "unknown_urgent"    # Unknown and significant, process now


@dataclass
class GateResult:
    """Result from the Knowledge Gate."""
    decision: GateDecision
    source: Optional[str] = None  # "user", "gemini", "core", None
    reaction: Optional[str] = None
    context_info: Optional[Dict[str, Any]] = None
    behavior_policy: Optional[Dict[str, Any]] = None
    should_call_gemini: bool = False
    reason: str = ""


class KnowledgeGate:
    """
    The Knowledge Gate intercepts all observations before Gemini.
    
    It answers: "Do we already know enough to react to this?"
    """
    
    def __init__(self):
        self._stats = {
            "total_checks": 0,
            "known_hits": 0,
            "unknown_queued": 0,
            "unknown_urgent": 0,
            "gemini_saved": 0
        }
    
    def check(self, 
              window_title: str,
              app_name: str,
              features: ContextFeatures,
              episode: Optional[Episode] = None,
              force_gemini: bool = False) -> GateResult:
        """
        Check if this context is known and decide how to handle it.
        
        Args:
            window_title: Current window title
            app_name: Current app name
            features: Extracted semantic features
            episode: Current episode (for context)
            force_gemini: If True, always queue for Gemini
            
        Returns:
            GateResult with decision and any cached data
        """
        self._stats["total_checks"] += 1
        
        # Force Gemini if requested (e.g., user asked a question)
        if force_gemini:
            return GateResult(
                decision=GateDecision.UNKNOWN_URGENT,
                should_call_gemini=True,
                reason="Forced Gemini call requested"
            )
        
        # 1. Query the knowledge priority chain
        kb_result = database.lookup_app_in_kb(app_name, window_title)
        
        if kb_result["found"]:
            self._stats["known_hits"] += 1
            self._stats["gemini_saved"] += 1
            
            # Get behavior policy if available
            behavior_name = None
            if kb_result["app_info"]:
                behavior_name = kb_result["app_info"].get("behavior")
            elif kb_result["context_info"]:
                behavior_name = kb_result["context_info"].get("behavior")
            
            behavior_policy = None
            if behavior_name:
                behavior_policy = database.get_behavior_policy(behavior_name)
            
            # Determine if we have a reaction to use
            reaction = kb_result["reaction"]
            
            if reaction:
                return GateResult(
                    decision=GateDecision.KNOWN_USE_TEMPLATE,
                    source=kb_result["source"],
                    reaction=reaction,
                    context_info=kb_result.get("context_info") or kb_result.get("app_info"),
                    behavior_policy=behavior_policy,
                    should_call_gemini=False,
                    reason=f"Found in {kb_result['source']} KB with reaction"
                )
            else:
                # Known but no specific reaction (e.g., generic browser)
                return GateResult(
                    decision=GateDecision.KNOWN_SKIP,
                    source=kb_result["source"],
                    context_info=kb_result.get("context_info") or kb_result.get("app_info"),
                    behavior_policy=behavior_policy,
                    should_call_gemini=False,
                    reason=f"Found in {kb_result['source']} KB, no reaction needed"
                )
        
        # 2. Not found in any KB - this is genuinely unknown
        
        # Determine urgency based on features
        is_urgent = self._assess_urgency(features, episode)
        
        if is_urgent:
            self._stats["unknown_urgent"] += 1
            return GateResult(
                decision=GateDecision.UNKNOWN_URGENT,
                should_call_gemini=True,
                reason="Unknown context with high significance"
            )
        else:
            self._stats["unknown_queued"] += 1
            return GateResult(
                decision=GateDecision.UNKNOWN_QUEUE,
                should_call_gemini=False,  # Will be batched later
                reason="Unknown context, queued for batch processing"
            )
    
    def _assess_urgency(self, features: ContextFeatures, episode: Optional[Episode]) -> bool:
        """
        Determine if an unknown context is urgent enough for immediate Gemini.
        
        Urgent conditions:
        - User is actively focused (coding, writing)
        - First observation of a new episode
        - Significant activity shift
        """
        # Focused work is high priority
        if features.is_focused:
            return True
        
        # First observation of new episode
        if episode and episode.observation_count <= 1:
            return True
        
        # Active creation activities
        if features.activity_type in ["coding", "writing"]:
            return True
        
        # Default: not urgent, queue for batch
        return False
    
    def get_capability_routing(self, task: str) -> Dict[str, Any]:
        """Get capability routing from Core KB."""
        return database.get_capability_routing(task)
    
    def should_use_gemini_for_task(self, task: str) -> bool:
        """Check if a specific task requires Gemini."""
        routing = self.get_capability_routing(task)
        requires = routing.get("requires_gemini", True)
        
        if isinstance(requires, bool):
            return requires
        elif requires == "if_unknown":
            return False  # Will be determined by check()
        else:
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge gate statistics."""
        total = self._stats["total_checks"]
        if total > 0:
            hit_rate = (self._stats["known_hits"] / total) * 100
        else:
            hit_rate = 0
        
        return {
            **self._stats,
            "hit_rate_percent": round(hit_rate, 1)
        }
    
    def reset_stats(self):
        """Reset statistics (e.g., for new session)."""
        self._stats = {
            "total_checks": 0,
            "known_hits": 0,
            "unknown_queued": 0,
            "unknown_urgent": 0,
            "gemini_saved": 0
        }


# Singleton instance
knowledge_gate = KnowledgeGate()
