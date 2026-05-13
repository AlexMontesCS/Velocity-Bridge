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
const DEBUG_RELAY = (Deno.env.get("RELAY_DEBUG") || "").toLowerCase() === "true";

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

function redactPayload(payload: RelayPayload): Record<string, unknown> {
  const { token: _token, ...rest } = payload;
  return {
    ...rest,
    token: _token ? "[redacted]" : undefined,
  };
}

function debugLog(message: string, data?: unknown): void {
  if (!DEBUG_RELAY) {
    return;
  }
  if (data === undefined) {
    console.log(`[relay] ${message}`);
    return;
  }
  console.log(`[relay] ${message}`, data);
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
  const contentType = request.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const payload = (await request.json().catch(() => null)) as RelayPayload | null;
    if (!payload || typeof payload !== "object") {
      throw new HttpError(400, "Invalid JSON payload");
    }
    return payload;
  }

  if (
    contentType.includes("application/x-www-form-urlencoded") ||
    contentType.includes("multipart/form-data")
  ) {
    const formData = await request.formData().catch(() => null);
    if (!formData) {
      throw new HttpError(400, "Invalid form payload");
    }

    const payload: Record<string, string> = {};
    for (const [key, value] of formData.entries()) {
      payload[key] = typeof value === "string" ? value : value.name;
    }
    return payload as RelayPayload;
  }

  const text = await request.text();
  if (!text.trim()) {
    throw new HttpError(400, "Invalid request payload");
  }

  try {
    return JSON.parse(text) as RelayPayload;
  } catch {
    throw new HttpError(400, "Invalid request payload");
  }
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

async function subscribeSSE(
  pairId: string,
  target: Target,
  params: URLSearchParams,
): Promise<Response> {
  const token = params.get("token") || "";
  await requirePair(pairId, token);

  const prefix = messagePrefix(pairId, target);
  const timeoutSeconds = safeNumber(params.get("timeout"), 30);
  const maxEvents = safeNumber(params.get("max_events"), 50);

  let eventCount = 0;
  const headers = new Headers({
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache",
    "access-control-allow-origin": "*",
    "connection": "keep-alive",
  });

  const body = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      const startTime = Date.now();
      const timeoutMs = timeoutSeconds * 1000;

      try {
        // Stream the initial ":ready" comment to confirm connection
        controller.enqueue(encoder.encode(": ready\n\n"));

        const watchIterator = kv.watch(prefix);
        for await (const entries of watchIterator) {
          for (const entry of entries) {
            const message = entry.value as StoredMessage;
            if (!message) continue;

            eventCount++;
            debugLog(`SSE event #${eventCount}`, { pairId, target, id: message.id });

            // Send as SSE event (client may disconnect mid-stream)
            try {
              const event = `data: ${JSON.stringify(message)}\n\n`;
              controller.enqueue(encoder.encode(event));
            } catch (enqueueErr) {
              debugLog("SSE enqueue failed (client likely disconnected)", enqueueErr);
              try {
                controller.close();
              } catch {
                /* already closed */
              }
              return;
            }

            // Close after max events or timeout
            if (eventCount >= maxEvents || Date.now() - startTime > timeoutMs) {
              debugLog("SSE closing", { eventCount, pairId, target });
              try {
                controller.close();
              } catch {
                /* already closed */
              }
              return;
            }
          }
        }
      } catch (error) {
        if (error instanceof Deno.errors.Interrupted) {
          // Normal closure
          debugLog("SSE interrupted", { eventCount, pairId, target });
        } else {
          console.error("SSE error:", error);
          const detail =
            error instanceof Error && error.message
              ? error.message.slice(0, 300)
              : "Stream error";
          try {
            const errorMsg =
              `event: error\ndata: ${JSON.stringify({ detail })}\n\n`;
            controller.enqueue(encoder.encode(errorMsg));
          } catch {
            /* controller closed */
          }
        }
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      }
    },
  });

  return new Response(body, { headers });
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
    debugLog("incoming request", {
      method: request.method,
      path: url.pathname,
      query: url.search,
      contentType: request.headers.get("content-type"),
      userAgent: request.headers.get("user-agent"),
    });

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
        debugLog("parsed post payload", redactPayload(payload));
        return json(await postMessage(pairId, target, payload));
      }

      if (request.method === "GET") {
        return json(await getMessages(pairId, target, url.searchParams));
      }
    }

    // GET /v1/pairs/{pairId}/subscribe/{target} - SSE endpoint
    if (
      parts.length === 5 &&
      parts[0] === "v1" &&
      parts[1] === "pairs" &&
      parts[3] === "subscribe"
    ) {
      const pairId = parts[2];
      const target = requireTarget(parts[4]);

      if (request.method === "GET") {
        return await subscribeSSE(pairId, target, url.searchParams);
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
      debugLog("parsed phone payload", redactPayload(payload));

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
