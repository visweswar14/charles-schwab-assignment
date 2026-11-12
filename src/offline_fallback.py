import json
import time

OFFLINE_DEV_CODE = """import sqlite3
import string
import time
from urllib.parse import urlparse

BASE62 = string.digits + string.ascii_letters

def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62[rem])
    return "".join(reversed(chars))

class URLShortenerService:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        try:
            with self.conn:
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        short_code TEXT UNIQUE,
                        long_url TEXT NOT NULL,
                        clicks INTEGER DEFAULT 0,
                        created_at REAL,
                        last_accessed REAL
                    )
                ''')
        except sqlite3.Error as e:
            raise RuntimeError(f"Database initialization failed: {e}")

    def shorten_url(self, long_url: str, custom_alias: str = None) -> str:
        parsed = urlparse(long_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Invalid URL format. Must include http:// or https://")
        try:
            now = time.time()
            with self.conn:
                cursor = self.conn.execute(
                    "INSERT INTO urls (short_code, long_url, clicks, created_at) VALUES (?, ?, 0, ?)",
                    (custom_alias, long_url, now)
                )
                code = custom_alias or encode_base62(cursor.lastrowid + 10000)
                if not custom_alias:
                    self.conn.execute("UPDATE urls SET short_code = ? WHERE id = ?", (code, cursor.lastrowid))
                return code
        except sqlite3.IntegrityError:
            raise ValueError(f"Alias {custom_alias} is already in use.")
        except sqlite3.Error as e:
            raise RuntimeError(f"Storage error: {e}")

    def resolve_url(self, short_code: str) -> str:
        try:
            row = self.conn.execute("SELECT long_url FROM urls WHERE short_code = ?", (short_code,)).fetchone()
            if not row:
                raise KeyError(f"Short code {short_code} not found.")
            with self.conn:
                self.conn.execute(
                    "UPDATE urls SET clicks = clicks + 1, last_accessed = ? WHERE short_code = ?",
                    (time.time(), short_code)
                )
            return row[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database lookup failed: {e}")

    def get_analytics(self, short_code: str) -> dict:
        try:
            row = self.conn.execute(
                "SELECT long_url, clicks, created_at, last_accessed FROM urls WHERE short_code = ?",
                (short_code,)
            ).fetchone()
            if not row:
                raise KeyError(f"Short code {short_code} not found.")
            return {
                "long_url": row[0],
                "clicks": row[1],
                "created_at": row[2],
                "last_accessed": row[3]
            }
        except sqlite3.Error as e:
            raise RuntimeError(f"Analytics query failed: {e}")
"""

OFFLINE_QA_CODE = """import pytest
from solution import URLShortenerService

@pytest.fixture
def service():
    return URLShortenerService(db_path=":memory:")

def test_shorten_and_resolve_url(service):
    code = service.shorten_url("https://example.com")
    assert isinstance(code, str) and len(code) > 0
    resolved = service.resolve_url(code)
    assert resolved == "https://example.com"

def test_analytics_increments_clicks(service):
    code = service.shorten_url("https://example.com")
    service.resolve_url(code)
    service.resolve_url(code)
    stats = service.get_analytics(code)
    assert stats["clicks"] == 2
    assert stats["last_accessed"] is not None

def test_invalid_url_raises_value_error(service):
    with pytest.raises(ValueError):
        service.shorten_url("not-a-valid-url")
"""

OFFLINE_OPENAPI_SPEC = """openapi: 3.0.0
info:
  title: Scalable URL Shortener API
  version: 1.0.0
paths:
  /api/v1/shorten:
    post:
      summary: Create a shortened URL
  /{short_code}:
    get:
      summary: Resolve short code and record analytics
  /api/v1/analytics/{short_code}:
    get:
      summary: Retrieve click count and timestamps
"""

OFFLINE_DESIGN_DOC = """# Scalable URL Shortener - Architecture & Design

## Overview
- **Encoding:** Base62 auto-increment ID mapping (0-9a-zA-Z) with optional custom aliases.
- **Persistence:** SQLite relational schema with unique index on short_code.
- **Analytics:** Tracks total clicks, creation timestamp, and last access timestamp.
- **Resilience:** All database operations are wrapped in try/except sqlite3.Error blocks.
"""


def get_offline_response(role: str, prompt: str) -> str:
    """Deterministic fallback for offline reviewer evaluation or 503 cloud outages."""
    time.sleep(0.2)
    lower_prompt = prompt.lower()

    if role == "intake":
        if ("faster" in lower_prompt or "better stats" in lower_prompt) and "clarification" not in lower_prompt:
            return json.dumps({
                "is_ambiguous": True,
                "ambiguities": [
                    "Specify target latency SLA (e.g., < 50ms p99) and expected QPS.",
                    "Specify required analytics metrics (e.g., click count, timestamp, referrer)."
                ],
                "scenario": "brownfield",
                "normalized": {"goal": "", "constraints": [], "acceptance_criteria": []}
            })
        scenario = "brownfield" if "existing" in lower_prompt or "src/" in lower_prompt else "greenfield"
        return json.dumps({
            "is_ambiguous": False,
            "ambiguities": [],
            "scenario": scenario,
            "normalized": {
                "goal": "Scalable URL shortener service with REST API contract, SQLite persistence, and click analytics",
                "constraints": ["Base62 short code generation", "Sub-50ms redirect lookup", "Graceful DB error handling"],
                "acceptance_criteria": [
                    "shorten_url() validates URLs and persists mapping",
                    "resolve_url() returns original URL and increments click analytics",
                    "get_analytics() returns click count and timestamps"
                ]
            }
        })

    if role == "codebase_reasoner":
        return json.dumps({
            "impacted_files": ["src/api/routes/urls.py", "src/db/storage.py", "src/analytics/tracker.py"],
            "affected_apis": ["GET /{short_code}", "POST /api/v1/shorten"],
            "data_flow": "Client -> APIRouter -> URLService -> SQLite/RedisStore -> AnalyticsTracker"
        })

    if role == "decomposer":
        return json.dumps([
            {"id": "T1", "title": "Define OpenAPI 3.0 URL Shortener & Analytics Contract", "role": "architect", "deps": []},
            {"id": "T2", "title": "Implement URL Shortener with SQLite Persistence & Analytics", "role": "developer", "deps": ["T1"]},
            {"id": "T3", "title": "Generate Standalone Pytest Unit & Integration Suite", "role": "qa", "deps": ["T1"]},
            {"id": "T4", "title": "Write Architecture, Trade-offs & API Documentation", "role": "tech_writer", "deps": ["T2", "T3"]}
        ])

    if role == "architect":
        return OFFLINE_OPENAPI_SPEC
    if role == "developer":
        return OFFLINE_DEV_CODE
    if role == "qa":
        return OFFLINE_QA_CODE
    if role == "tech_writer":
        return OFFLINE_DESIGN_DOC

    return ""
