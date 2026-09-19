from __future__ import annotations

import gzip

import httpx
import pytest

from ragforge.collector import HttpCollector, SourceSpec, load_sources, normalize_url


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _source(**overrides) -> SourceSpec:
    values = {
        "id": "docs",
        "type": "sitemap",
        "base_url": "https://example.test/",
        "sitemap_url": "https://example.test/sitemap.xml",
        "allowed_domains": ["example.test"],
        "category": "docs",
        "trust": 1.0,
        "enabled": True,
        "max_pages": 20,
    }
    values.update(overrides)
    return SourceSpec(**values)


def test_load_sources_uses_safe_yaml_and_validates_fields(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
        - id: ollama_docs
          type: sitemap
          base_url: https://docs.ollama.com/
          sitemap_url: https://docs.ollama.com/sitemap.xml
          allowed_domains: [docs.ollama.com]
          category: local_llm
          trust: 1.0
          enabled: true
          max_pages: 200
        """,
        encoding="utf-8",
    )

    sources = load_sources(path)

    assert sources[0].id == "ollama_docs"
    assert sources[0].max_pages == 200

    path.write_text("!!python/object/apply:os.system ['whoami']", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML"):
        load_sources(path)


def test_normalize_url_removes_fragment_and_tracking_but_keeps_query():
    assert normalize_url(
        "HTTPS://Example.TEST:443/guide/?utm_source=x&lang=zh#section"
    ) == "https://example.test/guide/?lang=zh"


def test_sitemap_collection_honors_robots_and_rejects_cross_domain_redirect():
    sitemap = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/ok</loc></url>
      <url><loc>https://example.test/private</loc></url>
      <url><loc>https://example.test/redirect</loc></url>
    </urlset>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap, headers={"content-type": "application/xml"})
        if request.url.path == "/ok":
            return httpx.Response(200, text="<main><h1>OK</h1><p>Useful page.</p></main>", headers={"content-type": "text/html"})
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "https://evil.example/landing"})
        return httpx.Response(404)

    result = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
    ).collect()[0]

    assert [page.url for page in result.pages] == ["https://example.test/ok"]
    assert any(error.code == "robots_disallowed" for error in result.errors)
    assert any(error.code == "redirect_domain" for error in result.errors)
    assert result.enumeration_complete is True


def test_sitemap_discovery_stops_after_page_limit_plus_one():
    sitemap = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/first</loc></url>
      <url><loc>https://late.example.test/second</loc></url>
      <url><loc>https://too-late.example.test/third</loc></url>
    </urlset>
    """
    resolved_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        return httpx.Response(200, text="<main><p>First</p></main>", headers={"content-type": "text/html"})

    def resolve_host(host: str) -> list[str]:
        resolved_hosts.append(host)
        return ["93.184.216.34"]

    result = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=resolve_host,
        min_interval=0,
    ).collect(max_pages=1)[0]

    assert [page.url for page in result.pages] == ["https://example.test/first"]
    assert "late.example.test" in resolved_hosts
    assert "too-late.example.test" not in resolved_hosts


def test_sitemap_entities_are_rejected_as_untrusted_xml():
    sitemap = b'''<!DOCTYPE urlset [<!ENTITY injected "https://example.test/should-not-fetch">]
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>&injected;</loc></url>
    </urlset>'''

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, content=sitemap, headers={"content-type": "application/xml"})
        raise AssertionError(f"unexpected fetch: {request.url}")

    result = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
    ).collect()[0]

    assert result.pages == []
    assert any(error.code == "bad_sitemap" for error in result.errors)


def test_collection_time_budget_stops_before_next_request():
    calls: list[str] = []
    clock_values = iter([0.0, 2.0])

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")

    collector = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
        max_duration=1.0,
        clock=lambda: next(clock_values, 2.0),
    )

    result = collector.collect(max_pages=1)[0]

    assert calls == []
    assert any(error.code == "time_budget_exhausted" for error in result.errors)
    assert result.enumeration_complete is False


def test_page_failure_does_not_abort_other_pages_and_429_retries():
    sitemap = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/good</loc></url>
      <url><loc>https://example.test/retry</loc></url>
      <url><loc>https://example.test/bad</loc></url>
    </urlset>
    """
    attempts = {"retry": 0, "bad": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        if request.url.path == "/good":
            return httpx.Response(200, text="<main><p>Good</p></main>", headers={"content-type": "text/html"})
        if request.url.path == "/retry":
            attempts["retry"] += 1
            if attempts["retry"] < 3:
                return httpx.Response(429, headers={"retry-after": "0"})
            return httpx.Response(200, text="<main><p>Retry succeeded</p></main>", headers={"content-type": "text/html"})
        attempts["bad"] += 1
        return httpx.Response(503)

    result = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
        sleep=sleeps.append,
        max_retries=2,
    ).collect()[0]

    assert {page.url for page in result.pages} == {"https://example.test/good", "https://example.test/retry"}
    assert attempts["retry"] == 3
    assert attempts["bad"] == 3
    assert any(error.code == "http_5xx" for error in result.errors)


def test_private_ip_and_oversized_response_are_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, content=b"x" * 100, headers={"content-type": "text/html"})

    private = HttpCollector(
        [_source(base_url="http://127.0.0.1/", sitemap_url="http://127.0.0.1/sitemap.xml", allowed_domains=["127.0.0.1"])],
        client=_client(handler),
        min_interval=0,
    ).collect()[0]
    assert any(error.code == "private_ip" for error in private.errors)

    oversized = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
        max_response_bytes=30,
    ).collect()[0]
    assert any(error.code == "response_too_large" for error in oversized.errors)


def test_gzip_response_is_not_decompressed_twice():
    compressed = gzip.compress(b"<main><p>compressed page</p></main>")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=compressed, headers={
            "content-type": "text/html",
            "content-encoding": "gzip",
        })

    collector = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
    )
    page = collector.fetch_page("https://example.test/page", _source(), obey_robots=False)

    assert page.error_code is None
    assert page.content == b"<main><p>compressed page</p></main>"


def test_redirect_to_trailing_slash_does_not_loop():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/page":
            return httpx.Response(301, headers={"location": "/page/"})
        return httpx.Response(200, content=b"<main><p>slash page</p></main>", headers={"content-type": "text/html"})

    collector = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
    )
    page = collector.fetch_page("https://example.test/page", _source(), obey_robots=False)

    assert page.error_code is None
    assert page.url == "https://example.test/page/"


def test_streaming_response_is_stopped_when_collection_deadline_expires():
    clock_value = [0.0]

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            for part in (b"first", b"second", b"third"):
                clock_value[0] += 0.6
                yield part

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream(), headers={"content-type": "text/html"})

    collector = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: ["93.184.216.34"],
        min_interval=0,
        max_duration=1.0,
        clock=lambda: clock_value[0],
    )
    collector._deadline = 1.0

    page = collector.fetch_page("https://example.test/page", _source(), obey_robots=False)

    assert page.error_code == "time_budget_exhausted"


def test_dns_resolution_change_between_connect_checks_is_rejected():
    resolutions = iter([
        ["93.184.216.34"],
        ["93.184.216.35"],
        ["10.0.0.8"],
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<main>should not be trusted</main>")

    collector = HttpCollector(
        [_source()],
        client=_client(handler),
        resolve_host=lambda _host: next(resolutions),
        min_interval=0,
    )

    page = collector.fetch_page("https://example.test/page", _source(), obey_robots=False)

    assert page.error_code == "dns_rebind"
