import type { ApiFieldErrors } from "./types";

const EMPTY_STATUSES = new Set([204, 205, 304]);
const DEFAULT_ERROR = "요청을 처리하지 못했습니다.";

const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);

function messages(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);
  if (record(value)) return Object.values(value).flatMap(messages);
  return [];
}

function fieldErrors(body: unknown): ApiFieldErrors | undefined {
  if (!record(body)) return undefined;
  const source = record(body.field_errors) ? body.field_errors : body;
  const fields = Object.fromEntries(
    Object.entries(source)
      .filter(([key]) => !["detail", "message", "code"].includes(key))
      .map(([key, value]) => [key, messages(value)])
      .filter(([, value]) => value.length),
  );
  return Object.keys(fields).length ? fields : undefined;
}

export class ApiError extends Error {
  readonly name = "ApiError";
  readonly status: number;
  readonly fields?: ApiFieldErrors;
  readonly body?: unknown;

  constructor(message: string, status: number, fields?: ApiFieldErrors, body?: unknown) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.body = body;
  }
}

async function responseBody(response: Response): Promise<{ json: boolean; value: unknown }> {
  const text = await response.text();
  if (!text) return { json: true, value: null };
  try { return { json: true, value: JSON.parse(text) }; } catch { return { json: false, value: text }; }
}

export async function parseApiError(response: Response, fallback = DEFAULT_ERROR): Promise<ApiError> {
  const { value: body } = await responseBody(response);
  const fields = fieldErrors(body);
  const detail = record(body) && typeof body.detail === "string" ? body.detail : undefined;
  const message = record(body) && typeof body.message === "string" ? body.message : undefined;
  return new ApiError(message ?? detail ?? (fields && Object.values(fields).flat()[0]) ?? fallback, response.status, fields, body);
}

export async function readApiResponse<T>(response: Response, fallback = DEFAULT_ERROR): Promise<T | null> {
  if (EMPTY_STATUSES.has(response.status)) return null;
  if (!response.ok) throw await parseApiError(response, fallback);
  const body = await responseBody(response);
  if (body.value === null) return null;
  if (!body.json) throw new ApiError(fallback, response.status, undefined, body.value);
  return body.value as T;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  fetcher: (path: string, init?: RequestInit) => Promise<Response> = fetch,
): Promise<T | null> {
  return readApiResponse<T>(await fetcher(path, init));
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError");
}
