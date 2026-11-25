import { expect, test, type Page } from "@playwright/test";
import { STUDENT, createImageExam, expiredAccessToken, storedAnswers } from "./support";

/**
 * One real attempt, driven through the UI as the seeded student TA-000001:
 *   a) autosave shows "تم الحفظ ✓" and the answers are in the database
 *   b) a page reload mid-exam resumes, later answers still save, and every answer is scored
 *   c) an expired access token is refreshed transparently -- no redirect to /login
 *   d) every question image loads (preloaded up front), including after navigating/reloading
 *   e) the header's Arabic save text renders (screenshot in e2e/.artifacts/exam-header.png)
 */

const SAVED = "تم الحفظ ✓";
const QUESTIONS = 4;

type AttemptPayload = {
  attempt_id: number;
  violation_count: number;
  questions: { id: number; position: number; image_url: string | null; choices: { id: number; label: string }[] }[];
};

async function attemptPayload(page: Page, attemptId: number): Promise<AttemptPayload> {
  const response = await page.request.get(`/api/v1/me/attempts/${attemptId}`);
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as AttemptPayload;
  payload.questions.sort((a, b) => a.position - b.position);
  return payload;
}

/** Clicks a choice and waits for the debounced autosave round-trip and the "saved" indicator. */
async function answer(page: Page, label: string) {
  const saved = page.waitForResponse((r) => r.request().method() === "PUT" && r.url().includes("/answers") && r.status() === 200);
  await page.getByRole("button", { name: label, exact: true }).click();
  await saved;
  await expect(page.getByText(SAVED, { exact: true })).toBeVisible();
}

async function goToQuestion(page: Page, index: number) {
  for (let guard = 0; guard < QUESTIONS * 2; guard++) {
    const header = await page.getByText(/^سؤال \d+ من \d+$/).textContent();
    const current = Number(header!.match(/\d+/)![0]) - 1;
    if (current === index) return;
    await page.getByRole("button", { name: current < index ? "التالي" : "السابق", exact: true }).click();
  }
  throw new Error(`could not reach question ${index + 1}`);
}

async function expectQuestionImageLoaded(page: Page, url: string) {
  // Match the object path, not the whole URL: every payload load re-signs it (new X-Amz-Date and
  // signature), so the page's URL and one fetched separately by the test differ in the query.
  const img = page.locator(`img[src^="${url.split("?")[0]}?"]`);
  await expect(img).toBeVisible();
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true);
  // ...and nothing anywhere on the page is a broken image.
  const broken = await page.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.src));
  expect(broken).toEqual([]);
}

