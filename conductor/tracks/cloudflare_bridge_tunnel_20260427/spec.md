# Specification: Cloudflare Bridge Tunneling

## Problem
Ngrok's free tier includes a "You are visiting a site..." warning page. When the Python `requests` library hits the remote bridge, it receives this HTML page instead of JSON, leading to `JSONDecodeError` or connection drops during streaming.

## Solution
Use `cloudflared` to create a Quick Tunnel. Quick Tunnels do not have the interstitial warning page and are generally more stable for long-lived WebSocket/Streaming connections.

### Components
- **Remote (Notebooks):** Download `cloudflared` binary, run it in the background, and extract the `.trycloudflare.com` URL.
- **Local:** No changes needed to `settings.json` format, only the URL value will change.

### Requirements
- Linux amd64 binary for `cloudflared` (Colab/Kaggle).
- No account or token required for Quick Tunnels.
