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
/**
 * Deno KV rejects values > 65536 bytes after V8 serialization (not JSON.stringify).
 * JSON length can be under the limit while the stored value still overflows — use a margin.
 */
const KV_MAX_MESSAGE_BYTES = 52_000;
/** Base64 is ASCII; leave headroom for V8/KV encoding overhead on each chunk value. */
const IMAGE_CHUNK_CHARS = 50_000;
/** Deno Deploy: many mutations per atomic; we keep ≤10 for compatibility with older limits. */
const MAX_IMAGE_SHARDS = 8;
/** Keep idle SSE responses alive across serverless/proxy idle timers. */
const SSE_HEARTBEAT_MS = 15_000;
/** Exact-read inbox index used as a fallback when prefix listing misses recent writes. */
const INBOX_INDEX_LIMIT = 500;

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

/** Out-of-band storage for large base64 image slices (not under `messagePrefix`). */
function imageChunkKey(pairId: string, target: Target, id: number, idx: number): Deno.KvKey {
  return ["pair", pairId, "img", target, String(id), String(idx).padStart(3, "0")];
}

function jsonUtf8ByteLength(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value)).length;
}

function isKvValueTooLargeError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const m = err.message;
  return (
    m.includes("65536") ||
    /value too large|too large \(max \d+ bytes\)/i.test(m)
  );
}

function shardCountFromPayload(p: Record<string, unknown>): number {
  const raw = p._relay_image_shards;
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return Math.max(0, Math.floor(raw));
  }
  if (typeof raw === "string" && /^\d+$/.test(raw)) {
    return parseInt(raw, 10);
  }
  return 0;
}

/** KV may deserialize string chunks as Uint8Array in some paths; normalize without corrupting bytes. */
function kvChunkToString(value: unknown): string {
  if (typeof value === "string") return value;
  if (value instanceof Uint8Array) {
    return new TextDecoder("latin1").decode(value);
  }
  if (value instanceof ArrayBuffer) {
    return new TextDecoder("latin1").decode(new Uint8Array(value));
  }
  throw new HttpError(500, "Relay image shard has unexpected type");
}

async function hydrateShardedMessage(
  pairId: string,
  target: Target,
  message: StoredMessage,
): Promise<StoredMessage> {
  const p = message.payload as Record<string, unknown>;
  const n = shardCountFromPayload(p);
  if (n <= 0) {
    return message;
  }
  const parts: string[] = [];
  for (let i = 0; i < n; i++) {
    const r = await kv.get(imageChunkKey(pairId, target, message.id, i));
    if (r.value === null || r.value === undefined) {
      throw new HttpError(500, "Relay image shard missing");
    }
    parts.push(kvChunkToString(r.value));
  }
  const { _relay_image_shards: _s, ...clean } = p;
  const newPayload = { ...clean, image: parts.join("") } as Omit<RelayPayload, "token">;
  return { ...message, payload: newPayload };
}

/** Exact key bumped on every new message so `kv.watch` can wake (watch does not support prefix subtrees). */
function streamNotifyKey(pairId: string, target: Target): Deno.KvKey {
  return ["pair", pairId, "sse", target];
}

function inboxIndexKey(pairId: string, target: Target): Deno.KvKey {
  return ["pair", pairId, "idx", target];
}

function sequenceKey(pairId: string): Deno.KvKey {
  return ["pair", pairId, "seq"];
}

async function nextMessageId(pairId: string): Promise<number> {
  const key = sequenceKey(pairId);

  for (let attempt = 0; attempt < 8; attempt++) {
    const current = await kv.get<number>(key);
    const wallClockId = Date.now() * 1000 + Math.floor(Math.random() * 1000);
    const previous = typeof current.value === "number" ? current.value : 0;
    const next = Math.max(previous + 1, wallClockId);
    const commit = await kv.atomic()
      .check(current)
      .set(key, next, { expireIn: MESSAGE_TTL_SECONDS * 1000 })
      .commit();
    if (commit.ok) {
      return next;
    }
  }

  throw new HttpError(503, "Relay could not allocate message id");
}

async function appendInboxIndex(pairId: string, target: Target, id: number): Promise<void> {
  const key = inboxIndexKey(pairId, target);
  for (let attempt = 0; attempt < 8; attempt++) {
    const current = await kv.get<number[]>(key);
    const ids = Array.isArray(current.value) ? current.value : [];
    const next = [...ids.filter((existing) => existing !== id), id]
      .sort((a, b) => a - b)
      .slice(-INBOX_INDEX_LIMIT);
    const commit = await kv.atomic()
      .check(current)
      .set(key, next, { expireIn: MESSAGE_TTL_SECONDS * 1000 })
      .commit();
    if (commit.ok) {
      return;
    }
  }
  debugLog("inbox index update failed", { pairId, target, id });
}

