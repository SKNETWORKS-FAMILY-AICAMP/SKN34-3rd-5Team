import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";
import { chromium } from "/tmp/pw/node_modules/playwright/index.mjs";

const base = "http://127.0.0.1:18110";
const suffix = randomBytes(5).toString("hex");
const users = [`w0ui${suffix}a`, `w0ui${suffix}b`];
const password = `W0!a${randomBytes(12).toString("hex")}`;
const title = `W0 UI E2E ${suffix}`;
const updatedTitle = `${title} updated`;
const content = `browser draft ${suffix}`;
const comment = `browser comment ${suffix}`;
writeFileSync("/results/owned.json", JSON.stringify({ users }));

const browser = await chromium.launch({ headless: true });

async function newPage() {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  return { context, page };
}

async function login(username) {
  const session = await newPage();
  await session.page.goto(`${base}/login`);
  await session.page.locator("#login-id").fill(username);
  await session.page.locator("#login-password").fill(password);
  await session.page.getByRole("button", { name: "로그인", exact: true }).click();
  await session.page.waitForURL(/\/routes\/new$/);
  const tokenResponse = await session.context.request.post(`${base}/api/auth/signin`, { data: { username, password } });
  const result = await tokenResponse.json();
  assert.equal(tokenResponse.status(), 200);
  assert.equal(typeof result.access, "string");
  return { ...session, access: result.access };
}

