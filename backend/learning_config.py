"""
Learning configuration for Rin's activity tracking and intelligence features.
User-configurable settings for privacy and behavior.
"""

import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "learning_config.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "track_files": True,
    "track_apps": True,
    "watched_directories": [os.path.expanduser("~")],
    "excluded_paths": [
        "**/node_modules/**",
        "**/.git/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/AppData/Local/Temp/**",
        "**/AppData/Local/**/Cache/**",
        "**/AppData/Local/**/Code Cache/**",
        "**/AppData/Local/**/GPUCache/**",
        "**/AppData/Local/**/ShaderCache/**",
        "**/AppData/Roaming/Mozilla/**",
        "**/AppData/Roaming/zen/**",
        "**/AppData/Local/Google/Chrome/**",
        "**/AppData/Local/Microsoft/Edge/**",
        "**/AppData/Local/BraveSoftware/**",
        "**/*.tmp",
        "**/*.log",
        "**/*.sqlite-wal",
        "**/*.sqlite-shm",
        "**/*.sqlite-journal",
        "**/*-journal"
    ],
    "excluded_apps": [
        "SearchUI.exe",
        "ShellExperienceHost.exe",
        "LockApp.exe",
        "SystemSettings.exe",
        "ApplicationFrameHost.exe"
    ],
    "data_retention_days": 30,
    "share_insights": True,  # Rin mentions what she learns
    "min_focus_seconds": 2,  # Minimum time to count as "focused" on app
}


def get_config() -> dict:
    """Load configuration, creating default if not exists."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # Merge with defaults (user config takes precedence)
                config = {**DEFAULT_CONFIG, **user_config}
                return config
        except Exception as e:
            print(f"[LearningConfig] Error loading config: {e}, using defaults")
    
    # Save defaults if no config exists
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Save configuration to disk."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"[LearningConfig] Error saving config: {e}")
        return False


def update_config(updates: dict) -> dict:
    """Update specific config values and save."""
    config = get_config()
    config.update(updates)
    save_config(config)
    return config


def is_path_excluded(path: str, excluded_patterns: list = None) -> bool:
    """Check if a path matches any exclusion pattern."""
    import fnmatch
    
    if excluded_patterns is None:
        excluded_patterns = get_config().get("excluded_paths", [])
    
    path_normalized = path.replace("\\", "/")
    
    for pattern in excluded_patterns:
        if fnmatch.fnmatch(path_normalized, pattern):
            return True
    
    return False


def is_app_excluded(app_name: str, excluded_apps: list = None) -> bool:
    """Check if an app should be excluded from tracking."""
    if excluded_apps is None:
        excluded_apps = get_config().get("excluded_apps", [])
    
    return app_name.lower() in [a.lower() for a in excluded_apps]
