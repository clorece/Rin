import sqlite3
import json
from datetime import datetime, timedelta
import os
from logger import log_system_change

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "thea.db")

def get_db_connection():
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Memories: Stores what Thea has seen or talked about
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,  -- 'observation' or 'chat'
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            meta TEXT -- JSON string for extra data (e.g. image path, sender)
        )
    ''')
    
    # System State: Stores mood, last active, etc.
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # File activity tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS file_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER,
            file_type TEXT,
            directory TEXT
        )
    ''')
    
    # Application/window tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS app_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            window_title TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER,
            category TEXT
        )
    ''')
    
    # Learned patterns
    c.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            usage_count INTEGER DEFAULT 0,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Response cache for API cost reduction
    c.execute('''
        CREATE TABLE IF NOT EXISTS response_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_hash TEXT NOT NULL,
            context_type TEXT NOT NULL,
            response TEXT NOT NULL,
            success_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for faster queries
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_activity_path ON file_activity(path)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_activity_timestamp ON file_activity(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_app_activity_app ON app_activity(app_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_app_activity_timestamp ON app_activity(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_response_cache_hash ON response_cache(context_hash)')
    
    # ============== Knowledge Graph Tables ==============
    
    # Core user understanding - what Rin learns about the user
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,       -- 'preference', 'workflow', 'interest', 'habit', 'emotional'
            key TEXT NOT NULL,            -- What this knowledge is about
            value TEXT NOT NULL,          -- The learned information
            confidence REAL DEFAULT 0.5,  -- 0.0 to 1.0
            source TEXT DEFAULT 'observed', -- 'observed', 'stated', 'inferred'
            evidence_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, key)
        )
    ''')
    
    # Rin's insights - observations and suggestions she generates
    c.execute('''
        CREATE TABLE IF NOT EXISTS rin_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_type TEXT NOT NULL,   -- 'observation', 'suggestion', 'pattern', 'concern'
            content TEXT NOT NULL,        -- The insight text
            context TEXT,                 -- What triggered this insight (JSON)
            relevance_score REAL DEFAULT 0.5,
            shared_with_user INTEGER DEFAULT 0,  -- 0 = not shared, 1 = shared
            user_feedback TEXT,           -- 'positive', 'negative', 'dismissed', null
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Context embeddings - for similarity matching
    c.execute('''
        CREATE TABLE IF NOT EXISTS context_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_hash TEXT NOT NULL UNIQUE,
            window_title TEXT,
            app_name TEXT,
            app_category TEXT,
            description TEXT,             -- Rin's description of this context
            embedding_data TEXT,          -- JSON array of embedding vector (or summary features)
            occurrence_count INTEGER DEFAULT 1,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Knowledge graph indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_knowledge_category ON user_knowledge(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_knowledge_confidence ON user_knowledge(confidence)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_rin_insights_type ON rin_insights(insight_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_rin_insights_shared ON rin_insights(shared_with_user)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_context_embeddings_hash ON context_embeddings(context_hash)')
    
    # ============== Staging Knowledge Base (Runtime Unknowns) ==============
    
    # Staging KB: Runtime unknowns processed by Gemini, awaiting developer classification
    c.execute('''
        CREATE TABLE IF NOT EXISTS staging_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_type TEXT NOT NULL,     -- 'pattern', 'reaction', 'context_mapping', 'extracted'
            context_signature TEXT,           -- app:title hash for matching
            content TEXT NOT NULL,            -- The actual knowledge (JSON)
            gemini_response TEXT,             -- Raw Gemini response that generated this
            is_general INTEGER DEFAULT 1,     -- 1 = general (promote to Gemini KB), 0 = user-specific
            promoted INTEGER DEFAULT 0,       -- 1 = already promoted to Gemini KB
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_staging_type ON staging_knowledge(knowledge_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_staging_promoted ON staging_knowledge(promoted)')
    
    conn.commit()
    conn.close()


# ============== Memory Functions ==============

def add_memory(mem_type, content, meta=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO memories (type, content, meta) VALUES (?, ?, ?)",
        (mem_type, content, json.dumps(meta) if meta else None)
    )
    conn.commit()
    conn.close()
    
    # Log system change for significant memories
    if mem_type != "observation":  # Observations are too noisy, log chat/thoughts
        log_system_change("MEMORY", "added", f"[{mem_type}] {content[:50]}...")

def get_recent_memories(limit=10):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows][::-1] # Return in chronological order


# ============== File Activity Functions ==============

def add_file_activity(path: str, action: str, file_type: str = None, 
                      directory: str = None, duration_seconds: int = None):
    """Log a file activity event."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO file_activity (path, action, file_type, directory, duration_seconds) 
           VALUES (?, ?, ?, ?, ?)""",
        (path, action, file_type, directory, duration_seconds)
    )
    conn.commit()
    conn.close()

def get_file_activity_stats(days: int = 7) -> dict:
    """Get file activity statistics for the past N days."""
    conn = get_db_connection()
    c = conn.cursor()
    
    cutoff = datetime.now() - timedelta(days=days)
    
    # Most active files
    c.execute("""
        SELECT path, COUNT(*) as count, MAX(timestamp) as last_accessed
        FROM file_activity 
        WHERE timestamp > ?
        GROUP BY path 
        ORDER BY count DESC 
        LIMIT 20
    """, (cutoff,))
    top_files = [dict(row) for row in c.fetchall()]
    
    # Most active directories
    c.execute("""
        SELECT directory, COUNT(*) as count
        FROM file_activity 
        WHERE timestamp > ? AND directory IS NOT NULL
        GROUP BY directory 
        ORDER BY count DESC 
        LIMIT 10
    """, (cutoff,))
    top_directories = [dict(row) for row in c.fetchall()]
    
    # File types distribution
    c.execute("""
        SELECT file_type, COUNT(*) as count
        FROM file_activity 
        WHERE timestamp > ? AND file_type IS NOT NULL
        GROUP BY file_type 
        ORDER BY count DESC 
        LIMIT 15
    """, (cutoff,))
    file_types = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return {
        "top_files": top_files,
        "top_directories": top_directories,
        "file_types": file_types
    }


# ============== App Activity Functions ==============

def add_app_activity(app_name: str, window_title: str = None,
                     duration_seconds: int = None, category: str = None):
    """Log an app focus event."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO app_activity (app_name, window_title, duration_seconds, category) 
           VALUES (?, ?, ?, ?)""",
        (app_name, window_title, duration_seconds, category)
    )
    conn.commit()
    conn.close()

