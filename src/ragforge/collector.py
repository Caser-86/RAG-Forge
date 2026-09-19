"""受控的公开资料采集器。

采集器的默认策略偏保守：先检查 robots.txt，再限制域名、解析地址、响应大小、
重定向次数和请求频率。它只负责发现和下载页面，不负责把页面当成可信指令执行。
"""
from __future__ import annotations

import email.utils
import ipaddress
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from bs4 import BeautifulSoup
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException


USER_AGENT = "RAGForgeLocalCollector/0.1"
DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_MIN_INTERVAL = 1.0
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid",
}


@dataclass(frozen=True)
class SourceSpec:
    id: str
    type: str
    base_url: str
    allowed_domains: tuple[str, ...] = ()
    category: str = ""
    trust: float = 1.0
    enabled: bool = True
    max_pages: int = 200
    sitemap_url: str | None = None
    seed_urls: tuple[str, ...] = ()
    language: str = ""
    license_hint: str = "official documentation"

    def __post_init__(self) -> None:
        if self.type not in {"sitemap", "links"}:
            raise ValueError(f"unsupported source type: {self.type!r}")
        base = normalize_url(self.base_url)
        object.__setattr__(self, "base_url", base)
        domains = tuple(_normalize_host(value) for value in self.allowed_domains if str(value).strip())
        if not domains:
            host = urlsplit(base).hostname
            if not host:
                raise ValueError(f"source {self.id!r} has no base host")
            domains = (host,)
        object.__setattr__(self, "allowed_domains", domains)
        if self.max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if not 0.0 <= self.trust <= 1.0:
            raise ValueError("trust must be between 0 and 1")
        if self.sitemap_url:
            object.__setattr__(self, "sitemap_url", normalize_url(self.sitemap_url))
        object.__setattr__(self, "seed_urls", tuple(normalize_url(url) for url in self.seed_urls))


@dataclass(frozen=True)
class CollectorError:
    code: str
    message: str
    url: str | None = None
    status: int | None = None


@dataclass
class FetchedPage:
    source_id: str
    requested_url: str
    url: str
    status: int | None
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    error_code: str | None = None
    error: str | None = None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()


@dataclass
class CollectionResult:
    source_id: str
    pages: list[FetchedPage] = field(default_factory=list)
    errors: list[CollectorError] = field(default_factory=list)
    skipped: list[CollectorError] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    enumeration_complete: bool = False


