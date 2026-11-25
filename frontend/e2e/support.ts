import { createHmac } from "node:crypto";
import { deflateSync } from "node:zlib";
import { request, type APIRequestContext } from "@playwright/test";
import { Client } from "pg";

export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3001";
// Read-only verification queries. Refuses anything but a dedicated *_e2e database, so a
// misconfigured run can never point these at the dev database.
const DATABASE_URL = process.env.E2E_DATABASE_URL ?? "postgresql://talent:talent@localhost:5432/talent_e2e";
// Must match SECRET_KEY of the backend under test (docker-compose.e2e.yml).
const JWT_SECRET = process.env.E2E_JWT_SECRET ?? "e2e-only-secret-key-never-used-anywhere-else-0123456789";

export const ADMIN = { identifier: "admin@talent.dev", password: "Admin123!Dev" };
export const STUDENT = { identifier: "TA-000001", password: "Student123!" }; // seeded by app.cli.seed_dev

// ---------------------------------------------------------------------------------- images ----

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf: Buffer): number {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

/** A real, browser-decodable RGB PNG (a solid colour), so "image loaded" is a meaningful check. */
export function solidPng(width: number, height: number, [r, g, b]: [number, number, number]): Buffer {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8-bit depth, truecolour, default compression/filter/interlace
  const row = Buffer.alloc(1 + width * 3);
  for (let x = 0; x < width; x++) row.set([r, g, b], 1 + x * 3);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ------------------------------------------------------------------------------------- JWT ----

/** An access token exactly like the backend's (HS256, sub/role/sid/exp) but already expired. */
export function expiredAccessToken(userId: number, role: "student" | "admin"): string {
  const b64 = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const head = b64({ alg: "HS256", typ: "JWT" });
  const body = b64({ sub: String(userId), role, sid: "e2e-expired", exp: Math.floor(Date.now() / 1000) - 120 });
  const signature = createHmac("sha256", JWT_SECRET).update(`${head}.${body}`).digest("base64url");
  return `${head}.${body}.${signature}`;
}

// --------------------------------------------------------------------------------- admin API ----

async function csrfHeader(api: APIRequestContext): Promise<Record<string, string>> {
  const csrf = (await api.storageState()).cookies.find((c) => c.name === "csrf_token")?.value;
  return csrf ? { "X-CSRF-Token": csrf } : {};
}

export async function adminApi(): Promise<APIRequestContext> {
  const api = await request.newContext({ baseURL: BASE_URL });
  const login = await api.post("/api/v1/auth/login", { data: { ...ADMIN, remember: false } });
  if (!login.ok()) throw new Error(`admin login failed: ${login.status()} ${await login.text()}`);
  return api;
}

export type ExamFixture = { examId: number; title: string; questionCount: number; answerKey: string };

/** A published exam of N image questions in the seeded course, with answer key "ABCD...". */
export async function createImageExam(questionCount: number): Promise<ExamFixture> {
  const api = await adminApi();
  try {
    const courses = (await (await api.get("/api/v1/admin/courses")).json()) as { id: number; title: string }[];
    const course = courses.find((c) => c.title === "SAT Math — Basics");
    if (!course) throw new Error("seeded course 'SAT Math — Basics' not found -- is this the seeded E2E stack?");

    const title = `E2E image exam ${Date.now()}`;
    const created = await api.post("/api/v1/admin/exams", {
      headers: await csrfHeader(api),
      data: { title, course_id: course.id, exam_mode: "full", duration_minutes: 60, passing_score: 50, max_attempts: 1, ends_at: null },
    });
    if (created.status() !== 201) throw new Error(`create exam: ${created.status()} ${await created.text()}`);
    const examId = ((await created.json()) as { id: number }).id;

    const colours: [number, number, number][] = [[220, 38, 38], [37, 99, 235], [22, 163, 74], [202, 138, 4], [147, 51, 234], [8, 145, 178]];
    // The endpoint reads a repeated "files" field, which only a real FormData can express.
    const form = new FormData();
    for (let i = 0; i < questionCount; i++) {
      const png = new Uint8Array(solidPng(480, 240, colours[i % colours.length]!));
      form.append("files", new File([png], `q${i + 1}.png`, { type: "image/png" }));
    }
    form.append("topic", "E2E");
    const upload = await api.post(`/api/v1/admin/exams/${examId}/question-images`, { headers: await csrfHeader(api), multipart: form });
    if (upload.status() !== 201) throw new Error(`upload images: ${upload.status()} ${await upload.text()}`);

    const answerKey = "ABCD".repeat(Math.ceil(questionCount / 4)).slice(0, questionCount);
    const key = await api.post(`/api/v1/admin/exams/${examId}/answer-key`, { headers: await csrfHeader(api), data: { answers: answerKey } });
    if (!key.ok()) throw new Error(`answer key: ${key.status()} ${await key.text()}`);
    return { examId, title, questionCount, answerKey };
  } finally {
    await api.dispose();
  }
}

// ------------------------------------------------------------------------------------ DB ----

export async function storedAnswers(attemptId: number): Promise<Map<number, number | null>> {
  const dbName = new URL(DATABASE_URL).pathname.slice(1);
  if (!dbName.endsWith("_e2e")) throw new Error(`refusing to query non-E2E database "${dbName}"`);
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    const { rows } = await client.query<{ question_id: number; choice_id: number | null }>(
      "SELECT question_id, choice_id FROM exam_answers WHERE attempt_id = $1", [attemptId],
    );
    return new Map(rows.map((r) => [r.question_id, r.choice_id]));
  } finally {
    await client.end();
  }
}
