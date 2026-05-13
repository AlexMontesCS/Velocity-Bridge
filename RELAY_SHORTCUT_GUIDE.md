# iOS Relay Shortcut Setup Guide

This guide explains how to create an iOS Shortcut that sends clipboard content to a Velocity Bridge relay server instead of directly to your desktop.

## Shortcut Overview

**Name:** Velocity Bridge - Relay Send Clipboard

**Purpose:** Copy on iPhone → Send to Relay → Desktop pulls from relay

**Trigger:** Manual run or Back Tap automation

---

## Configuration Variables

Before building the shortcut, you need these values:

| Variable | Example | Source |
|----------|---------|--------|
| **Relay URL** | `https://relay.example.com` | Deploy relay server |
| **Pair ID** | `abc123xyz789` | Relay server assignment |
| **Relay Token** | `sk_relay_abc123...` | Relay server credentials |

---

## Step-by-Step Building Instructions

### **Step 1: Create New Shortcut**
1. Open the **Shortcuts** app on iPhone
2. Tap **+** (Create Shortcut)
3. Name it: **Velocity Bridge - Relay**

---

### **Step 2: Add Input/Variables Section**

Add these as **Ask for** inputs to make the shortcut configurable:

```
Ask for Relay URL
  Type: Text
  Default: [leave empty or enter your relay URL]
  Request: "Enter relay URL (e.g., https://relay.example.com)"

Ask for Pair ID
  Type: Text
  Default: [leave empty or enter your pair ID]
  Request: "Enter pair ID"

Ask for Relay Token
  Type: Text (Hidden for security)
  Default: [leave empty or enter your token]
  Request: "Enter relay token"
```

**Alternatively** (better for automation):
- Store these as **Text** variables directly in the shortcut
- Edit them in the shortcut definition
- This avoids prompts when run automatically

---

### **Step 3: Get Clipboard Content**

Add action:
```
Get Clipboard
```
This retrieves the current clipboard (text or image).

---

### **Step 4: Prepare Request Payload**

Add action:
```
Set Dictionary
  Key: "token"     Value: [Relay Token variable]
  Key: "kind"      Value: "clipboard"
  Key: "type"      Value: "text"  (or "image" if image content)
  Key: "content"   Value: [Clipboard content]
```

**For image clipboard:**
- Detect if clipboard contains image
- Set type to "image"
- Encode image as base64
- Add key: "image" → Base64 encoded image

---

### **Step 5: Build URL**

Add action:
```
Text
  [Relay URL]/v1/pairs/[Pair ID]/messages/phone
```

Result should look like:
```
https://relay.example.com/v1/pairs/abc123xyz789/messages/phone
```

---

### **Step 6: Make HTTPS Request**

Add action:
```
POST Request
  URL: [URL from Step 5]
  Headers:
    - Key: "Content-Type"      Value: "application/json"
    - Key: "Accept"            Value: "application/json"
    - Key: "User-Agent"        Value: "VelocityBridge-iOS/3.0"
  Body: [Dictionary from Step 4] (as JSON)
  Ask: Off
  Show: Off
  Timeout: 15 seconds
```

---

### **Step 7: Handle Response**

Add action:
```
If [Request Status Code] = 200
  Show Result "✅ Sent to relay"
Otherwise
  Show Result "❌ Failed: [Error Message]"
```

---

### **Step 8: Error Handling**

Add action:
```
On Error
  Show Alert "Relay Error"
  Message: [Error Details]
```

---

## Complete Shortcut Flow (Visual)

```
┌─────────────────────────────────────────┐
│  Ask for configuration (or use defaults)│
├─────────────────────────────────────────┤
│  Get Clipboard (text/image)             │
├─────────────────────────────────────────┤
│  Detect clipboard type                  │
├─────────────────────────────────────────┤
│  Build JSON payload with:               │
│    - token                              │
│    - kind: "clipboard"                  │
│    - type: "text" or "image"            │
│    - content/image: [data]              │
├─────────────────────────────────────────┤
│  Build URL:                             │
│  {relayURL}/v1/pairs/{pairID}/          │
│  messages/phone                         │
├─────────────────────────────────────────┤
│  POST with Headers:                     │
│    Content-Type: application/json       │
│    Accept: application/json             │
│    User-Agent: VelocityBridge-iOS       │
├─────────────────────────────────────────┤
│  If Status = 200: Success ✅            │
│  Else: Error ❌                         │
└─────────────────────────────────────────┘
```

---

## JSON Payload Examples

### Text Clipboard
```json
{
  "token": "sk_relay_abc123xyz789",
  "kind": "clipboard",
  "type": "text",
  "content": "Hello from iPhone!"
}
```

### Image Clipboard
```json
{
  "token": "sk_relay_abc123xyz789",
  "kind": "clipboard",
  "type": "image",
  "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "filename": "clipboard_image.png"
}
```

---

## Storing Configuration as Text

For **Back Tap automation** (no prompts), hardcode values:

```
Text: "https://relay.example.com"
  → Store in variable "RelayURL"

Text: "abc123xyz789"
  → Store in variable "PairID"

Text: "sk_relay_abc123xyz789"
  → Store in variable "RelayToken"
```

Then reference these variables throughout the shortcut.

---

## Setting Up Back Tap Automation

Once shortcut is created:

1. Go to **Settings → Accessibility → Touch → Back Tap**
2. Tap **Double Tap** or **Triple Tap**
3. Choose **Shortcuts** → **Velocity Bridge - Relay**
4. Double-tap (or triple-tap) the back of iPhone to send clipboard

---

## Testing the Shortcut

1. Copy some text to clipboard
2. Run the shortcut (manual or Back Tap)
3. Watch for success/error notification
4. On desktop, check relay status in Velocity Bridge app

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection Failed" | Check Relay URL is correct and accessible |
| "401 Unauthorized" | Verify relay token is correct |
| "Invalid URL" | Ensure no spaces in Pair ID or URL |
| Clipboard empty | Copy something before running shortcut |
| Image not sending | Ensure image is in clipboard (copy from Photos) |

---

## Advanced: Bidirectional Shortcut

To also **pull** from relay (desktop → iPhone):

```
1. Ask user: "Pull or Push?"
2. If Push: [Use steps above]
3. If Pull:
   - GET [RelayURL]/v1/pairs/[PairID]/messages/iphone
   - Parse response for clipboard data
   - Set Clipboard to received content
   - Show notification
```

---

## Publishing to iCloud

Once tested and working:

1. Open shortcut → **Share** → **Collaborate**
2. Generate shareable iCloud link
3. Share the link in project README
4. Users tap link → **Get Shortcut** → **Add Shortcut**

---

## Notes

- Relay token should be **treated as a secret** - don't share publicly
- Users must configure their own relay URL and credentials
- Shortcut will fail silently if stored credentials are wrong
- Test with a simple text clipboard first, then images
