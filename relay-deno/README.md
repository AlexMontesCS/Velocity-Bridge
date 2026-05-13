# Velocity Bridge Relay - Deno Deploy

Free serverless relay for Velocity Bridge (phone ↔ desktop clipboard sync).

## Why Deno Deploy?

- **Free tier:** 1 million requests/day (vs. Cloudflare Workers' 100k list ops/day)
- **Better value:** No quota overages, just rate limiting
- **Auto-deploy:** Push to GitHub → deploys automatically
- **Same API:** Drop-in replacement for Cloudflare Workers relay

## Quick Start

### 1. Create Deno Deploy Project

1. Go to https://dash.deno.com
2. Click **"New Project"**
3. Select **"Deploy from GitHub"** (or use CLI below)
4. Connect your Velocity-Bridge repo
5. Set **Entry point** to `relay-deno/main.ts`
6. Click **Deploy**

### 2. Get Your Relay URL

After deployment, you'll see a URL like:
```
https://velocity-bridge-abc123.deno.dev
```

### 3. Update Your Desktop Client

In Velocity Bridge GUI → Settings → Relay:

```
Relay URL: https://velocity-bridge-abc123.deno.dev
```

(Keep your existing Pair ID and Token)

## Deploy via CLI

```bash
# Install Deno (if not already)
curl -fsSL https://deno.land/x/install/install.sh | sh

# Deploy
cd relay-deno
deno task deploy --project=velocity-bridge
```

(Requires `DENO_DEPLOY_TOKEN` env var from https://dash.deno.com/account)

## Auto-Deploy on GitHub Push

1. In Deno Deploy dashboard, link your GitHub repo
2. Deno auto-deploys on push to `main` (or set branch in settings)

## Testing

### Local Dev

```bash
deno run --allow-net --allow-env main.ts
# Server runs on http://localhost:8000
```

### Test Health Check

```bash
curl https://your-relay.deno.dev/
# {"status": "ok", "service": "Velocity Bridge Relay (Deno Deploy)"}
```

### Test Message POST (same as before)

```bash
curl -X POST "https://your-relay.deno.dev/v1/pairs/YOUR_PAIR_ID/messages/desktop" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_TOKEN",
    "kind": "clipboard",
    "type": "text",
    "content": "Hello from relay"
  }'
```

## API Endpoints

Identical to Cloudflare Workers relay:

- `POST /v1/pairs/{pairId}/messages/{target}` — Queue message
- `GET /v1/pairs/{pairId}/messages/{target}` — Fetch messages
- `POST /v1/pairs/{pairId}/phone/send` — iOS sends clipboard
- `POST /v1/pairs/{pairId}/phone/request_clipboard` — iOS requests clipboard

## Performance

- **Cold start:** ~10ms (Deno Deploy is fast)
- **Read latency:** <100ms global
- **Write latency:** <50ms
- **Simultaneous users:** Unlimited (Deno Deploy auto-scales)

## Limits

- Message size: 512KB per message
- Pair ID: max 80 chars
- Token: min 8 chars
- Message TTL: 24 hours

## Migrate from Cloudflare Workers

1. Deploy this relay to Deno Deploy
2. Update `relay_url` in your desktop app settings
3. Done! Messages queued on Workers will time out (24h TTL), no data loss risk
4. Optional: Delete your Cloudflare Workers project

## Costs

**Free tier (sufficient for 1 read/sec):**
- 1,000,000 requests/day
- Unlimited storage (KV)
- Bandwidth: unlimited

**Paid tier (if needed):** $65/month for much higher limits

## Troubleshooting

**"Cannot find Deno"**
```bash
curl -fsSL https://deno.land/x/install/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
```

**Deploy fails with permissions error**
```bash
deno task deploy --project=velocity-bridge --auth=<TOKEN>
# Get TOKEN from https://dash.deno.com/account
```

**Relay returns 403 (invalid token)**
- Ensure you're using the correct `relay_token` from Velocity Bridge settings
- Token must match the first request to establish the pair

**Messages not appearing**
- Check desktop is polling at the correct URL
- Verify `relay_enabled` is true in app settings
- Look at browser console: Settings → Relay Status

## Support

Issues? Check:
1. [Deno docs](https://docs.deno.com/deploy/)
2. [Velocity Bridge issues](https://github.com/AlexMontesCS/Velocity-Bridge/issues)
