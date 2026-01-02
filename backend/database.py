import sqlite3
import json
from datetime import datetime, timedelta
import os

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


# Initialize on import
init_db()

