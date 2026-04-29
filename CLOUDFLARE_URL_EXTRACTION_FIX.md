# Cloudflare Bridge Tunneling - URL Extraction Fix

## Problem
The tunnel was stuck at "Starting Cloudflare Quick Tunnel" because the URL extraction wasn't reading the output correctly.

## Root Cause
- **cloudflared** outputs the tunnel URL to **stderr**, not stdout
- The original code was only reading stdout, so it never found the URL
- This caused the extraction to timeout after 3 seconds

## Solution Applied
✅ **Fixed in all three places:**

### 1. Notebooks (LLM_Bridge.ipynb & XTTS_Bridge.ipynb)
- Changed to read from `proc.stderr.readline()` instead of `proc.stdout.readline()`
- Added loop that tries for 15 seconds (increased from 3)
- Added debug print statements to see what cloudflared is outputting
- Better error handling

### 2. standalone_llm_bridge.py
- Rewrote `_extract_cloudflare_url()` method
- Now reads from both stderr and stdout
- Accumulates output lines and searches for URL pattern
- Increased timeout to 15 seconds

## What To Do Now

### For Colab/Kaggle Users
1. **Refresh** the notebook page (Ctrl+R)
2. **Clear all outputs** (Runtime > Clear all outputs)
3. **Run All** again (Ctrl+F9)
4. Wait 10-15 seconds - the URL should now appear

### For Local Testing
```bash
python colab_bridge/standalone_llm_bridge.py --tunnel cloudflare --port 8000
# You should now see the URL appear after 3-5 seconds
```

## Expected Output
```
Starting Cloudflare Quick Tunnel...
[cloudflared] ... tunnel running ...
[cloudflared] ... registered tunnel connection ...
[cloudflared] https://xxxxx.trycloudflare.com available

🚀 Cloudflare tunnel online: https://xxxxx.trycloudflare.com
```

## Verification
✅ URL format: `https://[6-8 random chars].trycloudflare.com`  
✅ URL appears within 15 seconds  
✅ No error messages about "Failed to extract"  

If still stuck, check:
- Internet connection is stable
- cloudflared binary downloaded successfully
- No firewall blocking cloudflared

Let me know if you still have issues!
