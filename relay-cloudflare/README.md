# Velocity Bridge Cloudflare Relay

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/AlexMontesCS/Velocity-Bridge/tree/main/relay-cloudflare)

This is the easiest relay target for Velocity Bridge. It runs as a Cloudflare
Worker and stores short-lived clipboard messages in Workers KV.

## Why Cloudflare Instead of Plain Vercel?

Vercel's deploy button is great, but a relay needs durable storage between
requests. Cloudflare's deploy button can provision KV automatically, so the
relay has somewhere persistent to hold messages without asking users to wire up
a separate database.

## Deploy

1. Click **Deploy to Cloudflare**.
2. Let Cloudflare clone the Worker into your account.
3. Accept the generated KV namespace binding.
4. Copy the deployed Worker URL, such as:

```text
https://velocity-bridge-relay.<your-subdomain>.workers.dev
```

Paste that URL into Velocity Bridge's **Settings -> Relay** screen.

## Limits

Workers KV's free tier is good for personal clipboard syncing, but it is not a
high-throughput message bus. Messages expire after 24 hours by default.

Clipboard payloads are plaintext inside your Cloudflare KV namespace until they
expire. Use a relay account you control.