try {
  const anonymous = await newPage();
  await anonymous.page.goto(`${base}/community`);
  await anonymous.page.getByRole("heading", { name: "자유 게시판", exact: true }).waitFor();
  await anonymous.page.getByRole("link", { name: "로그인", exact: true }).waitFor();
  await anonymous.context.close();
  console.log("PASS anonymous community read");

  const setup = await newPage();
  for (const [index, username] of users.entries()) {
    const response = await setup.context.request.post(`${base}/api/auth/signup/`, { data: {
      username, email: `${username}@example.test`, password, re_password: password,
      first_name: `W0 UI ${index + 1}`, birth_date: "2000-01-01", gender: index ? "F" : "M",
    } });
    assert.equal(response.status(), 201);
  }
  await setup.context.close();

  let session = await login(users[0]);
  let { context, page } = session;
  await page.goto(`${base}/community`);
  await page.getByRole("button", { name: "글쓰기", exact: true }).first().click();
  const editor = page.getByRole("dialog");
  await editor.getByLabel("제목").fill(title);
  await editor.getByLabel("내용").fill(content);
  await page.route("**/api/community/posts/", route => route.request().method() === "POST"
    ? route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporary test failure" }) })
    : route.continue());
  await editor.getByRole("button", { name: "저장", exact: true }).click();
  await editor.getByRole("alert").waitFor();
  assert.equal(await editor.getByLabel("제목").inputValue(), title);
  assert.equal(await editor.getByLabel("내용").inputValue(), content);
  await page.unroute("**/api/community/posts/");
  await editor.getByRole("button", { name: "저장", exact: true }).click();
  await page.waitForURL(url => new URL(url).searchParams.has("post"));
  const postUrl = page.url();
  const postId = new URL(postUrl).searchParams.get("post");
  assert.ok(postId);
  await page.getByText(title, { exact: true }).first().waitFor();
  await page.getByRole("navigation", { name: "게시글 이동" }).getByRole("button", { name: "글쓰기", exact: true }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "게시글 작성" }).waitFor();
  await page.getByRole("dialog").getByRole("button", { name: "취소", exact: true }).click();
  console.log("PASS bottom shared editor and error draft preservation");

  await page.getByRole("button", { name: "수정", exact: true }).first().click();
  await page.getByRole("dialog").getByLabel("제목").fill(updatedTitle);
  await page.getByRole("dialog").getByRole("button", { name: "저장", exact: true }).click();
  await page.getByText(updatedTitle, { exact: true }).first().waitFor();

  await page.getByLabel("댓글 내용").fill(comment);
  await page.getByRole("button", { name: "등록", exact: true }).click();
  const commentItem = page.getByRole("listitem").filter({ hasText: comment });
  await commentItem.waitFor();
  page.once("dialog", dialog => dialog.accept());
  await commentItem.getByRole("button", { name: "삭제", exact: true }).click();
  await commentItem.waitFor({ state: "detached" });

  let upvote = page.getByRole("button", { name: /^추천 \d+$/ });
  await upvote.waitFor({ state: "visible" });
  await upvote.click();
  await page.locator('button[aria-pressed="true"]').filter({ hasText: "추천" }).waitFor();
  await page.reload();
  upvote = page.getByRole("button", { name: /^추천 \d+$/ });
  await page.locator('button[aria-pressed="true"]').filter({ hasText: "추천" }).waitFor();
  await upvote.click();
  await page.locator('button[aria-pressed="false"]').filter({ hasText: "추천" }).waitFor();

  await page.getByRole("button", { name: "신고", exact: true }).click();
  const report = page.getByRole("dialog", { name: "게시글 신고" });
  await report.getByLabel("상세 사유").fill("W0 browser persistence check");
  await report.getByRole("button", { name: "신고 접수", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "신고를 접수했어요" }).waitFor();
  console.log("PASS owner update, comment, refreshed vote state, and report UI");
  await context.close();

  session = await login(users[1]);
  ({ context, page } = session);
  await page.goto(postUrl);
  await page.getByText(updatedTitle, { exact: true }).first().waitFor();
  assert.equal(await page.getByRole("button", { name: "수정", exact: true }).count(), 0);
  const forbidden = await page.evaluate(async ({ postId, access }) => {
    const response = await fetch(`/api/community/posts/${encodeURIComponent(postId)}/`, {
      method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${access}` },
      body: JSON.stringify({ title: "forbidden" }),
    });
    return response.status;
  }, { postId, access: session.access });
  assert.equal(forbidden, 403);
  await page.goto(`${base}/community/predictions`);
  await page.locator("article").first().waitFor();
  assert.ok(await page.locator("article").count() >= 1);
  assert.equal((await page.locator("body").innerText()).includes("W0 E2E FIXTURE"), false);
  let openCard = null;
  for (let index = 0; index < await page.locator("article").count(); index += 1) {
    const candidate = page.locator("article").nth(index);
    if (await candidate.getByRole("button").first().isEnabled()) { openCard = candidate; break; }
  }
  if (openCard) {
    const cardId = await openCard.getAttribute("id");
    const choices = openCard.getByRole("button");
    const waitPressed = (index, value) => page.waitForFunction(({ cardId, index, value }) =>
      document.getElementById(cardId)?.querySelectorAll("button")[index]?.getAttribute("aria-pressed") === value,
    { cardId, index, value });
    await choices.nth(0).click();
    await waitPressed(0, "true");
    await page.reload();
    openCard = page.locator(`[id="${cardId}"]`);
    await openCard.getByRole("button").nth(0).waitFor();
    await waitPressed(0, "true");
    await openCard.getByRole("button").nth(1).click();
    await waitPressed(1, "true");
    await openCard.getByRole("button").nth(1).click();
    await waitPressed(1, "false");
    console.log("PASS different-user 403 and live prediction choice/change/cancel/reload");
  } else {
    console.log("DEFERRED live prediction vote: no open fresh game; cards rendered from live source");
  }
  await context.close();

  session = await login(users[0]);
  ({ context, page } = session);
  await page.goto(postUrl);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "삭제", exact: true }).first().click();
  await page.waitForURL(`${base}/community`);
  assert.equal(await page.getByText(updatedTitle, { exact: true }).count(), 0);
  console.log("PASS owner delete UI");
  await context.close();
} finally {
  await browser.close();
}
