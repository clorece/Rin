import os
import datetime

def log_activity(activity_type, content):
    """
    Logs unified activity to logs/activity.log.
    """
    try:
        # Assuming we are in backend/ directory, log is in ../logs/
        # Use absolute path calculation based on this file's location
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "..", "logs")
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_path = os.path.join(log_dir, "activity.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{activity_type}] {content}\n")
    except Exception as e:
        print(f"Failed to log activity: {e}")

def clear_activity_log():
    """Clears the activity log on startup."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "..", "logs")
        log_path = os.path.join(log_dir, "activity.log")
        
        if os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
    except Exception as e:
        print(f"Failed to clear activity log: {e}")
