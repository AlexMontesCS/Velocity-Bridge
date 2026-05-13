/**
 * Velocity Bridge Relay - Deno Deploy
 * Serverless relay for phone-to-desktop clipboard sync
 * 
 * Deploy: https://dash.deno.com
 */

type Target = "desktop" | "phone";
type RelayKind = "clipboard" | "command" | "response";

interface RelayPayload {
  token: string;
  kind?: RelayKind;
  type?: string;
  content?: string;
  image?: string;
  filename?: string;
  command?: string;
  request_id?: string;
  correlation_id?: string;
}

interface StoredMessage {
  id: number;
  target: Target;
  kind: RelayKind;
  correlation_id?: string;
  payload: Omit<RelayPayload, "token">;
  created_at: number;
}

const MAX_LIMIT = 100;
const MESSAGE_TTL_SECONDS = 86400; // 24 hours
const kv = await Deno.openKv();

class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

function json(body: unknown, status = 200): Response {
  const headers = new Headers({
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
  });
  return new Response(JSON.stringify(body), { status, headers });
}

async function sha256(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function pairKey(pairId: string): string[] {
  return ["pair", pairId, "token"];
}

function messageKey(pairId: string, target: Target, id: number): string[] {
  return ["pair", pairId, "msg", target, String(id).padStart(16, "0")];
}

function messagePrefix(pairId: string, target: Target): string[] {
  return ["pair", pairId, "msg", target];
}

function safeNumber(value: string | null | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function withoutToken(payload: RelayPayload): Omit<RelayPayload, "token"> {
  const { token: _token, ...rest } = payload;
  return rest;
}

function requireTarget(value: string): Target {
  if (value === "desktop" || value === "phone") {
    return value;
  }
  throw new HttpError(400, "Invalid message target");
}

async function requirePair(pairId: string, token: string): Promise<void> {
  if (!pairId || pairId.length > 80) {
    throw new HttpError(400, "Invalid pair id");
  }
  if (!token || token.length < 8) {
    throw new HttpError(422, "Relay token must be at least 8 characters");
  }

  const tokenHash = await sha256(token);
  const key = pairKey(pairId);
  const existing = await kv.get(key);

  if (!existing.value) {
    await kv.set(key, tokenHash, { expireIn: MESSAGE_TTL_SECONDS * 1000 });
    return;
  }

  if (existing.value !== tokenHash) {
    throw new HttpError(403, "Invalid relay token");
  }
}

async function readPayload(request: Request): Promise<RelayPayload> {
  const payload = (await request.json().catch(() => null)) as RelayPayload | null;
  if (!payload || typeof payload !== "object") {
    throw new HttpError(400, "Invalid JSON payload");
  }
  return payload;
}

async function postMessage(
  pairId: string,
  target: Target,
  payload: RelayPayload,
): Promise<Record<string, unknown>> {
  await requirePair(pairId, payload.token);

  const now = Math.floor(Date.now() / 1000);
  const id = Date.now() * 1000 + Math.floor(Math.random() * 1000);
  const correlationId = payload.correlation_id || payload.request_id;
  const payloadWithoutToken = withoutToken(payload);
  const kind = payload.kind || "clipboard";

  const message: StoredMessage = {
    id,
    target,
    kind,
    correlation_id: correlationId,
    payload: payloadWithoutToken,
    created_at: now,
  };

  const key = messageKey(pairId, target, id);
  await kv.set(key, message, { expireIn: MESSAGE_TTL_SECONDS * 1000 });

  return { status: "queued", id, expires_in: MESSAGE_TTL_SECONDS };
}

async function getMessages(
  pairId: string,
  target: Target,
  params: URLSearchParams,
): Promise<Record<string, unknown>> {
  const token = params.get("token") || "";
  await requirePair(pairId, token);

  const after = safeNumber(params.get("after"), 0);
  const limit = Math.min(Math.max(safeNumber(params.get("limit"), 25), 1), MAX_LIMIT);
  const correlationId = params.get("correlation_id");
  const prefix = messagePrefix(pairId, target);

  const messages: StoredMessage[] = [];
  const entries = kv.list({ prefix });

  for await (const entry of entries) {
    const message = entry.value as StoredMessage;
    if (!message || message.id <= after) {
      continue;
    }
    if (correlationId && message.correlation_id !== correlationId) {
      continue;
    }
    messages.push(message);
    if (messages.length >= limit) break;
  }

  messages.sort((a, b) => a.id - b.id);
  const page = messages.slice(0, limit);

  return {
    status: "success",
    messages: page,
    cursor: page.length ? page[page.length - 1].id : after,
  };
}

Deno.serve(async (request: Request): Promise<Response> => {
  try {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "content-type",
        },
      });
    }

    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);

    // Health check
    if (url.pathname === "/" && request.method === "GET") {
      return json({ status: "ok", service: "Velocity Bridge Relay (Deno Deploy)" });
    }

    // POST/GET /v1/pairs/{pairId}/messages/{target}
    if (
      parts.length === 5 &&
      parts[0] === "v1" &&
      parts[1] === "pairs" &&
      parts[3] === "messages"
    ) {
      const pairId = parts[2];
      const target = requireTarget(parts[4]);

      if (request.method === "POST") {
        const payload = await readPayload(request);
        return json(await postMessage(pairId, target, payload));
      }

      if (request.method === "GET") {
        return json(await getMessages(pairId, target, url.searchParams));
      }
    }

    // Special phone endpoints: /v1/pairs/{pairId}/phone/{action}
    if (
      parts.length === 5 &&
      parts[0] === "v1" &&
      parts[1] === "pairs" &&
      parts[3] === "phone"
    ) {
      const pairId = parts[2];
      const action = parts[4];

      if (request.method !== "POST") {
        throw new HttpError(405, "Method not allowed");
      }

      const payload = await readPayload(request);

      if (action === "send") {
        // iOS sends clipboard → deliver to desktop
        payload.kind = "clipboard";
        return json(await postMessage(pairId, "desktop", payload));
      }

      if (action === "request_clipboard") {
        // iOS requests clipboard from desktop
        const requestId = payload.request_id || crypto.randomUUID();
        const queued = await postMessage(pairId, "desktop", {
          token: payload.token,
          kind: "command",
          command: "get_clipboard",
          request_id: requestId,
          correlation_id: requestId,
        });
        return json({
          status: "queued",
          request_id: requestId,
          message_id: queued.id,
        });
      }

      throw new HttpError(404, "Unknown phone action");
    }

    return json({ detail: "Not found" }, 404);
  } catch (error) {
    if (error instanceof HttpError) {
      return json({ detail: error.message }, error.status);
    }
    console.error("Relay error:", error);
    return json({ detail: "Internal server error" }, 500);
  }
});
