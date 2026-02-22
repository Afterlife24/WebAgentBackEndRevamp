# Navigation Fix for EC2 Deployment

## Problem
The `webbrowser.open()` function in `tools.py` was trying to open URLs on the **server machine** (EC2 Ubuntu), not the **user's browser**. This worked locally because the server and browser were on the same machine, but failed on EC2 because:

1. EC2 Ubuntu server has no GUI/desktop environment
2. No browser installed or running on the server
3. Even if a browser existed, it would open on the server, not the user's machine

## Root Cause
```python
# OLD CODE - Opens browser on SERVER (EC2)
webbrowser.open(url)  # ❌ This runs on EC2, not user's machine
```

## Solution
Use **LiveKit Data Channel** to send navigation commands from the backend (EC2) to the frontend (user's browser).

### Backend Changes (`tools.py`)

**Before:**
```python
webbrowser.open(url)  # Opens on server
```

**After:**
```python
# Send navigation command to frontend via LiveKit data channel
await room.local_participant.publish_data(
    json.dumps({
        "type": "navigate",
        "action": "open_url",
        "url": url
    }).encode('utf-8'),
    reliable=True
)
```

### Frontend Changes (`LiveKitWidget.tsx`)

Added `NavigationHandler` component that:
1. Listens for data messages from LiveKit room
2. Parses navigation commands
3. Opens URLs in user's browser using `window.open()` or `window.location.href`

```typescript
const handleDataReceived = (payload: Uint8Array) => {
  const message = JSON.parse(decoder.decode(payload));
  
  if (message.type === "navigate") {
    if (message.action === "open_url") {
      window.open(message.url, "_blank");  // ✅ Opens in USER's browser
    } else if (message.action === "navigate_to_section") {
      window.location.href = message.url;  // ✅ Navigates in USER's browser
    }
  }
};
```

## Architecture Flow

```
User: "Open pricing page"
    ↓
Frontend (Browser) → LiveKit Room → Backend Agent (EC2)
    ↓
Agent calls navigate_to_section("pricing")
    ↓
Backend sends data message via LiveKit:
{
  "type": "navigate",
  "action": "navigate_to_section",
  "section": "pricing",
  "url": "https://www.novaflux.afterlife.org.in/pricing"
}
    ↓
Frontend receives data message
    ↓
NavigationHandler executes: window.location.href = url
    ↓
User's browser navigates to pricing page ✅
```

## Detailed Logging Added

### Backend (`tools.py`)
- `[TOOL] navigate_to_section called with section: {section}`
- `[TOOL] Mapped section '{section}' to URL: {url}`
- `[TOOL] Room found, sending navigation data to frontend`
- `[TOOL] Successfully sent navigation command for section: {section}`
- `[TOOL] Error in navigate_to_section: {error}` (with full traceback)

### Frontend (`LiveKitWidget.tsx`)
- `[NavigationHandler] Setting up data message listener`
- `[NavigationHandler] Received data message: {message}`
- `[NavigationHandler] Navigation command received: {data}`
- `[NavigationHandler] Opening URL: {url}`
- `[NavigationHandler] Navigating to section: {section}, URL: {url}`
- `[NavigationHandler] Error processing data message: {error}`

## Testing

### Local Testing
1. Start backend: `python agent.py`
2. Start frontend: `npm run dev`
3. Open web agent widget
4. Say: "Open pricing page"
5. Check console logs for navigation flow

### EC2 Testing
1. Deploy updated code to EC2
2. Restart agent: `sudo systemctl restart web-agent` (or your service name)
3. Test from frontend
4. Check logs: `journalctl -u web-agent -f` or `tail -f /path/to/logs`

## Benefits

1. **Works on headless servers** - No GUI/browser needed on EC2
2. **Secure** - Navigation happens in user's browser, not server
3. **Real-time** - Uses LiveKit's reliable data channel
4. **Detailed logging** - Easy to debug navigation issues
5. **Fallback handling** - Graceful error messages if navigation fails

## Message Format

### Open External URL
```json
{
  "type": "navigate",
  "action": "open_url",
  "url": "https://example.com"
}
```

### Navigate to Internal Section
```json
{
  "type": "navigate",
  "action": "navigate_to_section",
  "section": "pricing",
  "url": "https://www.novaflux.afterlife.org.in/pricing",
  "description": "Pricing page"
}
```

## Files Modified

1. `WebAgentBackEndRevamp/tools.py` - Updated both `open_url()` and `navigate_to_section()`
2. `afterlife_website_3agents/app/components/LiveKitWidget.tsx` - Added `NavigationHandler` component

## Dependencies

No new dependencies required. Uses existing:
- Backend: `livekit.agents` (already installed)
- Frontend: `@livekit/components-react`, `livekit-client` (already installed)
