# Scalable URL Shortener Technical Specification

## 1. Architecture Decisions

To meet the sub-50ms latency constraint using standalone Python and SQLite, the system adopts a lightweight, synchronous architecture optimized for fast read paths.

*   **Database Engine (SQLite):** SQLite is embedded, eliminating network overhead. Write-Ahead Logging (WAL) mode is enabled to allow concurrent reads during writes.
*   **ID Generation Strategy:** Sequential Auto-Increment Primary Keys are used instead of random UUIDs. This avoids fragmentation in SQLite's B-Tree and ensures $O(1)$ database lookups.
*   **Base62 Encoding:** Integer IDs are converted to Base62 strings (`[a-zA-Z0-9]`) to generate compact URL slugs. This provides ~56.8 trillion combinations using an 8-character limit.
*   **Analytics Tracking:** Click events (timestamp and count) are tracked synchronously on redirect. To prevent analytics writes from blocking the redirect pipeline, writes are kept to a single indexed update and insert statement.

### Data Schema

```sql
-- URLs Table
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    long_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics Table
CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER,
    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id);
```

---

## 2. Usage Examples

Below is a complete, standalone Python implementation using the built-in `http.server`, `sqlite3`, and standard libraries.

### Implementation (`shortener.py`)

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import json
import urllib.parse
import string

DB_FILE = "url_shortener.db"
BASE62_CHARS = string.digits + string.ascii_letters

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                long_url TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_id INTEGER,
                clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(url_id) REFERENCES urls(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id);")

def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62_CHARS[0]
    encoded = []
    while num > 0:
        encoded.append(BASE62_CHARS[num % 62])
        num //= 62
    return "".join(reversed(encoded))

def decode_base62(s: str) -> int:
    num = 0
    for char in s:
        num = num * 62 + BASE62_CHARS.index(char)
    return num

class URLShortenerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/shorten":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                long_url = data["long_url"]
            except (json.JSONDecodeError, KeyError):
                self.send_error(400, "Invalid JSON or missing 'long_url'")
                return

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO urls (long_url) VALUES (?)", (long_url,))
                url_id = cursor.lastrowid
                conn.commit()

            short_code = encode_base62(url_id)
            response = {"short_url": f"http://{self.headers['Host']}/{short_code}"}

            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        parts = self.path.strip("/").split("/")
        
        # Analytics Endpoint: /api/analytics/{short_code}
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "analytics":
            short_code = parts[2]
            try:
                url_id = decode_base62(short_code)
            except ValueError:
                self.send_error(400, "Invalid short code")
                return

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT long_url FROM urls WHERE id = ?", (url_id,))
                row = cursor.fetchone()
                if not row:
                    self.send_error(404, "URL not found")
                    return
                
                long_url = row[0]
                cursor.execute("SELECT COUNT(*), MAX(clicked_at), MIN(clicked_at) FROM clicks WHERE url_id = ?", (url_id,))
                total_clicks, last_click, first_click = cursor.fetchone()
                
                cursor.execute("SELECT clicked_at FROM clicks ORDER BY clicked_at DESC LIMIT 10")
                recent_clicks = [r[0] for r in cursor.fetchall()]

            response = {
                "long_url": long_url,
                "total_clicks": total_clicks,
                "first_click": first_click,
                "last_click": last_click,
                "recent_clicks": recent_clicks
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        # Redirect Endpoint: /{short_code}
        elif len(parts) == 1 and parts[0] and parts[0] != "api":
            short_code = parts[0]
            try:
                url_id = decode_base62(short_code)
            except ValueError:
                self.send_error(404, "Not Found")
                return

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT long_url FROM urls WHERE id = ?", (url_id,))
                row = cursor.fetchone()
                if not row:
                    self.send_error(404, "URL not found")
                    return
                
                long_url = row[0]
                # Log click
                cursor.execute("INSERT INTO clicks (url_id) VALUES (?)", (url_id,))
                conn.commit()

            self.send_response(302)
            self.send_header("Location", long_url)
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

if __name__ == "__main__":
    init_db()
    server = HTTPServer(("127.0.0.1", 8080), URLShortenerHandler)
    print("Server running on http://127.0.0.1:8080")
    server.serve_forever()
```

### API Usage

#### 1. Shorten a URL
```bash
curl -X POST http://localhost:8080/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://www.example.com"}'
```
*Response (`201 Created`):*
```json
{"short_url": "http://localhost:8080/b"}
```

#### 2. Access a Short URL (Redirect & Analytics Capture)
```bash
curl -I http://localhost:8080/b
```
*Response (`302 Found`):*
```http
Location: https://www.example.com
```

#### 3. Retrieve Analytics
```bash
curl http://localhost:8080/api/analytics/b
```
*Response (`200 OK`):*
```json
{
  "long_url": "https://www.example.com",
  "total_clicks": 1,
  "first_click": "2023-10-25 14:30:00",
  "last_click": "2023-10-25 14:30:00",
  "recent_clicks": ["2023-10-25 14:30:00"]
}
```

---

## 3. Failure Modes & Mitigations

| Failure Mode | Root Cause | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Database Locks (`sqlite3.OperationalError: database is locked`)** | High concurrent write traffic locking the SQLite file. | Request timeouts / HTTP 500 errors. | Enable WAL mode (`PRAGMA journal_mode=WAL;`) and configure a busy timeout via `sqlite3.connect(..., timeout=5.0)`. |
| **Latency Breach (>50ms)** | Complex queries or missing indexes on analytics aggregation. | Slow redirects/API responses. | Maintain strict indices (`idx_clicks_url_id`). Avoid full table scans by utilizing SQLite's internal rowid optimizations. |
| **Invalid Short Code Decodes** | Malformed base62 inputs (e.g., special characters like `/` or `-`). | Server crashes or incorrect DB queries. | Wrap Base62 string decoders in `try/except` blocks handling `ValueError` and validate character sets against the Base62 alphabet. |
| **Disk Space Exhaustion** | Unbounded growth of the `clicks` analytics table. | SQLite write failures. | Implement a log-rotation/archival cron job to purge or aggregate historical click records older than a retention threshold. |