test("student exam: autosave, resume after reload, token refresh, images", async ({ page, context }) => {
  const exam = await createImageExam(QUESTIONS);
  const labels = exam.answerKey.split(""); // answer every question correctly: A, B, C, D

  page.on("dialog", (dialog) => dialog.accept()); // the runner's beforeunload "leave page?" prompt
  const imageStatus = new Map<string, number>(); // keyed by object path: signed URLs differ per load
  const objectPath = (url: string) => url.split("?")[0]!;
  const refreshStatuses: number[] = [];
  page.on("response", (r) => {
    if (r.url().startsWith("http://localhost:9000/")) imageStatus.set(objectPath(r.url()), r.status());
    if (r.url().endsWith("/api/v1/auth/refresh")) refreshStatuses.push(r.status());
  });

  await test.step("log in as the seeded student", async () => {
    await page.goto("/login");
    await page.locator("#identifier").fill(STUDENT.identifier);
    await page.locator("#password").fill(STUDENT.password);
    await page.locator("#password").press("Enter");
    await page.waitForURL(/\/dashboard$/);
  });

  let attemptId = 0;
  await test.step("start the image exam", async () => {
    await page.goto(`/exams/${exam.examId}`);
    await page.getByRole("button", { name: "بدء الامتحان", exact: true }).click();
    await page.waitForURL(/\/exams\/attempt\/\d+$/);
    attemptId = Number(page.url().match(/attempt\/(\d+)$/)![1]);
    await expect(page.getByText(`سؤال 1 من ${QUESTIONS}`, { exact: true })).toBeVisible();
  });

  let payload = await attemptPayload(page, attemptId);
  const choiceFor = (index: number) => payload.questions[index]!.choices.find((c) => c.label === labels[index])!.id;

  await test.step("d) every question image is preloaded and loads", async () => {
    const urls = payload.questions.map((q) => q.image_url!);
    expect(urls.every(Boolean)).toBe(true);
    // All four were fetched before the student ever navigated to questions 2-4.
    await expect.poll(() => urls.every((u) => imageStatus.get(objectPath(u)) === 200), { message: "all images preloaded" }).toBe(true);
    for (let i = 0; i < QUESTIONS; i++) {
      await goToQuestion(page, i);
      await expectQuestionImageLoaded(page, urls[i]!);
    }
    await goToQuestion(page, 0);
    await expectQuestionImageLoaded(page, urls[0]!); // and again after navigating back
  });

  await test.step("a) answer questions 1-2: saved indicator + rows in the database", async () => {
    await answer(page, labels[0]!);
    await goToQuestion(page, 1);
    await answer(page, labels[1]!);
    const rows = await storedAnswers(attemptId);
    expect(rows.get(payload.questions[0]!.id)).toBe(choiceFor(0));
    expect(rows.get(payload.questions[1]!.id)).toBe(choiceFor(1));
  });

  await test.step("e) the header renders the Arabic save text", async () => {
    const header = page.locator("div.sticky").first();
    await header.screenshot({ path: "e2e/.artifacts/exam-header.png" });
    const saved = header.getByText(SAVED, { exact: true });
    await expect(saved).toBeVisible();
    expect(await page.locator("html").getAttribute("dir")).toBe("rtl");
    // The text is drawn with a loaded web font (not a missing-glyph fallback) and has real width.
    const rendering = await saved.evaluate(async (el) => {
      await document.fonts.ready;
      const family = getComputedStyle(el).fontFamily.split(",")[0]!.trim();
      return { family, loaded: document.fonts.check(`14px ${family}`, el.textContent ?? ""), width: el.getBoundingClientRect().width };
    });
    expect(rendering.loaded, `font ${rendering.family} loaded`).toBe(true);
    expect(rendering.width).toBeGreaterThan(30);

    // The header stays readable while scrolled (phone-sized viewport, scrolled to the bottom):
    // the timer and save status must not end up hidden under the site's own sticky top bar.
    await page.setViewportSize({ width: 390, height: 700 });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    for (const target of [saved, header.getByText(/\d{2}:\d{2}/)]) {
      const hidden = await target.evaluate((el) => {
        const r = el.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return !(hit && (hit === el || el.contains(hit) || hit.contains(el)));
      });
      expect(hidden, `"${await target.textContent()}" is covered by another element while scrolled`).toBe(false);
    }
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => window.scrollTo(0, 0));
  });

  await test.step("b) reload mid-exam: answers survive and numbering continues", async () => {
    await page.reload();
    await expect(page.getByText(`سؤال 1 من ${QUESTIONS}`, { exact: true })).toBeVisible();
    await expect(page.getByText("· تمت الإجابة على 2", { exact: true })).toBeVisible();
    payload = await attemptPayload(page, attemptId); // image URLs are re-signed on every load
    await goToQuestion(page, 2);
    await expectQuestionImageLoaded(page, payload.questions[2]!.image_url!);
    await answer(page, labels[2]!);
    expect((await storedAnswers(attemptId)).get(payload.questions[2]!.id)).toBe(choiceFor(2));
  });

  await test.step("c) expired access token: the save refreshes the session, no /login", async () => {
    const me = (await (await page.request.get("/api/v1/auth/me")).json()) as { id: number };
    const expire = () => context.addCookies([{
      name: "access_token", value: expiredAccessToken(me.id, "student"), domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax",
    }]);
    await expire();
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401); // really rejected now

    const refreshesBefore = refreshStatuses.length;
    await goToQuestion(page, 3);
    await answer(page, labels[3]!);
    expect(refreshStatuses.slice(refreshesBefore)).toEqual([200]);
    expect(page.url()).toMatch(/\/exams\/attempt\/\d+$/);
    expect((await storedAnswers(attemptId)).get(payload.questions[3]!.id)).toBe(choiceFor(3));

    // A full page load with an expired token isn't bounced to /login by the route guard either.
    await expire();
    await page.reload();
    await expect(page.getByText(`سؤال 1 من ${QUESTIONS}`, { exact: true })).toBeVisible();
    expect(page.url()).toMatch(/\/exams\/attempt\/\d+$/);
    await expect(page.getByText(`· تمت الإجابة على ${QUESTIONS}`, { exact: true })).toBeVisible();
  });

  await test.step("b) submit: every answer is scored", async () => {
    await goToQuestion(page, QUESTIONS - 1);
    await page.getByRole("button", { name: "تسليم الامتحان", exact: true }).first().click();
    await page.getByRole("button", { name: "تأكيد", exact: true }).click();
    await expect(page.getByText("100%", { exact: true })).toBeVisible();
    await expect(page.getByText(`${QUESTIONS} من ${QUESTIONS} نقطة`, { exact: true })).toBeVisible();
    const rows = await storedAnswers(attemptId);
    expect(payload.questions.map((q) => rows.get(q.id))).toEqual(payload.questions.map((_, i) => choiceFor(i)));
  });
});