def get_app_activity_stats(days: int = 7) -> dict:
    """Get app usage statistics for the past N days."""
    conn = get_db_connection()
    c = conn.cursor()
    
    cutoff = datetime.now() - timedelta(days=days)
    
    # Total time per app
    c.execute("""
        SELECT app_name, SUM(duration_seconds) as total_seconds, COUNT(*) as sessions
        FROM app_activity 
        WHERE timestamp > ? AND duration_seconds IS NOT NULL
        GROUP BY app_name 
        ORDER BY total_seconds DESC 
        LIMIT 15
    """, (cutoff,))
    top_apps = [dict(row) for row in c.fetchall()]
    
    # Time per category
    c.execute("""
        SELECT category, SUM(duration_seconds) as total_seconds
        FROM app_activity 
        WHERE timestamp > ? AND category IS NOT NULL AND duration_seconds IS NOT NULL
        GROUP BY category 
        ORDER BY total_seconds DESC
    """, (cutoff,))
    categories = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return {
        "top_apps": top_apps,
        "categories": categories
    }


# ============== Pattern Functions ==============

def save_pattern(pattern_type: str, pattern_key: str, pattern_data: dict, 
                 confidence: float = 0.5):
    """Save or update a learned pattern."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if pattern exists
    c.execute(
        "SELECT id, usage_count FROM patterns WHERE pattern_type = ? AND pattern_key = ?",
        (pattern_type, pattern_key)
    )
    existing = c.fetchone()
    
    if existing:
        # Update existing pattern
        c.execute("""
            UPDATE patterns 
            SET pattern_data = ?, confidence = ?, usage_count = usage_count + 1, last_seen = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(pattern_data), confidence, existing['id']))
    else:
        # Insert new pattern
        c.execute("""
            INSERT INTO patterns (pattern_type, pattern_key, pattern_data, confidence)
            VALUES (?, ?, ?, ?)
        """, (pattern_type, pattern_key, json.dumps(pattern_data), confidence))
    
    conn.commit()
    conn.close()
    
    action = "updated" if existing else "created"
    log_system_change("LEARNING", f"pattern_{action}", f"[{pattern_type}] {pattern_key} (conf: {confidence:.2f})")

