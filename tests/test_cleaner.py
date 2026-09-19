from ragforge.ingest.cleaner import CLEANER_VERSION, clean_html


def test_cleaner_preserves_headings_code_lists_and_removes_chrome():
    html = """
    <html><head><title>RAG Guide</title></head><body>
      <nav>Global navigation</nav>
      <main>
        <h1>Retrieval</h1>
        <h2>Hybrid Search</h2>
        <p>Dense and sparse retrieval complement each other.</p>
        <pre><code>curl http://127.0.0.1:6333/readyz</code></pre>
        <ul><li>Dense</li><li>BM25</li></ul>
      </main>
      <div class="cookie-banner">Accept cookies</div>
      <footer>Previous | Next</footer>
    </body></html>
    """

    result = clean_html(html, "https://example.test/guide", response_status=200)

    assert result.status == "ok"
    assert result.title == "RAG Guide"
    assert "Global navigation" not in result.text
    assert "Accept cookies" not in result.text
    assert "# Retrieval" in result.text
    assert "## Hybrid Search" in result.text
    assert "curl http://127.0.0.1:6333/readyz" in result.text
    assert "- Dense" in result.text
    assert result.content_hash
    assert result.meta["cleaner_version"] == CLEANER_VERSION


def test_cleaner_skips_empty_and_login_pages():
    empty = clean_html("<html><body><nav>Menu</nav></body></html>", "https://example.test/empty")
    login = clean_html(
        "<html><head><title>Sign in</title></head><body><main>Sign in to continue</main></body></html>",
        "https://example.test/login",
    )

    assert empty.status == "skipped"
    assert empty.reason in {"empty_body", "empty_after_cleaning"}
    assert login.status == "skipped"
    assert login.reason == "login_page"


def test_cleaner_hash_is_stable_after_whitespace_normalization():
    first = clean_html("<main><p>A   sentence</p>\n<p>Second line.</p></main>", "https://example.test/a")
    second = clean_html("<main> <p>A sentence</p><p>Second line.</p> </main>", "https://example.test/a")

    assert first.status == second.status == "ok"
    assert first.content_hash == second.content_hash


def test_cleaner_handles_nested_template_nodes_after_removal():
    result = clean_html(
        "<main><div class='cookie-banner'><span class='inner'>Ignore me</span></div><p>Useful text.</p></main>",
        "https://example.test/nested",
    )

    assert result.status == "ok"
    assert result.text == "Useful text."
