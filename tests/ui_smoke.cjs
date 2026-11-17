const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const axe = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const base = process.env.UI_TEST_BASE_URL || "http://127.0.0.1:5001";
assert.ok(
  base.endsWith(":5001"),
  "Use the isolated ui_server.py fixture on port 5001.",
);
fs.mkdirSync("/tmp/campus-checks", { recursive: true });
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 1024 } });
  const failures = [],
    errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  async function inspect(name, path, width = 1440) {
    await p.setViewportSize({ width, height: 1024 });
    await p.goto(base + path);
    await p.evaluate(async () => {
      for (const img of document.images) img.loading = "eager";
      await Promise.all(
        [...document.images].map((img) => img.decode().catch(() => {})),
      );
    });
    await p.screenshot({
      path: `/tmp/campus-checks/${name}-${width}.png`,
      fullPage: true,
    });
    const over = await p.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 1,
    );
    if (over) failures.push(name + " overflow " + width);
    await p.addScriptTag({ content: axe });
    const a = await p.evaluate(async () =>
      axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      }),
    );
    for (const v of a.violations)
      failures.push({
        name,
        width,
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      });
    const broken = await p
      .locator("img")
      .evaluateAll((imgs) =>
        imgs
          .filter((i) => !i.complete || i.naturalWidth === 0)
          .map((i) => i.src),
      );
    assert.deepEqual(broken, []);
  }
  for (const width of [1440, 390, 320])
    for (const [name, path] of [
      ["landing", "/"],
      ["features", "/features"],
      ["demo", "/preview/ai"],
      ["login", "/auth/login"],
      ["register", "/auth/register"],
    ])
      await inspect(name, path, width);
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(base + "/");
  await p
    .locator(".marketing-nav")
    .getByRole("link", { name: "AI 분석", exact: true })
    .click();
  assert.equal(new URL(p.url()).hash, "#ai");
  await p.locator(".faq-list summary").first().focus();
  await p.keyboard.press("Enter");
  assert.equal(
    await p.locator(".faq-list details").first().getAttribute("open"),
    "",
  );
  assert.equal(
    await p.locator('.marketing-header a[href^="/preview/"]').count(),
    0,
  );
  await p.goto(base + "/auth/login");
  await p.locator("#username").fill("campus_test");
  await p.locator("#password").fill("browser-test-password");
  await p.locator(".assignment-form button[type=submit]").click();
  await p.waitForURL(base + "/");
  await p.getByRole("button", { name: "메뉴 열기" }).click();
  assert.equal(
    await p
      .getByRole("button", { name: "메뉴 닫기" })
      .getAttribute("aria-expanded"),
    "true",
  );
  await p.keyboard.press("Escape");
  assert.equal(
    await p
      .getByRole("button", { name: "메뉴 열기" })
      .getAttribute("aria-expanded"),
    "false",
  );
  for (const width of [1440, 390, 320])
    for (const [name, path] of [
      ["dashboard", "/"],
      ["manager", "/assignments"],
      ["archive", "/assignments?view=completed"],
      ["courses", "/courses"],
      ["backup", "/backup"],
      ["calendar", "/calendar"],
      ["ai", "/ai/analyze"],
      ["new", "/assignments/new"],
      ["detail", "/assignments/1"],
      ["schedule", "/schedule"],
      ["empty-search", "/assignments?q=unmatched-campus-fixture"],
    ])
      await inspect(name, path, width);
  fs.writeFileSync(
    "/tmp/campus-checks/results.json",
    JSON.stringify({ failures, errors }, null, 2),
  );
  await p.setViewportSize({ width: 1440, height: 1024 });
  await p.goto(base + "/assignments/new");
  await p.locator("#title").fill("브라우저 검증 과제");
  await p.locator("#course").fill("UX 검증");
  await p.locator("#due_date").fill("2026-11-20");
  await p.locator("#description").fill("실제 폼으로 등록한 테스트 데이터");
  await p.getByRole("button", { name: "과제 등록", exact: true }).click();
  await p.waitForURL(base + "/assignments");
  await p
    .locator(".assignment-row")
    .filter({ hasText: "브라우저 검증 과제" })
    .first()
    .locator(".assignment-title")
    .click();
  await p.waitForURL(/\/assignments\/\d+$/);
  const detailPath = new URL(p.url()).pathname;
  assert.match(await p.locator("h1").innerText(), /브라우저 검증 과제/);
  await p
    .locator(".check-add-form input[name=content]")
    .fill("키보드로 요구사항 검토");
  await p.locator(".check-add-form button").click();
  await p.waitForLoadState();
  await p
    .getByRole("button", {
      name: "완료 표시: 키보드로 요구사항 검토",
      exact: true,
    })
    .click();
  await p.waitForLoadState();
  assert.equal(
    await p.locator(".check-text.checked").innerText(),
    "키보드로 요구사항 검토",
  );
  await p.locator("input[name=attachment]").setInputFiles({
    name: "ux-check.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("campus upload smoke"),
  });
  await p.locator("form:has(input[name=attachment]) button").click();
  await p.waitForLoadState();
  assert.match(await p.locator("#attachments").innerText(), /ux-check.txt/);
  await p.locator("#note-content").fill("검토 완료 기록");
  await p.locator("form:has(#note-content) button").click();
  await p.waitForLoadState();
  assert.match(await p.locator(".note-history").innerText(), /검토 완료 기록/);
  await p.goto(base + detailPath + "/edit");
  await p.locator("#title").fill("수정된 브라우저 과제");
  await p.getByRole("button", { name: "수정 저장" }).click();
  await p.waitForLoadState();
  assert.match(await p.locator("h1").innerText(), /수정된 브라우저 과제/);
  await p.goto(base + "/assignments");
  await p.locator("#dashboard-query").fill("수정된 브라우저");
  await p.getByRole("button", { name: "검색", exact: true }).click();
  await p.waitForLoadState();
  assert.equal(await p.locator(".assignment-row").count(), 1);
  await p.goto(base + "/ai/analyze");
  await p.locator("#notice").fill("운영체제 보고서를 PDF로 제출하세요.");
  await p.locator("#ai-submit-button").click();
  await p.waitForLoadState();
  assert.match(
    await p.locator(".form-errors").innerText(),
    /Gemini API 키가 없습니다/,
  );
  await p.goto(base + detailPath);
  p.once("dialog", (d) => d.accept());
  await p.locator('form[action="' + detailPath + '/delete"] button').click();
  await p.waitForURL(base + "/assignments");
  assert.equal(
    await p
      .locator(".assignment-row")
      .filter({ hasText: "수정된 브라우저 과제" })
      .count(),
    0,
  );
  await p.locator(".logout-button").click();
  await p.waitForURL(base + "/auth/login");
  await p.goto(base + "/assignments/new");
  assert.equal(new URL(p.url()).pathname, "/auth/login");
  fs.writeFileSync(
    "/tmp/campus-checks/results.json",
    JSON.stringify(
      {
        failures,
        errors,
        flows:
          "CRUD, checklist completion, attachment upload, notes, search, AI missing-key error, logout, auth redirect, mobile navigation",
        captures: 48,
      },
      null,
      2,
    ),
  );
  console.log(
    JSON.stringify({
      accessibilityOrLayoutIssues: failures.length,
      browserErrors: errors,
      flows: "passed",
    }),
  );
  await b.close();
  if (failures.length || errors.length) process.exitCode = 1;
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
