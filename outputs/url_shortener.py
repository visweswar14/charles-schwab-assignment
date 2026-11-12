import sqlite3
import string
import time
import urllib.parse
from typing import Optional, Dict, Tuple, Any

class URLShortenerService:
    ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
    BASE = len(ALPHABET)

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")

    def _create_tables(self) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url_id INTEGER NOT NULL,
                    clicked_at REAL NOT NULL,
                    FOREIGN KEY (url_id) REFERENCES urls (id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id)")
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to create tables: {e}")

    def _encode_base62(self, num: int) -> str:
        if num == 0:
            return self.ALPHABET[0]
        
        arr = []
        while num > 0:
            num, rem = divmod(num, self.BASE)
            arr.append(self.ALPHABET[rem])
        return "".join(reversed(arr))

    def _decode_base62(self, code: str) -> int:
        num = 0
        for char in code:
            num = num * self.BASE + self.ALPHABET.index(char)
        return num

    def shorten_url(self, original_url: str) -> Optional[str]:
        if not original_url:
            return None

        parsed = urllib.parse.urlparse(original_url)
        if not parsed.scheme:
            original_url = "http://" + original_url

        try:
            cursor = self.conn.cursor()
            created_at = time.time()
            cursor.execute(
                "INSERT INTO urls (original_url, created_at) VALUES (?, ?)",
                (original_url, created_at)
            )
            self.conn.commit()
            url_id = cursor.lastrowid
            return self._encode_base62(url_id)
        except Exception as e:
            self.conn.rollback()
            return None

    def resolve_url(self, short_code: str) -> Optional[str]:
        if not short_code:
            return None

        try:
            url_id = self._decode_base62(short_code)
        except (ValueError, IndexError):
            return None

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, original_url FROM urls WHERE id = ?", (url_id,))
            row = cursor.fetchone()
            
            if not row:
                return None

            clicked_at = time.time()
            cursor.execute(
                "INSERT INTO clicks (url_id, clicked_at) VALUES (?, ?)",
                (row["id"], clicked_at)
            )
            self.conn.commit()
            return row["original_url"]
        except Exception as e:
            self.conn.rollback()
            return None

    def get_analytics(self, short_code: str) -> Optional[Dict[str, Any]]:
        if not short_code:
            return None

        try:
            url_id = self._decode_base62(short_code)
        except (ValueError, IndexError):
            return None

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, original_url, created_at FROM urls WHERE id = ?", (url_id,))
            url_row = cursor.fetchone()

            if not url_row:
                return None

            cursor.execute(
                "SELECT clicked_at FROM clicks WHERE url_id = ? ORDER BY clicked_at ASC",
                (url_id,)
            )
            click_rows = cursor.fetchall()

            clicks = [row["clicked_at"] for row in click_rows]

            return {
                "short_code": short_code,
                "original_url": url_row["original_url"],
                "created_at": url_row["created_at"],
                "click_count": len(clicks),
                "timestamps": clicks
            }
        except Exception as e:
            return None

    def close(self) -> None:
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass