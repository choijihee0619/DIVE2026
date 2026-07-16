import { getSessionCookie } from "@/lib/session-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** backend/app/core/responses.py::success_envelope / error_envelope 그대로. */
interface SuccessEnvelope<T> {
  status: "Success";
  data: T;
  error: null;
  request_id: string;
}

interface ErrorEnvelope {
  status: "Failed";
  data: null;
  error: { error_code: string; message: string; details: Record<string, unknown> };
  request_id: string;
}

type Envelope<T> = SuccessEnvelope<T> | ErrorEnvelope;

export class ApiError extends Error {
  errorCode: string;
  details: Record<string, unknown>;
  httpStatus: number;
  requestId: string;

  constructor(errorCode: string, message: string, httpStatus: number, requestId: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.errorCode = errorCode;
    this.httpStatus = httpStatus;
    this.requestId = requestId;
    this.details = details;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** FormData 등 이미 인코딩된 body를 그대로 전달할 때 사용(예: 파일 업로드). */
  rawBody?: BodyInit;
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getSessionCookie();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let body: BodyInit | undefined;
  if (options.rawBody !== undefined) {
    body = options.rawBody;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body,
  });

  const requestId = res.headers.get("X-Request-ID") ?? "";
  let envelope: Envelope<T>;
  try {
    envelope = (await res.json()) as Envelope<T>;
  } catch {
    throw new ApiError("ERROR-PARSE", "응답을 해석할 수 없습니다.", res.status, requestId);
  }

  if (envelope.status === "Failed" || !res.ok) {
    const err = envelope.status === "Failed" ? envelope.error : null;
    throw new ApiError(
      err?.error_code ?? "ERROR-UNKNOWN",
      err?.message ?? "알 수 없는 오류가 발생했습니다.",
      res.status,
      envelope.request_id,
      err?.details ?? {},
    );
  }

  return envelope.data;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: "DELETE" }),
};
