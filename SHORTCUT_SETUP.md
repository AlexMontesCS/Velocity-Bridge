# iOS Shortcuts Setup

After running `./setup.sh`, you got a server URL and token. You'll need both.

## Quick Setup (Recommended)

Scan the QR codes in the README or use these links:

- **Text Clipboard**: [Add Shortcut](https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152)
- **Image Clipboard**: [Add Shortcut](https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865)

After adding, edit each shortcut and replace `YOUR_IP` and `yourtoken` with your values.

## Pro Tip: Back Tap

Trigger shortcuts instantly by tapping the back of your iPhone:

1. Go to **Settings → Accessibility → Touch → Back Tap**
2. Set **Double Tap** → your Text Clipboard shortcut
3. Set **Triple Tap** → your Image Clipboard shortcut

Now just copy anything on your iPhone and double-tap the back. It syncs to Linux instantly.

---

## Manual Setup

## Text Clipboard

This sends copied text from your iPhone to your Linux clipboard.

1. Open Shortcuts app
2. Create new shortcut
3. Add **Get Clipboard**
4. Add **Get Contents of URL** with:
   - URL: `http://YOUR_IP:8080/clipboard`
   - Method: `POST`
   - Headers: add `Content-Type` = `application/json`
   - Request Body: `JSON`
   - Add these fields (all Text type):
     - `type` → `text`
     - `content` → tap and pick the blue Clipboard variable
     - `token` → your token from setup

To trigger it easily, go to Settings → Accessibility → Touch → Back Tap and assign this shortcut.

## Image Clipboard

This sends copied images to your Linux clipboard.

1. Create new shortcut
2. Add **Get Clipboard**
3. Add **Base64 Encode** — select Clipboard as input
4. Add **Get Contents of URL** with:
   - URL: `http://YOUR_IP:8080/upload_image`
   - Method: `POST`
   - Headers: `Content-Type` = `application/json`
   - Request Body: `JSON`
   - Fields:
     - `image` → pick the blue Base64 Encoded variable
     - `filename` → `clipboard_image.png`
     - `token` → your token

Assign to the other back tap (double or triple).

## File Upload (optional)

For sharing files directly:

1. Create shortcut, name it "Send to Fedora"
2. In shortcut settings, enable "Show in Share Sheet"
3. Add **Get Contents of URL**:
   - URL: `http://YOUR_IP:8080/upload`
   - Method: `POST`
   - Request Body: `Form`
   - Fields:
     - `file` → Shortcut Input
     - `token` → your token

Now you can share → Send to Fedora from any app.

## Troubleshooting

**"Could not connect"** — Check you're on the same WiFi, verify the IP is correct

**"Invalid token"** — Copy-paste the token exactly, no extra spaces

**Image not working** — Make sure you actually copied an image (long press → Copy), not just selected it

**First time sending images** — iOS will ask for permission, tap "Always Allow"

---

That's it. Copy on iPhone, tap the back, paste on Linux.