class CollectorRequestError(RuntimeError):
    def __init__(self, code: str, message: str, *, url: str, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.url = url
        self.status = status


def _normalize_host(host: str) -> str:
    return str(host).strip().lower().rstrip(".")


def normalize_url(url: str) -> str:
    """规范化 URL，但不删除可能影响正文的普通 query 参数。"""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("only http and https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("URL host is required")
    host = _normalize_host(host)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid URL port") from exc
    default_port = (parsed.scheme.lower() == "http" and port == 80) or (
        parsed.scheme.lower() == "https" and port == 443
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    # 不删除非根路径的尾斜杠：很多文档站点把 /guide 和 /guide/ 视为不同
    # canonical URL，删除它会把服务器的规范化重定向变成循环。
    path = parsed.path or "/"
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
         if key.lower() not in _TRACKING_PARAMS]
    )
    return urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def load_sources(path: str | Path) -> list[SourceSpec]:
    """使用 safe_load 读取来源配置，不允许 YAML 构造任意 Python 对象。"""
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"YAML source configuration could not be loaded: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError("YAML source configuration must be a list")
    sources: list[SourceSpec] = []
    seen: set[str] = set()
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("each source entry must be a mapping")
        required = {"id", "type", "base_url", "allowed_domains", "category", "trust", "enabled", "max_pages"}
        missing = required - raw.keys()
        if missing:
            raise ValueError(f"source entry missing fields: {sorted(missing)}")
        source = SourceSpec(
            id=str(raw["id"]),
            type=str(raw["type"]),
            base_url=str(raw["base_url"]),
            allowed_domains=tuple(str(item) for item in raw["allowed_domains"]),
            category=str(raw.get("category", "")),
            trust=float(raw.get("trust", 1.0)),
            enabled=bool(raw.get("enabled", True)),
            max_pages=int(raw.get("max_pages", 200)),
            sitemap_url=str(raw["sitemap_url"]) if raw.get("sitemap_url") else None,
            seed_urls=tuple(str(item) for item in raw.get("seed_urls", [])),
            language=str(raw.get("language", "")),
            license_hint=str(raw.get("license_hint", "official documentation")),
        )
        if not source.id or source.id in seen:
            raise ValueError(f"source id must be non-empty and unique: {source.id!r}")
        seen.add(source.id)
        sources.append(source)
    return sources


class HttpCollector:
    def __init__(
        self,
        sources: Iterable[SourceSpec],
        *,
        client: httpx.Client | None = None,
        user_agent: str = USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_retry_wait: float = 60.0,
        max_duration: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        resolve_host: Callable[[str], Iterable[str]] | None = None,
    ):
        self.sources = list(sources)
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_redirects = max_redirects
        self.max_response_bytes = max_response_bytes
        self.min_interval = min_interval
        self.max_retry_wait = max_retry_wait
        if max_duration is not None and max_duration <= 0:
            raise ValueError("max_duration must be positive")
        self.max_duration = max_duration
        self._sleep = sleep
        self._clock = clock
        self._resolve_host = resolve_host or _resolve_public_addresses
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_errors: dict[str, CollectorError] = {}
        self._deadline: float | None = None
        self._owns_client = client is None
        # Do not let ambient HTTP(S)_PROXY settings route a public-source fetch
        # through an unreviewed destination. Callers supplying a client own its
        # proxy/trust_env policy and should configure it explicitly.
        self.client = client or httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> HttpCollector:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def collect(self, *, max_pages: int | None = None) -> list[CollectionResult]:
        results: list[CollectionResult] = []
        previous_deadline = self._deadline
        self._deadline = self._clock() + self.max_duration if self.max_duration is not None else None
        try:
            for index, source in enumerate(self.sources):
                if self._budget_expired():
                    results.extend(
                        CollectionResult(
                            pending.id,
                            errors=[CollectorError(
                                "time_budget_exhausted",
                                "collection time budget exhausted",
                                url=pending.base_url,
                            )],
                            enumeration_complete=False,
                        )
                        for pending in self.sources[index:]
                    )
                    break
                if not source.enabled:
                    results.append(CollectionResult(source.id, enumeration_complete=False))
                    continue
                results.append(self._collect_source(source, max_pages=max_pages))
        finally:
            self._deadline = previous_deadline
        return results

    def _collect_source(self, source: SourceSpec, *, max_pages: int | None) -> CollectionResult:
        result = CollectionResult(source.id)
        limit = min(source.max_pages, max_pages) if max_pages else source.max_pages
        if not self._robots_allowed(source, source.base_url, result):
            result.enumeration_complete = False
            return result

        if source.type == "sitemap":
            urls, complete = self._discover_sitemap(source, result, limit)
        else:
            urls, complete = self._discover_links(source, result, limit)
        result.discovered_urls = urls[:limit]
        if len(urls) > limit:
            complete = False

        failed_fetch = False
        for url in result.discovered_urls:
            try:
                validate_url(url, source, resolve_host=self._resolve_host)
            except CollectorRequestError as exc:
                result.errors.append(_error_from_exception(exc))
                continue
            if not self._robots_allowed(source, url, result):
                continue
            page = self.fetch_page(url, source, obey_robots=False)
            if page.error_code:
                result.errors.append(CollectorError(page.error_code, page.error or page.error_code, url=page.url, status=page.status))
                failed_fetch = failed_fetch or page.error_code in {"timeout", "network_error", "http_5xx", "too_many_redirects", "time_budget_exhausted"}
                if page.error_code == "time_budget_exhausted":
                    break
                continue
            if page.status is None or not 200 <= page.status < 300:
                result.errors.append(CollectorError("http_status", f"unexpected HTTP status {page.status}", url=page.url, status=page.status))
                failed_fetch = True
                continue
            if page.content_type and page.content_type not in {"text/html", "application/xhtml+xml"}:
                result.skipped.append(CollectorError("unsupported_content_type", page.content_type, url=page.url, status=page.status))
                continue
            result.pages.append(page)
        # 页面失败会让“完整枚举”不成立；robots 拒绝和安全跳过不影响已完整解析的 sitemap。
        result.enumeration_complete = complete and not failed_fetch
        return result

    def _discover_sitemap(self, source: SourceSpec, result: CollectionResult, limit: int) -> tuple[list[str], bool]:
        sitemap_url = source.sitemap_url or urljoin(source.base_url, "sitemap.xml")
        queue = [normalize_url(sitemap_url)]
        seen_sitemaps: set[str] = set()
        urls: list[str] = []
        complete = True
        while queue and len(urls) <= limit:
            current = queue.pop(0)
            if current in seen_sitemaps:
                continue
            seen_sitemaps.add(current)
            if not self._robots_allowed(source, current, result):
                complete = False
                continue
            page = self.fetch_page(current, source, obey_robots=False)
            if page.error_code or page.status != 200:
                result.errors.append(CollectorError(page.error_code or "sitemap_http_status", page.error or f"sitemap status {page.status}", current, page.status))
                complete = False
                continue
            try:
                root = ET.fromstring(page.content)
            except (ET.ParseError, DefusedXmlException) as exc:
                result.errors.append(CollectorError("bad_sitemap", str(exc), current, page.status))
                complete = False
                continue
            root_name = _xml_local_name(root.tag)
            locs = [_text_of(child) for child in root.iter() if _xml_local_name(child.tag) == "loc" and _text_of(child)]
            if root_name == "sitemapindex":
                for loc in locs:
                    try:
                        validate_url(normalize_url(loc), source, resolve_host=self._resolve_host)
                        queue.append(normalize_url(loc))
                    except (ValueError, CollectorRequestError) as exc:
                        result.errors.append(_error_from_exception(exc, url=loc))
                        complete = False
            elif root_name == "urlset":
                for loc in locs:
                    # 只多发现一个候选即可判断是否超过页面上限；避免大 sitemap
                    # 在截断前为数千个 URL 做 DNS/IP 安全校验。
                    if len(urls) > limit:
                        break
                    try:
                        normalized = normalize_url(loc)
                        validate_url(normalized, source, resolve_host=self._resolve_host)
                    except (ValueError, CollectorRequestError) as exc:
                        result.errors.append(_error_from_exception(exc, url=loc))
                        continue
                    if normalized not in urls:
                        urls.append(normalized)
            else:
                result.errors.append(CollectorError("bad_sitemap", f"unsupported root element {root_name!r}", current, page.status))
                complete = False
        if queue:
            complete = False
        return urls, complete

    def _discover_links(self, source: SourceSpec, result: CollectionResult, limit: int) -> tuple[list[str], bool]:
        seeds = list(source.seed_urls) or [source.base_url]
        urls: list[str] = []
        for seed in seeds:
            if seed not in urls:
                urls.append(seed)
        # links 类型只做一层发现，避免无限爬取；页面正文稍后统一下载并清洗。
        for seed in list(urls):
            if len(urls) > limit or not self._robots_allowed(source, seed, result):
                continue
            page = self.fetch_page(seed, source, obey_robots=False)
            if page.error_code or page.status != 200:
                result.errors.append(CollectorError(page.error_code or "seed_http_status", page.error or f"seed status {page.status}", seed, page.status))
                continue
            soup = BeautifulSoup(page.content, "html.parser")
            for anchor in soup.find_all("a", href=True):
                try:
                    candidate = normalize_url(urljoin(page.url, str(anchor["href"])))
                    validate_url(candidate, source, resolve_host=self._resolve_host)
                except (ValueError, CollectorRequestError):
                    continue
                if candidate not in urls:
                    urls.append(candidate)
                if len(urls) > limit:
                    break
        return urls, len(urls) <= limit

    def _robots_allowed(self, source: SourceSpec, url: str, result: CollectionResult) -> bool:
        host = _normalize_host(urlsplit(url).hostname or "")
        if host in self._robots_errors:
            error = self._robots_errors[host]
            if not any(item.code == error.code and item.url == url for item in result.errors):
                result.errors.append(CollectorError(error.code, error.message, url, error.status))
            return False
        policy: RobotFileParser | None = self._robots.get(host)
        if host not in self._robots:
            robots_url = urlunsplit((urlsplit(url).scheme, urlsplit(url).netloc, "/robots.txt", "", ""))
            try:
                validate_url(robots_url, source, resolve_host=self._resolve_host)
                page = self.fetch_page(robots_url, source, obey_robots=False)
            except CollectorRequestError as exc:
                error = _error_from_exception(exc)
                self._robots_errors[host] = error
                result.errors.append(error)
                return False
            if page.status == 404:
                policy = RobotFileParser(robots_url)
                policy.parse([])
            elif page.error_code or page.status not in {200}:
                error = CollectorError(page.error_code or "robots_unavailable", page.error or f"robots status {page.status}", robots_url, page.status)
                self._robots_errors[host] = error
                result.errors.append(error)
                return False
            else:
                policy = RobotFileParser(robots_url)
                policy.parse(page.content.decode("utf-8", errors="replace").splitlines())
            self._robots[host] = policy
        policy = self._robots[host]
        if policy is not None and not policy.can_fetch(self.user_agent, url):
            result.errors.append(CollectorError("robots_disallowed", "robots.txt disallows this URL", url))
            return False
        return True

    def fetch_page(self, url: str, source: SourceSpec, *, obey_robots: bool = True) -> FetchedPage:
        normalized = normalize_url(url)
        if obey_robots:
            temporary = CollectionResult(source.id)
            if not self._robots_allowed(source, normalized, temporary):
                return FetchedPage(source.id, normalized, normalized, None, error_code="robots_disallowed", error="robots.txt disallows this URL")
        current = normalized
        for redirect_count in range(self.max_redirects + 1):
            try:
                validate_url(current, source, resolve_host=self._resolve_host)
            except CollectorRequestError as exc:
                return FetchedPage(source.id, normalized, current, exc.status, error_code=exc.code, error=str(exc))
            for attempt in range(self.max_retries + 1):
                try:
                    response = self._request_once(current)
                except CollectorRequestError as exc:
                    if exc.code in {"timeout", "network_error", "http_5xx"} and attempt < self.max_retries:
                        self._backoff(attempt)
                        continue
                    return FetchedPage(source.id, normalized, current, exc.status, error_code=exc.code, error=str(exc))
                if response.status_code == 429 and attempt < self.max_retries:
                    wait = _retry_after_seconds(response.headers.get("retry-after"))
                    if wait is not None and wait <= self.max_retry_wait:
                        self._sleep(wait)
                        continue
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        return FetchedPage(source.id, normalized, current, response.status_code, error_code="redirect_missing_location", error="redirect response has no Location")
                    try:
                        next_url = normalize_url(urljoin(current, location))
                        validate_url(next_url, source, resolve_host=self._resolve_host)
                    except (ValueError, CollectorRequestError) as exc:
                        error = _error_from_exception(exc, url=location)
                        return FetchedPage(source.id, normalized, current, response.status_code, error_code=error.code, error=error.message)
                    current = next_url
                    break
                error_code = "http_5xx" if 500 <= response.status_code < 600 else None
                return FetchedPage(
                    source.id,
                    normalized,
                    current,
                    response.status_code,
                    content=response.content,
                    headers=dict(response.headers),
                    error_code=error_code,
                    error=f"HTTP {response.status_code}" if error_code else None,
                )
            else:
                return FetchedPage(source.id, normalized, current, None, error_code="network_error", error="request retries exhausted")
            if redirect_count == self.max_redirects:
                return FetchedPage(source.id, normalized, current, 3, error_code="too_many_redirects", error="redirect limit exceeded")
        return FetchedPage(source.id, normalized, current, None, error_code="too_many_redirects", error="redirect limit exceeded")

    def _request_once(self, url: str) -> httpx.Response:
        host = _normalize_host(urlsplit(url).hostname or "")
        self._wait_for_domain(host)
        remaining = self._remaining_budget()
        if remaining is not None and remaining <= 0:
            raise CollectorRequestError(
                "time_budget_exhausted",
                "collection time budget exhausted",
                url=url,
            )
        request_timeout = self.timeout if remaining is None else min(self.timeout, remaining)
        resolved_before = _resolve_addresses(host, url, self._resolve_host)
        _assert_public_addresses(resolved_before, url)
        try:
            with self.client.stream(
                "GET",
                url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                follow_redirects=False,
                timeout=request_timeout,
            ) as response:
                resolved_after = _resolve_addresses(host, url, self._resolve_host)
                if resolved_after != resolved_before:
                    raise CollectorRequestError(
                        "dns_rebind",
                        "resolved destination changed during request",
                        url=url,
                    )
                _assert_public_addresses(resolved_after, url)
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_response_bytes:
                    raise CollectorRequestError("response_too_large", "response Content-Length exceeds limit", url=url, status=response.status_code)
                body = bytearray()
                for chunk in response.iter_bytes():
                    if self._budget_expired():
                        raise CollectorRequestError(
                            "time_budget_exhausted",
                            "collection time budget exhausted",
                            url=url,
                        )
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise CollectorRequestError("response_too_large", "response exceeds byte limit", url=url, status=response.status_code)
                    if self._budget_expired():
                        raise CollectorRequestError(
                            "time_budget_exhausted",
                            "collection time budget exhausted",
                            url=url,
                        )
                decoded_headers = dict(response.headers)
                # httpx 已在 iter_bytes() 阶段解压；重包装时必须去掉编码标记，
                # 否则后续访问 .content 会触发二次解压。
                decoded_headers.pop("content-encoding", None)
                decoded_headers["content-length"] = str(len(body))
                return httpx.Response(
                    response.status_code,
                    headers=decoded_headers,
                    content=bytes(body),
                    request=response.request,
                )
        except CollectorRequestError:
            raise
        except httpx.TimeoutException as exc:
            raise CollectorRequestError("timeout", str(exc) or "request timed out", url=url) from exc
        except httpx.HTTPError as exc:
            raise CollectorRequestError("network_error", str(exc), url=url) from exc
        except (ValueError, TypeError) as exc:
            raise CollectorRequestError("network_error", str(exc), url=url) from exc

    def _wait_for_domain(self, host: str) -> None:
        now = self._clock()
        previous = self._last_request.get(host)
        if previous is not None:
            delay = self.min_interval - (now - previous)
            if delay > 0:
                remaining = self._remaining_budget()
                self._sleep(delay if remaining is None else min(delay, max(0.0, remaining)))
        self._last_request[host] = self._clock()

    def _backoff(self, attempt: int) -> None:
        delay = min(self.max_retry_wait, float(2**attempt))
        remaining = self._remaining_budget()
        self._sleep(delay if remaining is None else min(delay, max(0.0, remaining)))

    def _remaining_budget(self) -> float | None:
        if self._deadline is None:
            return None
        return self._deadline - self._clock()

    def _budget_expired(self) -> bool:
        remaining = self._remaining_budget()
        return remaining is not None and remaining <= 0


def validate_url(
    url: str,
    source: SourceSpec,
    *,
    resolve_host: Callable[[str], Iterable[str]] | None = None,
) -> None:
    try:
        normalized = normalize_url(url)
        parsed = urlsplit(normalized)
    except ValueError as exc:
        raise CollectorRequestError("invalid_url", str(exc), url=url) from exc
    host = _normalize_host(parsed.hostname or "")
    if not any(host == domain or host.endswith("." + domain) for domain in source.allowed_domains):
        raise CollectorRequestError("redirect_domain", f"host {host!r} is outside allowed domains", url=normalized)
    try:
        addresses = list((resolve_host or _resolve_public_addresses)(host))
    except OSError as exc:
        raise CollectorRequestError("dns_error", str(exc), url=normalized) from exc
    if not addresses:
        raise CollectorRequestError("dns_error", f"host {host!r} has no address", url=normalized)
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise CollectorRequestError("dns_error", f"invalid resolved address {address!r}", url=normalized) from exc
        if not ip.is_global:
            raise CollectorRequestError("private_ip", f"refusing non-public address {ip}", url=normalized)


def _resolve_public_addresses(host: str) -> Iterable[str]:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return [str(info[4][0]) for info in infos]
    return [str(ip)]


def _resolve_addresses(
    host: str,
    url: str,
    resolve_host: Callable[[str], Iterable[str]],
) -> tuple[str, ...]:
    try:
        addresses = tuple(sorted({str(address) for address in resolve_host(host)}))
    except OSError as exc:
        raise CollectorRequestError("dns_error", str(exc), url=url) from exc
    if not addresses:
        raise CollectorRequestError("dns_error", f"host {host!r} has no address", url=url)
    return addresses


def _assert_public_addresses(addresses: Iterable[str], url: str) -> None:
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise CollectorRequestError(
                "dns_error",
                f"invalid resolved address {address!r}",
                url=url,
            ) from exc
        if not ip.is_global:
            raise CollectorRequestError(
                "private_ip",
                f"refusing non-public address {ip}",
                url=url,
            )


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return 1.0
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            target = email.utils.parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 1.0


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text_of(element: ET.Element) -> str:
    return (element.text or "").strip()


def _error_from_exception(exc: Exception, *, url: str | None = None) -> CollectorError:
    if isinstance(exc, CollectorRequestError):
        return CollectorError(exc.code, str(exc), url or exc.url, exc.status)
    return CollectorError("invalid_url", str(exc), url)