def get_patterns(pattern_type: str = None, min_confidence: float = 0.0) -> list:
    """Get learned patterns, optionally filtered by type and confidence."""
    conn = get_db_connection()
    c = conn.cursor()
    
    if pattern_type:
        c.execute("""
            SELECT * FROM patterns 
            WHERE pattern_type = ? AND confidence >= ?
            ORDER BY confidence DESC, usage_count DESC
        """, (pattern_type, min_confidence))
    else:
        c.execute("""
            SELECT * FROM patterns 
            WHERE confidence >= ?
            ORDER BY confidence DESC, usage_count DESC
        """, (min_confidence,))
    
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['pattern_data'] = json.loads(d['pattern_data']) if d['pattern_data'] else {}
        result.append(d)
    return result


# ============== Response Cache Functions ==============

def cache_response(context_hash: str, context_type: str, response: str):
    """Cache a successful response for future use."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if already cached
    c.execute("SELECT id FROM response_cache WHERE context_hash = ?", (context_hash,))
    existing = c.fetchone()
    
    if existing:
        c.execute("""
            UPDATE response_cache 
            SET success_count = success_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (existing['id'],))
    else:
        c.execute("""
            INSERT INTO response_cache (context_hash, context_type, response)
            VALUES (?, ?, ?)
        """, (context_hash, context_type, response))
    
    conn.commit()
    conn.close()

def get_cached_response(context_hash: str) -> str | None:
    """Get a cached response if available."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT response FROM response_cache 
        WHERE context_hash = ?
    """, (context_hash,))
    row = c.fetchone()
    conn.close()
    
    return row['response'] if row else None


# ============== Cleanup Functions ==============

def cleanup_old_data(retention_days: int = 30):
    """Remove data older than retention period."""
    conn = get_db_connection()
    c = conn.cursor()
    
    cutoff = datetime.now() - timedelta(days=retention_days)
    
    c.execute("DELETE FROM file_activity WHERE timestamp < ?", (cutoff,))
    c.execute("DELETE FROM app_activity WHERE timestamp < ?", (cutoff,))
    
    conn.commit()
    deleted = c.rowcount
    conn.close()
    
    return deleted


# ============== Knowledge Graph Functions ==============

def learn_about_user(category: str, key: str, value: str, confidence: float = 0.5, 
                     source: str = "observed") -> bool:
    """Store or update knowledge about the user."""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Try to update existing knowledge
        c.execute("""
            UPDATE user_knowledge 
            SET value = ?, confidence = MIN(1.0, confidence + 0.1), 
                evidence_count = evidence_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE category = ? AND key = ?
        """, (value, category, key))
        
        if c.rowcount == 0:
            # Insert new knowledge
            c.execute("""
                INSERT INTO user_knowledge (category, key, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
            """, (category, key, value, confidence, source))
        
        conn.commit()
        
        action = "updated" if c.rowcount > 0 else "created" 
        # Note: rowcount logic in sqlite with UPSERT style update might vary, 
        # but here we separate Update vs Insert.
        # Actually logic above does Update then Insert.
        
        log_system_change("KNOWLEDGE", f"user_fact_learned", f"[{category}] {key}: {value} (conf: {confidence:.2f})")
        return True
    except Exception as e:
        print(f"[Knowledge] Error learning about user: {e}")
        return False
    finally:
        conn.close()


def get_user_knowledge(category: str = None, min_confidence: float = 0.0) -> list:
    """Retrieve knowledge about the user."""
    conn = get_db_connection()
    c = conn.cursor()
    
    if category:
        c.execute("""
            SELECT * FROM user_knowledge 
            WHERE category = ? AND confidence >= ?
            ORDER BY confidence DESC, updated_at DESC
        """, (category, min_confidence))
    else:
        c.execute("""
            SELECT * FROM user_knowledge 
            WHERE confidence >= ?
            ORDER BY confidence DESC, updated_at DESC
        """, (min_confidence,))
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_rin_insight(insight_type: str, content: str, context: dict = None, 
                    relevance_score: float = 0.5) -> int:
    """Store an insight Rin has generated."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO rin_insights (insight_type, content, context, relevance_score)
        VALUES (?, ?, ?, ?)
    """, (insight_type, content, json.dumps(context) if context else None, relevance_score))
    
    insight_id = c.lastrowid
    conn.commit()
    conn.close()
    
    log_system_change("INSIGHT", "generated", f"[{insight_type}] {content[:50]}... (score: {relevance_score:.2f})")
    
    return insight_id


def get_unshared_insights(min_relevance: float = 0.5, limit: int = 5) -> list:
    """Get insights Rin hasn't shared with the user yet."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT * FROM rin_insights 
        WHERE shared_with_user = 0 AND relevance_score >= ?
        ORDER BY relevance_score DESC, created_at DESC
        LIMIT ?
    """, (min_relevance, limit))
    
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['context'] = json.loads(d['context']) if d['context'] else None
        result.append(d)
    return result


