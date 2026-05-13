# Velocity Bridge Relay

This relay lets Velocity Bridge work when the phone and laptop are not on the
same network. Both devices make outbound HTTPS requests to the relay, so the
laptop does not need an open inbound port or LAN discovery.

## How It Works

1. Phone -> laptop: an iOS Shortcut posts the phone clipboard to the relay.
2. The laptop polls the relay over HTTPS and applies new clipboard messages.
3. Laptop -> phone: an iOS Shortcut asks the relay for the laptop clipboard.
4. The laptop sees that command, posts a response to the relay, and the Shortcut
   reads the response.

The relay stores messages in SQLite and expires them after 24 hours by default.
Pair tokens are stored as SHA-256 hashes, but clipboard payloads are plaintext at
the relay. Run it only on infrastructure you trust, behind HTTPS.

## Run Locally

```bash
cd relay
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8787
```

For real phone use, put it behind TLS:

```text
https://your-relay.example.com
```

## API

Phone to laptop:

```http
POST /v1/pairs/{pair_id}/phone/send
{
  "token": "relay-token",
  "type": "text",
  "content": "hello"
}
```

Laptop to phone request:

```http
POST /v1/pairs/{pair_id}/phone/request_clipboard
{
  "token": "relay-token"
}
```

Phone then polls:

```http
GET /v1/pairs/{pair_id}/messages/phone?token=relay-token&correlation_id={request_id}
```

