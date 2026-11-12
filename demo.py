import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.append("outputs")
import url_shortener


def get_shortener_instance():
    """Dynamically loads the generated URL shortener service class."""
    service_classes = [
        obj for obj in vars(url_shortener).values()
        if isinstance(obj, type) and obj.__module__ == "url_shortener"
    ]
    if not service_classes:
        raise RuntimeError("No URL shortener class found in outputs/url_shortener.py")
    return service_classes[0]()


shortener = get_shortener_instance()


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        code = self.path.lstrip("/")
        if not code or code == "favicon.ico":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"URL Shortener Server is running! Visit /<short_code> to redirect.")
            return

        if code.startswith("stats/"):
            short_code = code.replace("stats/", "", 1)
            stats = shortener.get_analytics(short_code)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(str(stats).encode("utf-8"))
            return

        res = shortener.resolve_url(code)
        target_url = res["long_url"] if isinstance(res, dict) else res

        if target_url:
            self.send_response(302)
            self.send_header("Location", target_url)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Short Code Not Found")


def main():
    print("====================================================")
    print("   GENERATED URL SHORTENER — LIVE BROWSER DEMO      ")
    print("====================================================")

    raw_url = input("\nEnter a URL to shorten (press Enter for 'https://google.com'):\n> ").strip()
    if not raw_url:
        raw_url = "https://google.com"
    elif not raw_url.startswith(("http://", "https://")):
        raw_url = f"https://{raw_url}"

    shorten_res = shortener.shorten_url(raw_url)
    short_code = shorten_res["short_code"] if isinstance(shorten_res, dict) else shorten_res

    print(f"\n[✓] Shortened URL : http://localhost:8000/{short_code}")
    print(f"[✓] Analytics URL : http://localhost:8000/stats/{short_code}")
    print("\nStarting local server on port 8000... (Press Ctrl+C to stop)")

    server = HTTPServer(("localhost", 8000), RedirectHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