def mark_insight_shared(insight_id: int, feedback: str = None):
    """Mark an insight as shared with the user."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        UPDATE rin_insights 
        SET shared_with_user = 1, user_feedback = ?
        WHERE id = ?
    """, (feedback, insight_id))
    
    conn.commit()
    conn.close()


def store_context_embedding(context_hash: str, window_title: str, app_name: str,
                            app_category: str, description: str, embedding_data: list = None):
    """Store or update a context embedding."""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            UPDATE context_embeddings 
            SET occurrence_count = occurrence_count + 1, last_seen = CURRENT_TIMESTAMP
            WHERE context_hash = ?
        """, (context_hash,))
        
        if c.rowcount == 0:
            c.execute("""
                INSERT INTO context_embeddings 
                (context_hash, window_title, app_name, app_category, description, embedding_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (context_hash, window_title, app_name, app_category, description,
                  json.dumps(embedding_data) if embedding_data else None))
        
        conn.commit()
    finally:
        conn.close()


def find_similar_context(window_title: str, app_name: str) -> dict | None:
    """Find a similar context based on window title and app."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Simple title-based matching for now
    # Future: Use embedding similarity
    c.execute("""
        SELECT * FROM context_embeddings 
        WHERE window_title = ? OR app_name = ?
        ORDER BY occurrence_count DESC
        LIMIT 1
    """, (window_title, app_name))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        d = dict(row)
        d['embedding_data'] = json.loads(d['embedding_data']) if d['embedding_data'] else None
        return d
    return None


def get_knowledge_summary() -> dict:
    """Get a summary of what Rin knows about the user."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Count by category
    c.execute("""
        SELECT category, COUNT(*) as count, AVG(confidence) as avg_confidence
        FROM user_knowledge
        GROUP BY category
    """)
    categories = {row['category']: {'count': row['count'], 'confidence': row['avg_confidence']} 
                  for row in c.fetchall()}
    
    # Total insights
    c.execute("SELECT COUNT(*) as total, SUM(shared_with_user) as shared FROM rin_insights")
    insights = c.fetchone()
    
    # Context coverage
    c.execute("SELECT COUNT(*) as total, SUM(occurrence_count) as occurrences FROM context_embeddings")
    contexts = c.fetchone()
    
    conn.close()
    
    return {
        "knowledge_categories": categories,
        "insights": {"total": insights['total'], "shared": insights['shared'] or 0},
        "contexts_learned": {"unique": contexts['total'], "total_occurrences": contexts['occurrences'] or 0}
    }


# ============== Knowledge Base Loader Functions ==============

# Cache for loaded KBs (avoid re-reading files every call)
_kb_cache = {
    "core": None,
    "gemini": None,
    "core_mtime": 0,
    "gemini_mtime": 0
}

def load_core_kb() -> dict:
    """Load the Core Knowledge Base from JSON file."""
    global _kb_cache
    kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "core_kb.json")
    
    try:
        mtime = os.path.getmtime(kb_path)
        if _kb_cache["core"] is None or mtime > _kb_cache["core_mtime"]:
            with open(kb_path, "r", encoding="utf-8") as f:
                _kb_cache["core"] = json.load(f)
                _kb_cache["core_mtime"] = mtime
        return _kb_cache["core"]
    except Exception as e:
        print(f"[KB] Failed to load core_kb.json: {e}")
        return {}


def load_gemini_kb() -> dict:
    """Load the Gemini Knowledge Base from JSON file."""
    global _kb_cache
    kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "gemini_kb.json")
    
    try:
        mtime = os.path.getmtime(kb_path)
        if _kb_cache["gemini"] is None or mtime > _kb_cache["gemini_mtime"]:
            with open(kb_path, "r", encoding="utf-8") as f:
                _kb_cache["gemini"] = json.load(f)
                _kb_cache["gemini_mtime"] = mtime
        return _kb_cache["gemini"]
    except Exception as e:
        print(f"[KB] Failed to load gemini_kb.json: {e}")
        return {}


def save_core_kb(data: dict) -> bool:
    """Save the Core Knowledge Base to JSON file."""
    global _kb_cache
    kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "core_kb.json")
    
    try:
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _kb_cache["core"] = data
        _kb_cache["core_mtime"] = os.path.getmtime(kb_path)
        print(f"[KB] Saved core_kb.json")
        return True
    except Exception as e:
        print(f"[KB] Failed to save core_kb.json: {e}")
        return False


def save_gemini_kb(data: dict) -> bool:
    """Save the Gemini Knowledge Base to JSON file."""
    global _kb_cache
    kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "gemini_kb.json")
    
    try:
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _kb_cache["gemini"] = data
        _kb_cache["gemini_mtime"] = os.path.getmtime(kb_path)
        print(f"[KB] Saved gemini_kb.json")
        return True
    except Exception as e:
        print(f"[KB] Failed to save gemini_kb.json: {e}")
        return False


def add_to_core_kb(section: str, key: str, data: dict) -> bool:
    """
    Add an entry to the Core Knowledge Base.
    
    Args:
        section: 'apps', 'contexts', 'behaviors', 'capabilities'
        key: Unique key for this entry
        data: The entry data
    """
    kb = load_core_kb()
    if not kb:
        return False
    
    if section not in kb:
        kb[section] = {}
    
    # Don't overwrite existing entries
    if key in kb[section]:
        print(f"[KB] Core KB already has {section}.{key}, skipping")
        return False
    
    kb[section][key] = data
    kb["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    
    success = save_core_kb(kb)
    if success:
        log_system_change("CORE_KB", "updated", f"Added/Updated [{section}] {key}")
    return success


def add_to_gemini_kb(section: str, key: str, data: dict) -> bool:
    """
    Add an entry to the Gemini Knowledge Base.
    
    Args:
        section: 'learned_patterns', 'learned_reactions', 'context_mappings', 'extracted_knowledge'
        key: Unique key for this entry
        data: The entry data
    """
    kb = load_gemini_kb()
    if not kb:
        return False
    
    if section not in kb:
        kb[section] = {}
    
    # Update if exists, otherwise add
    kb[section][key] = data
    kb["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    kb["metadata"]["total_entries"] = sum(
        len(v) for k, v in kb.items() 
        if isinstance(v, dict) and k not in ["version", "metadata"]
    )
    
    
    success = save_gemini_kb(kb)
    if success:
        log_system_change("GEMINI_KB", "updated", f"Added/Updated [{section}] {key}")
    return success


def promote_staging_to_gemini_kb(entry_id: int) -> bool:
    """
    Promote a staging KB entry directly to Gemini KB.
    Called automatically during learning or manually by developer.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT * FROM staging_knowledge WHERE id = ?", (entry_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return False
    
    entry = dict(row)
    content = json.loads(entry["content"]) if entry["content"] else {}
    
    # Determine section based on knowledge_type
    section_map = {
        "pattern": "learned_patterns",
        "reaction": "learned_reactions",
        "context_mapping": "context_mappings",
        "extracted": "extracted_knowledge"
    }
    section = section_map.get(entry["knowledge_type"], "learned_patterns")
    
    # Create key from context signature or id
    key = entry["context_signature"] or f"auto_{entry_id}"
    key = key.replace(":", "_").replace(" ", "_").lower()
    
    # Add to Gemini KB
    success = add_to_gemini_kb(section, key, {
        **content,
        "source": "staging",
        "staging_id": entry_id,
        "created_at": entry.get("created_at", datetime.now().isoformat())
    })
    
    if success:
        mark_staging_promoted(entry_id)
        # print(f"[KB] Promoted staging entry {entry_id} to Gemini KB") # Handled by logger now
        log_system_change("KNOWLEDGE_BASE", "promoted_staging", f"Entry {entry_id} promoted to {section}.{key}")
    
    return success


def auto_promote_confident_staging() -> int:
    """
    Automatically promote staging entries that appear frequently.
    Called during deep thinking to grow Gemini KB.
    Returns count of promoted entries.
    """
    entries = get_staging_kb_entries(promoted=False)
    promoted_count = 0
    
    # Group by context signature to find patterns
    signature_counts = {}
    for entry in entries:
        sig = entry.get("context_signature", "")
        if sig:
            signature_counts[sig] = signature_counts.get(sig, 0) + 1
    
    # Promote signatures that appear 3+ times (confident pattern)
    for sig, count in signature_counts.items():
        if count >= 3:
            # Find the first entry with this signature
            for entry in entries:
                if entry.get("context_signature") == sig and not entry.get("promoted"):
                    if promote_staging_to_gemini_kb(entry["id"]):
                        promoted_count += 1
                    break
    
    if promoted_count > 0:
        print(f"[KB] Auto-promoted {promoted_count} confident patterns to Gemini KB")
    
    return promoted_count

def add_to_staging_kb(knowledge_type: str, context_signature: str, 
                       content: dict, gemini_response: str = None,
                       is_general: bool = True) -> int:
    """Add knowledge from Gemini to staging for classification."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO staging_knowledge 
        (knowledge_type, context_signature, content, gemini_response, is_general)
        VALUES (?, ?, ?, ?, ?)
    """, (knowledge_type, context_signature, json.dumps(content), 
          gemini_response, 1 if is_general else 0))
    
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_staging_kb_entries(promoted: bool = False, limit: int = 100) -> list:
    """Get entries from staging KB."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT * FROM staging_knowledge 
        WHERE promoted = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (1 if promoted else 0, limit))
    
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['content'] = json.loads(d['content']) if d['content'] else {}
        result.append(d)
    return result


