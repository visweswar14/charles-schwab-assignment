import pytest
from url_shortener import URLShortenerService

@pytest.fixture
def url_shortener() -> URLShortenerService:
    service = URLShortenerService(db_path=":memory:")
    yield service
    service.close()

def test_shorten_and_resolve_url(url_shortener: URLShortenerService) -> None:
    original = "https://example.com/very/long/path?query=1"
    short_code = url_shortener.shorten_url(original)
    
    assert short_code is not None
    assert isinstance(short_code, str)
    assert len(short_code) > 0

    resolved = url_shortener.resolve_url(short_code)
    assert resolved == original

def test_shorten_url_adds_default_scheme(url_shortener: URLShortenerService) -> None:
    original = "example.com"
    short_code = url_shortener.shorten_url(original)
    
    assert short_code is not None
    resolved = url_shortener.resolve_url(short_code)
    assert resolved == "http://example.com"

def test_shorten_invalid_url_returns_none(url_shortener: URLShortenerService) -> None:
    assert url_shortener.shorten_url("") is None

def test_resolve_invalid_short_code(url_shortener: URLShortenerService) -> None:
    assert url_shortener.resolve_url("NONEXISTENT") is None
    assert url_shortener.resolve_url("") is None
    assert url_shortener.resolve_url("!@#$") is None

def test_analytics_tracking(url_shortener: URLShortenerService) -> None:
    original = "https://analytics-test.com"
    short_code = url_shortener.shorten_url(original)
    assert short_code is not None

    analytics = url_shortener.get_analytics(short_code)
    assert analytics is not None
    assert analytics["click_count"] == 0
    assert analytics["timestamps"] == []
    assert analytics["original_url"] == original

    # Resolve a few times
    assert url_shortener.resolve_url(short_code) == original
    assert url_shortener.resolve_url(short_code) == original

    analytics_updated = url_shortener.get_analytics(short_code)
    assert analytics_updated is not None
    assert analytics_updated["click_count"] == 2
    assert len(analytics_updated["timestamps"]) == 2
    assert analytics_updated["timestamps"][0] <= analytics_updated["timestamps"][1]

def test_get_analytics_invalid_code(url_shortener: URLShortenerService) -> None:
    assert url_shortener.get_analytics("BADCODE") is None
    assert url_shortener.get_analytics("") is None
    assert url_shortener.get_analytics("###") is None