async function collectMessagesFromIndex(
  pairId: string,
  target: Target,
  after: number,
  limit: number,
  correlationId: string | null,
): Promise<StoredMessage[]> {
  const index = await kv.get<number[]>(inboxIndexKey(pairId, target));
  const ids = (Array.isArray(index.value) ? index.value : [])
    .filter((id) => Number.isFinite(id) && id > after)
    .sort((a, b) => a - b)
    .slice(0, limit);
  if (ids.length === 0) {
    return [];
  }

  const messages: StoredMessage[] = [];
  for (const id of ids) {
    const entry = await kv.get<StoredMessage>(messageKey(pairId, target, id));
    const message = entry.value;
    if (!message || message.id <= after) {
      continue;
    }
    if (correlationId && message.correlation_id !== correlationId) {
      continue;
    }
    messages.push(await hydrateShardedMessage(pairId, target, message));
    if (messages.length >= limit) break;
  }
  return messages;
}

async function collectMessagesForPair(
  pairId: string,
  target: Target,
  after: number,
  limit: number,
  correlationId: string | null,
): Promise<StoredMessage[]> {
  const indexedMessages = await collectMessagesFromIndex(
    pairId,
    target,
    after,
    limit,
    correlationId,
  );
  if (indexedMessages.length > 0) {
    debugLog("collected messages from index", {
      pairId,
      pairIdLength: pairId.length,
      target,
      after,
      limit,
      correlationId,
      count: indexedMessages.length,
      ids: indexedMessages.map((message) => message.id),
    });
    return indexedMessages;
  }

  const prefix = messagePrefix(pairId, target);
  const messages: StoredMessage[] = [];
  const entries = kv.list({ prefix });

  for await (const entry of entries) {
    const message = entry.value as StoredMessage;
    if (!message || typeof message.id !== "number") {
      continue;
    }
    if (message.id <= after) {
      continue;
    }
    if (correlationId && message.correlation_id !== correlationId) {
      continue;
    }
    const hydrated = await hydrateShardedMessage(pairId, target, message);
    messages.push(hydrated);
    if (messages.length >= limit) break;
  }

  messages.sort((a, b) => a.id - b.id);
  debugLog("collected messages", {
    pairId,
    pairIdLength: pairId.length,
    target,
    after,
    limit,
    correlationId,
    count: messages.length,
    ids: messages.map((message) => message.id),
  });
  return messages;
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

async function debugVerifyQueuedMessage(
  key: Deno.KvKey,
  pairId: string,
  target: Target,
  id: number,
): Promise<void> {
  if (!DEBUG_RELAY) {
    return;
  }
  const stored = await kv.get<StoredMessage>(key).catch((error) => ({ value: null, error }));
  debugLog("queued message readback", {
    pairId,
    pairIdLength: pairId.length,
    target,
    id,
    readable: Boolean(stored.value && stored.value.id === id),
    storedId: stored.value?.id,
    storedTarget: stored.value?.target,
    error: "error" in stored ? String(stored.error) : undefined,
  });
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
  const id = await nextMessageId(pairId);
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

  if (target === "phone" && kind === "clipboard") {
    await clearPhoneClipboardQueue(pairId);
  }

  const key = messageKey(pairId, target, id);
  const notifyKey = streamNotifyKey(pairId, target);
  const ttlMs = MESSAGE_TTL_SECONDS * 1000;

  const img = payloadWithoutToken.image;
  if (jsonUtf8ByteLength(message) <= KV_MAX_MESSAGE_BYTES) {
    try {
      const commit = await kv.atomic()
        .set(key, message, { expireIn: ttlMs })
        .set(notifyKey, id, { expireIn: ttlMs })
        .commit();
      if (!commit.ok) {
        throw new HttpError(503, "Relay could not store message");
      }
      await appendInboxIndex(pairId, target, id);
      await debugVerifyQueuedMessage(key, pairId, target, id);
      debugLog("queued message", {
        pairId,
        pairIdLength: pairId.length,
        target,
        id,
        kind,
        correlationId,
      });
      return { status: "queued", id, expires_in: MESSAGE_TTL_SECONDS };
    } catch (err) {
      // V8-serialized KV value can exceed the limit even when JSON.stringify length looks OK.
      if (!isKvValueTooLargeError(err) || typeof img !== "string" || img.length === 0) {
        throw err;
      }
    }
  }

  // Image base64 exceeds one KV value (~64 KiB). Shard across extra keys (same atomic, ≤10 mutations).
  if (typeof img !== "string" || img.length === 0) {
    throw new HttpError(
      413,
      "Message too large for relay (64 KiB per value). Shrink payload or send images only via relay.",
    );
  }

  const chunkCount = Math.ceil(img.length / IMAGE_CHUNK_CHARS);
  if (chunkCount > MAX_IMAGE_SHARDS) {
    throw new HttpError(
      413,
      `Image too large for relay (max ~${MAX_IMAGE_SHARDS * IMAGE_CHUNK_CHARS} base64 characters).`,
    );
  }

  const metaPayload: Record<string, unknown> = { ...payloadWithoutToken as object };
  delete metaPayload.image;
  metaPayload._relay_image_shards = chunkCount;

  const metaMsg: StoredMessage = {
    id,
    target,
    kind,
    correlation_id: correlationId,
    payload: metaPayload as Omit<RelayPayload, "token">,
    created_at: now,
  };

  if (jsonUtf8ByteLength(metaMsg) > KV_MAX_MESSAGE_BYTES) {
    throw new HttpError(413, "Message metadata too large for relay");
  }

  const op = kv.atomic().set(key, metaMsg, { expireIn: ttlMs });
  for (let i = 0; i < chunkCount; i++) {
    const start = i * IMAGE_CHUNK_CHARS;
    op.set(
      imageChunkKey(pairId, target, id, i),
      img.slice(start, start + IMAGE_CHUNK_CHARS),
      { expireIn: ttlMs },
    );
  }
  const commit = await op.set(notifyKey, id, { expireIn: ttlMs }).commit();
  if (!commit.ok) {
    throw new HttpError(503, "Relay could not store sharded message");
  }
  await appendInboxIndex(pairId, target, id);
  await debugVerifyQueuedMessage(key, pairId, target, id);
  debugLog("queued sharded message", {
    pairId,
    pairIdLength: pairId.length,
    target,
    id,
    kind,
    correlationId,
    chunkCount,
  });

  return { status: "queued", id, expires_in: MESSAGE_TTL_SECONDS };
}

async function deleteMessageWithShards(
  pairId: string,
  target: Target,
  message: StoredMessage,
): Promise<void> {
  await kv.delete(messageKey(pairId, target, message.id));
  const shards = shardCountFromPayload(message.payload as Record<string, unknown>);
  if (shards <= 0) return;
  for (let i = 0; i < shards; i++) {
    await kv.delete(imageChunkKey(pairId, target, message.id, i));
  }
}

async function clearPhoneClipboardQueue(pairId: string): Promise<void> {
  const prefix = messagePrefix(pairId, "phone");
  const entries = kv.list<StoredMessage>({ prefix });
  for await (const entry of entries) {
    const message = entry.value;
    if (!message || message.kind !== "clipboard") {
      continue;
    }
    await deleteMessageWithShards(pairId, "phone", message);
  }
}

async function getLatestPhoneClipboard(
  pairId: string,
  params: URLSearchParams,
): Promise<Record<string, unknown>> {
  const token = params.get("token") || "";
  await requirePair(pairId, token);

  const correlationId = params.get("correlation_id");

  const prefix = messagePrefix(pairId, "phone");
  const entries = kv.list<StoredMessage>({ prefix });

  let latestResponse: StoredMessage | null = null;
  let latestClipboard: StoredMessage | null = null;
  for await (const entry of entries) {
    const message = entry.value;
    if (!message) {
      continue;
    }

    if (correlationId && message.correlation_id !== correlationId) {
      continue;
    }

    if (message.kind === "response") {
      if (!latestResponse || message.id > latestResponse.id) {
        latestResponse = message;
      }
      continue;
    }

    if (message.kind === "clipboard") {
      if (!latestClipboard || message.id > latestClipboard.id) {
        latestClipboard = message;
      }
    }
  }

  const latest = latestResponse || latestClipboard;
  if (!latest) {
    throw new HttpError(404, "No clipboard queued");
  }

  const hydrated = await hydrateShardedMessage(pairId, "phone", latest);

  return {
    status: "success",
    message: hydrated,
  };
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
  const debugId = DEBUG_RELAY ? safeNumber(params.get("debug_id"), 0) : 0;

  const page = await collectMessagesForPair(pairId, target, after, limit, correlationId);
  let debugMessage: StoredMessage | null = null;
  if (debugId > 0) {
    const exact = await kv.get<StoredMessage>(messageKey(pairId, target, debugId));
    debugMessage = exact.value || null;
    debugLog("debug message lookup", {
      pairId,
      pairIdLength: pairId.length,
      target,
      debugId,
      found: Boolean(debugMessage),
      storedId: debugMessage?.id,
      storedTarget: debugMessage?.target,
      storedKind: debugMessage?.kind,
    });
  }

  return {
    status: "success",
    messages: page,
    cursor: page.length ? page[page.length - 1].id : after,
    ...(debugId > 0
      ? {
        debug: {
          id: debugId,
          found: Boolean(debugMessage),
          message: debugMessage,
        },
      }
      : {}),
  };
}

async function subscribeSSE(
  pairId: string,
  target: Target,
  params: URLSearchParams,
): Promise<Response> {
  const token = params.get("token") || "";
  await requirePair(pairId, token);

  const notifyKey = streamNotifyKey(pairId, target);
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

        const watchdog = setTimeout(() => {
          try {
            debugLog("SSE watchdog forced close", { pairId, target });
            controller.close();
          } catch {
            /* already closed */
          }
        }, timeoutMs + 2500);

        try {
          let lastEmitted = safeNumber(params.get("after"), 0);
          const correlationId = params.get("correlation_id");

          const emitMessage = (message: StoredMessage): boolean => {
            eventCount++;
            debugLog(`SSE event #${eventCount}`, { pairId, target, id: message.id });
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
              return false;
            }
            if (eventCount >= maxEvents || Date.now() - startTime > timeoutMs) {
              debugLog("SSE closing", { eventCount, pairId, target });
              try {
                controller.close();
              } catch {
                /* already closed */
              }
              return false;
            }
            return true;
          };

          const drainBatch = async (): Promise<void> => {
            const remaining = maxEvents - eventCount;
            if (remaining <= 0) return;
            const batch = await collectMessagesForPair(
              pairId,
              target,
              lastEmitted,
              Math.min(remaining, MAX_LIMIT),
              correlationId,
            );
            if (batch.length === 0) return;
            for (const message of batch) {
              if (!emitMessage(message)) return;
              lastEmitted = Math.max(lastEmitted, message.id);
            }
          };

          // Backlog already in KV (e.g. client reconnects with ?after=)
          await drainBatch();
          if (eventCount >= maxEvents || Date.now() - startTime > timeoutMs) {
            try {
              controller.close();
            } catch {
              /* already closed */
            }
            return;
          }

          // kv.watch expects an array of keys; it does not watch prefix subtrees.
          // Do not use bare `for await` on watch: it blocks until the next KV change, so the
          // client `timeout` is never honored during idle (curl then hits its own --max-time).
          const watchStream = kv.watch([notifyKey]);
          const iter = watchStream[Symbol.asyncIterator]();

          try {
            let pendingKv:
              | Promise<{ tag: "kv"; r: Awaited<ReturnType<typeof iter.next>> }>
              | undefined;
            while (eventCount < maxEvents) {
              const elapsed = Date.now() - startTime;
              if (elapsed >= timeoutMs) {
                debugLog("SSE closing (timeout)", { eventCount, pairId, target });
                break;
              }
              const budget = timeoutMs - elapsed;
              if (budget <= 0) break;

              pendingKv ??= iter.next().then((r) => ({ tag: "kv" as const, r }));
              let tid: ReturnType<typeof setTimeout> | undefined;
              const onBudget = new Promise<{ tag: "to" }>((resolve) => {
                tid = setTimeout(() => resolve({ tag: "to" }), budget);
              });
              let heartbeatId: ReturnType<typeof setTimeout> | undefined;
              const onHeartbeat = new Promise<{ tag: "heartbeat" }>((resolve) => {
                heartbeatId = setTimeout(
                  () => resolve({ tag: "heartbeat" }),
                  Math.min(SSE_HEARTBEAT_MS, budget),
                );
              });
              const winner = await Promise.race([pendingKv, onBudget, onHeartbeat]);
              if (tid !== undefined) clearTimeout(tid);
              if (heartbeatId !== undefined) clearTimeout(heartbeatId);
              if (winner.tag === "to") {
                debugLog("SSE closing (idle timeout)", { eventCount, pairId, target });
                break;
              }
              if (winner.tag === "heartbeat") {
                try {
                  controller.enqueue(encoder.encode(": heartbeat\n\n"));
                } catch (enqueueErr) {
                  debugLog("SSE heartbeat failed (client likely disconnected)", enqueueErr);
                  break;
                }
                continue;
              }
              pendingKv = undefined;
              if (winner.r.done) break;

              await drainBatch();
              if (eventCount >= maxEvents) {
                debugLog("SSE closing (max_events)", { eventCount, pairId, target });
                break;
              }
            }
          } finally {
            // Never await iter.return() — on Deploy it can hang and block controller.close(),
            // which leaves curl waiting until --max-time.
            const ret = typeof iter.return === "function" ? iter.return() : undefined;
            if (ret && typeof (ret as Promise<unknown>).then === "function") {
              void Promise.race([
                ret as Promise<unknown>,
                new Promise<void>((r) => setTimeout(r, 400)),
              ]).catch(() => {});
            }
          }

          try {
            controller.close();
          } catch {
            /* already closed */
          }
        } finally {
          clearTimeout(watchdog);
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
      host: request.headers.get("host"),
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

      if (action === "latest_clipboard" && request.method === "GET") {
        return json(await getLatestPhoneClipboard(pairId, url.searchParams));
      }

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
