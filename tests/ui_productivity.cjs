// Run against the isolated tests/ui_server.py fixture only.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const base = "http://127.0.0.1:5001";
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 1024 } });
  await p.goto(base + "/auth/login");
  await p.locator("#username").fill("campus_test");
  await p.locator("#password").fill("browser-test-password");
  await p.locator(".assignment-form button[type=submit]").click();
  await p.waitForURL(base + "/");
  await p.goto(base + "/assignments/1");
  await p
    .getByRole("button", { name: "오늘 할 일에 추가", exact: true })
    .first()
    .click();
  await p.waitForLoadState();
  await p.goto(base + "/");
  assert.match(
    await p.locator(".today-list").first().innerText(),
    /자료 조사와 요구사항 정리/,
  );
  await p
    .getByRole("button", {
      name: "오늘 할 일 완료: 자료 조사와 요구사항 정리",
      exact: true,
    })
    .click();
  await p.waitForLoadState();
  assert.equal(new URL(p.url()).pathname, "/");
  await p.goto(base + "/assignments");
  let row = p
    .locator(".assignment-row")
    .filter({ hasText: "트리 구현 및 분석" });
  await row.locator("select[name=status]").selectOption("done");
  await row.locator("button[type=submit]").click();
  await p.waitForLoadState();
  assert.equal(
    await p
      .locator(".assignment-row")
      .filter({ hasText: "트리 구현 및 분석" })
      .count(),
    0,
  );
  await p
    .locator(".assignment-tabs")
    .getByRole("link", { name: /완료 보관함/ })
    .click();
  row = p.locator(".assignment-row").filter({ hasText: "트리 구현 및 분석" });
  assert.equal(await row.count(), 1);
  await row.locator("select[name=status]").selectOption("doing");
  await row.locator("button[type=submit]").click();
  await p.waitForLoadState();
  await p.goto(base + "/courses");
  await p.locator(".course-summary").filter({ hasText: "자료구조" }).click();
  assert.equal(await p.locator(".assignment-row").count(), 1);
  await p.goto(base + "/assignments/1");
  await p.locator("input[name=attachment]").setInputFiles({
    name: "backup-smoke.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("browser backup payload"),
  });
  await p.locator("form:has(input[name=attachment]) button").click();
  await p.waitForLoadState();
  await p.goto(base + "/backup");
  const downloadPromise = p.waitForEvent("download");
  await p.getByRole("button", { name: "내 데이터 ZIP 다운로드" }).click();
  const download = await downloadPromise;
  await download.saveAs("/tmp/campus-backup-smoke.zip");
  assert.ok(fs.statSync("/tmp/campus-backup-smoke.zip").size > 100);
  await p.locator("#backup-file").setInputFiles("/tmp/campus-backup-smoke.zip");
  await p.locator("input[name=confirm]").check();
  await p.getByRole("button", { name: "백업 복원하기" }).click();
  await p.waitForURL(/\/assignments\?view=all/);
  assert.equal(await p.locator(".assignment-row").count(), 6);
  assert.match(await p.locator(".toast").innerText(), /3개 과제/);
  console.log(
    "Pin, complete, quick status, archive, reopen, course filter, ZIP download and additive restore passed",
  );
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
