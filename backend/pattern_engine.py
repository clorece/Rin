"""
Pattern recognition engine for Rin's learning capabilities.
Analyzes activity data to detect user patterns and generate insights.
"""

import database
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional


class PatternEngine:
    """Analyzes activity data to detect and learn user patterns."""
    
    def __init__(self):
        self._insight_cache = []
        self._last_analysis = None
    
    def analyze_all(self, force: bool = False) -> list[dict]:
        """Run all pattern analyses and return insights."""
        # Throttle to once per minute unless forced
        if not force and self._last_analysis:
            if datetime.now() - self._last_analysis < timedelta(minutes=1):
                return self._insight_cache
        
        insights = []
        
        # Analyze different pattern types
        insights.extend(self._analyze_app_frequency())
        insights.extend(self._analyze_time_patterns())
        insights.extend(self._analyze_file_patterns())
        insights.extend(self._analyze_category_distribution())
        
        self._insight_cache = insights
        self._last_analysis = datetime.now()
        
        return insights
    
    def _analyze_app_frequency(self) -> list[dict]:
        """Detect most used applications."""
        insights = []
        stats = database.get_app_activity_stats(days=7)
        
        if not stats.get("top_apps"):
            return insights
        
        top_apps = stats["top_apps"][:5]
        
        for app in top_apps:
            hours = app["total_seconds"] / 3600 if app["total_seconds"] else 0
            if hours >= 1:
                pattern_key = f"app_frequency:{app['app_name']}"
                confidence = min(0.9, hours / 20)  # Max out at 20 hours
                
                database.save_pattern(
                    pattern_type="frequency",
                    pattern_key=pattern_key,
                    pattern_data={
                        "app_name": app['app_name'],
                        "hours": round(hours, 1),
                        "sessions": app['sessions']
                    },
                    confidence=confidence
                )
                
                insights.append({
                    "type": "app_frequency",
                    "app": app['app_name'],
                    "hours": round(hours, 1),
                    "message": f"You've spent about {round(hours, 1)} hours in {app['app_name']} this week."
                })
        
        return insights
    
    def _analyze_time_patterns(self) -> list[dict]:
        """Detect time-of-day usage patterns."""
        insights = []
        
        # This would require more granular timestamp analysis
        # For now, we'll use category distribution as a proxy
        stats = database.get_app_activity_stats(days=7)
        categories = stats.get("categories", [])
        
        if categories:
            dominant = categories[0]
            if dominant.get("total_seconds", 0) > 7200:  # More than 2 hours
                hours = dominant["total_seconds"] / 3600
                insights.append({
                    "type": "category_dominance",
                    "category": dominant["category"],
                    "hours": round(hours, 1),
                    "message": f"Your primary focus this week has been {dominant['category']} ({round(hours, 1)} hours)."
                })
        
        return insights
    
    def _analyze_file_patterns(self) -> list[dict]:
        """Detect file usage patterns."""
        insights = []
        stats = database.get_file_activity_stats(days=7)
        
        # Top file types
        file_types = stats.get("file_types", [])
        if file_types:
            top_type = file_types[0]
            if top_type.get("count", 0) >= 10:
                insights.append({
                    "type": "file_type_frequency",
                    "file_type": top_type["file_type"],
                    "count": top_type["count"],
                    "message": f"You work with {top_type['file_type']} files most frequently ({top_type['count']} interactions this week)."
                })
        
        # Top directories
        top_dirs = stats.get("top_directories", [])
        if top_dirs:
            top_dir = top_dirs[0]
            if top_dir.get("count", 0) >= 5:
                insights.append({
                    "type": "directory_frequency",
                    "directory": top_dir["directory"],
                    "count": top_dir["count"],
                    "message": f"Your most active project folder has {top_dir['count']} recent file changes."
                })
        
        return insights
    
    def _analyze_category_distribution(self) -> list[dict]:
        """Analyze work/play balance."""
        insights = []
        stats = database.get_app_activity_stats(days=7)
        categories = stats.get("categories", [])
        
        if len(categories) < 2:
            return insights
        
        total_time = sum(c.get("total_seconds", 0) for c in categories)
        if total_time < 3600:  # Less than 1 hour total - not enough data
            return insights
        
        category_pct = {}
        for cat in categories:
            pct = (cat.get("total_seconds", 0) / total_time) * 100
            category_pct[cat["category"]] = round(pct, 1)
        
        # Store as pattern
        database.save_pattern(
            pattern_type="distribution",
            pattern_key="weekly_category_distribution",
            pattern_data=category_pct,
            confidence=0.7
        )
        
        return insights
    
    def get_insights_for_rin(self, max_insights: int = 3) -> list[str]:
        """Get human-readable insights for Rin to share with user."""
        insights = self.analyze_all()
        
        # Sort by relevance/interest
        messages = [i["message"] for i in insights if "message" in i]
        
        return messages[:max_insights]
    
    def get_context_for_response(self) -> str:
        """Generate context string about user patterns for LLM prompts."""
        stats_app = database.get_app_activity_stats(days=7)
        stats_file = database.get_file_activity_stats(days=7)
        
        context_parts = []
        
        # Top apps
        top_apps = stats_app.get("top_apps", [])[:3]
        if top_apps:
            app_names = [a["app_name"] for a in top_apps]
            context_parts.append(f"User frequently uses: {', '.join(app_names)}")
        
        # Categories
        categories = stats_app.get("categories", [])[:3]
        if categories:
            cat_names = [c["category"] for c in categories]
            context_parts.append(f"User focuses on: {', '.join(cat_names)}")
        
        # File types
        file_types = stats_file.get("file_types", [])[:3]
        if file_types:
            types = [f["file_type"] for f in file_types if f["file_type"]]
            if types:
                context_parts.append(f"User works with: {', '.join(types)} files")
        
        return " ".join(context_parts) if context_parts else ""


# Singleton instance
pattern_engine = PatternEngine()
