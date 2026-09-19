async (page) => {
  const fail = (message) => { throw new Error(message); };

  await page.waitForSelector("#modelSelect:not([disabled])", { timeout: 10000 });
  const health = await page.locator("#healthText").textContent();
  if (!health || !health.includes("READY")) fail("health indicator did not become READY");
  if (await page.locator("#modelSelect option").count() < 1) fail("model catalog is empty");

  await page.locator("#queryInput").fill("What does RAG combine?");
  await page.locator("#queryInput").press("Enter");
  await page.locator("article.message.assistant.pending").waitFor({ state: "detached", timeout: 15000 });
  const answer = page.locator("article.message.assistant").last();
  await answer.waitFor({ state: "visible", timeout: 15000 });
  const answerText = await answer.textContent();
  if (!answerText || !answerText.includes("RAG")) fail("answer was not rendered");
  if (await page.locator(".citation-chip").count() < 1) fail("citation was not rendered");
  if (await page.locator("#saveButton").isDisabled()) fail("save button stayed disabled");

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#saveButton").click();
  const download = await downloadPromise;
  if (!download.suggestedFilename().endsWith(".md")) fail("unexpected export filename");

  await page.locator("#clearButton").click();
  const emptyText = await page.locator("#emptyState").textContent();
  if (!emptyText || !emptyText.includes("会话已清空")) fail("clear did not restore empty state");

  await page.locator("#queryInput").fill("重新验证键盘发送");
  await page.locator("#queryInput").press("Enter");
  await page.locator("article.message.assistant.pending").waitFor({ state: "detached", timeout: 15000 });
  await page.locator("article.message.assistant").last().waitFor({ state: "visible", timeout: 15000 });

  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (overflow) fail(`horizontal overflow at width ${width}`);
  }

  await page.screenshot({ path: "browser-e2e.png", fullPage: true });
  return { health, answer: answerText.slice(0, 120), citations: await page.locator(".citation-chip").count() };
}