def mark_staging_promoted(entry_id: int):
    """Mark a staging entry as promoted to Gemini KB."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE staging_knowledge SET promoted = 1 WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


# ============== Knowledge Priority Chain Lookup ==============

def lookup_app_in_kb(app_name: str, window_title: str = "") -> dict:
    """
    Query all knowledge bases in priority order for app/context info.
    Priority: User KB → Gemini KB → Core KB
    
    Returns: {
        "found": bool,
        "source": "user" | "gemini" | "core" | None,
        "app_info": {...} or None,
        "context_info": {...} or None,
        "reaction": str or None
    }
    """
    result = {
        "found": False,
        "source": None,
        "app_info": None,
        "context_info": None,
        "reaction": None
    }
    
    app_lower = app_name.lower() if app_name else ""
    title_lower = window_title.lower() if window_title else ""
    
    # 1. Check User KB (context_embeddings for seen contexts)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM context_embeddings 
        WHERE app_name LIKE ? OR window_title LIKE ?
        ORDER BY occurrence_count DESC
        LIMIT 1
    """, (f"%{app_lower}%", f"%{title_lower}%"))
    user_match = c.fetchone()
    conn.close()
    
    if user_match:
        result["found"] = True
        result["source"] = "user"
        result["context_info"] = dict(user_match)
        # User KB doesn't store reactions directly, but has descriptions
        return result
    
    # 2. Check Gemini KB
    gemini_kb = load_gemini_kb()
    
    # Check learned_reactions
    for key, reaction_data in gemini_kb.get("learned_reactions", {}).items():
        if key.startswith("_"): continue  # Skip templates
        sig = reaction_data.get("context_signature", "").lower()
        if app_lower in sig or title_lower in sig:
            result["found"] = True
            result["source"] = "gemini"
            result["reaction"] = reaction_data.get("reaction_text")
            result["context_info"] = reaction_data
            return result
    
    # Check context_mappings
    for key, mapping in gemini_kb.get("context_mappings", {}).items():
        if key.startswith("_"): continue
        if app_lower == mapping.get("app_name", "").lower():
            result["found"] = True
            result["source"] = "gemini"
            result["context_info"] = mapping
            return result
    
    # 3. Check Core KB
    core_kb = load_core_kb()
    
    # Check apps
    for app_key, app_data in core_kb.get("apps", {}).items():
        patterns = app_data.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in app_lower or app_lower in pattern.lower():
                result["found"] = True
                result["source"] = "core"
                result["app_info"] = app_data
                result["reaction"] = app_data.get("default_reaction")
                return result
    
    # Check contexts (for title matching like YouTube)
    for ctx_key, ctx_data in core_kb.get("contexts", {}).items():
        title_patterns = ctx_data.get("title_contains", [])
        for pattern in title_patterns:
            if pattern.lower() in title_lower:
                result["found"] = True
                result["source"] = "core"
                result["context_info"] = ctx_data
                result["reaction"] = ctx_data.get("default_reaction")
                return result
    
    return result


def get_behavior_policy(behavior_name: str) -> dict:
    """Get behavior policy from Core KB."""
    core_kb = load_core_kb()
    return core_kb.get("behaviors", {}).get(behavior_name, {})


def get_personality() -> dict:
    """Get Rin's personality definition from Core KB."""
    core_kb = load_core_kb()
    return core_kb.get("personality", {})


def get_capability_routing(task: str) -> dict:
    """Get capability routing for a task from Core KB."""
    core_kb = load_core_kb()
    return core_kb.get("capabilities", {}).get(task, {"handler": "gemini", "requires_gemini": True})


# Initialize on import
init_db()

