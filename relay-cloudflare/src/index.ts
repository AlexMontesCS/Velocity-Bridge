interface Env {
  VELOCITY_MESSAGES: KVNamespace;
  MESSAGE_TTL_SECONDS?: string;
}

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

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }));
    }

    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);

    try {
      if (url.pathname === "/" && request.method === "GET") {
        return json({ status: "ok", service: "Velocity Bridge Relay" });
      }

      if (parts.length === 5 && parts[0] === "v1" && parts[1] === "pairs" && parts[3] === "messages") {
        const pairId = parts[2];
        const target = requireTarget(parts[4]);

        if (request.method === "POST") {
          const payload = await readPayload(request);
          return json(await postMessage(env, pairId, target, payload));
        }

        if (request.method === "GET") {
          return json(await getMessages(env, pairId, target, url.searchParams));
        }
      }

      if (parts.length === 5 && parts[0] === "v1" && parts[1] === "pairs" && parts[3] === "phone") {
        const pairId = parts[2];
        const action = parts[4];
        const payload = await readPayload(request);

        if (request.method === "POST" && action === "send") {
          payload.kind = "clipboard";
          return json(await postMessage(env, pairId, "desktop", payload));
        }

        if (request.method === "POST" && action === "request_clipboard") {
          const requestId = payload.request_id || crypto.randomUUID();
          const queued = await postMessage(env, pairId, "desktop", {
            token: payload.token,
            kind: "command",
            command: "get_clipboard",
            request_id: requestId,
            correlation_id: requestId,
          });
          return json({ status: "queued", request_id: requestId, message_id: queued.id });
        }
      }

      return json({ detail: "Not found" }, 404);
    } catch (error) {
      if (error instanceof HttpError) {
        return json({ detail: error.message }, error.status);
      }
      return json({ detail: String(error) }, 500);
    }
  },
};

async function postMessage(
  env: Env,
  pairId: string,
  target: Target,
  payload: RelayPayload,
): Promise<Record<string, unknown>> {
  await requirePair(env, pairId, payload.token);

  const now = Math.floor(Date.now() / 1000);
  const ttlSeconds = messageTtl(env);
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

  await env.VELOCITY_MESSAGES.put(messageKey(pairId, target, id), JSON.stringify(message), {
    expirationTtl: ttlSeconds,
  });

  return { status: "queued", id, expires_in: ttlSeconds };
}

async function getMessages(
  env: Env,
  pairId: string,
  target: Target,
  params: URLSearchParams,
): Promise<Record<string, unknown>> {
  const token = params.get("token") || "";
  await requirePair(env, pairId, token);

  const after = safeNumber(params.get("after"), 0);
  const limit = Math.min(Math.max(safeNumber(params.get("limit"), 25), 1), MAX_LIMIT);
  const correlationId = params.get("correlation_id");
  const prefix = messagePrefix(pairId, target);
  const listed = await env.VELOCITY_MESSAGES.list({ prefix, limit: 1000 });
  const messages: StoredMessage[] = [];

  for (const key of listed.keys) {
    const id = Number(key.name.slice(prefix.length));
    if (!Number.isFinite(id) || id <= after) {
      continue;
    }

    const message = await env.VELOCITY_MESSAGES.get<StoredMessage>(key.name, "json");
    if (!message) {
      continue;
    }
    if (correlationId && message.correlation_id !== correlationId) {
      continue;
    }

    messages.push(message);
  }

  messages.sort((a, b) => a.id - b.id);
  const page = messages.slice(0, limit);
  return {
    status: "success",
    messages: page,
    cursor: page.length ? page[page.length - 1].id : after,
  };
}

async function requirePair(env: Env, pairId: string, token: string): Promise<void> {
  if (!pairId || pairId.length > 80) {
    throw new HttpError(400, "Invalid pair id");
  }
  if (!token || token.length < 8) {
    throw new HttpError(422, "Relay token must be at least 8 characters");
  }

  const tokenHash = await sha256(token);
  const key = pairKey(pairId);
  const existingHash = await env.VELOCITY_MESSAGES.get(key);

  if (!existingHash) {
    await env.VELOCITY_MESSAGES.put(key, tokenHash);
    return;
  }

  if (existingHash !== tokenHash) {
    throw new HttpError(403, "Invalid relay token");
  }
}

function requireTarget(value: string): Target {
  if (value === "desktop" || value === "phone") {
    return value;
  }
  throw new HttpError(400, "Invalid message target");
}

async function readPayload(request: Request): Promise<RelayPayload> {
  const payload = (await request.json().catch(() => null)) as RelayPayload | null;
  if (!payload || typeof payload !== "object") {
    throw new HttpError(400, "Invalid JSON payload");
  }
  return payload;
}

function withoutToken(payload: RelayPayload): Omit<RelayPayload, "token"> {
  const { token: _token, ...rest } = payload;
  return rest;
}

function messageTtl(env: Env): number {
  return Math.max(60, safeNumber(env.MESSAGE_TTL_SECONDS, 86400));
}

function safeNumber(value: string | null | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function pairKey(pairId: string): string {
  return `pair:${pairId}:token`;
}

function messagePrefix(pairId: string, target: Target): string {
  return `pair:${pairId}:msg:${target}:`;
}

function messageKey(pairId: string, target: Target, id: number): string {
  return `${messagePrefix(pairId, target)}${String(id).padStart(16, "0")}`;
}

async function sha256(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function json(body: unknown, status = 200): Response {
  return withCors(
    new Response(JSON.stringify(body), {
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    }),
  );
}

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("access-control-allow-origin", "*");
  headers.set("access-control-allow-methods", "GET,POST,OPTIONS");
  headers.set("access-control-allow-headers", "content-type");
  return new Response(response.body, { status: response.status, headers });
}

class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
