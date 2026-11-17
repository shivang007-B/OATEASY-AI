"""
Render Keep-Alive Pinger for OatEasy AI
---------------------------------------
Pings the Render health endpoint every 10-12 minutes to prevent
the free-tier web service from spinning down due to Render's
15-minute inactivity policy.
"""

import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

DEFAULT_URL = os.environ.get("RENDER_APP_URL", "https://oateasy-ai.onrender.com/health")
DEFAULT_INTERVAL_MINUTES = 12  # Render spins down at 15m; 12m guarantees it stays active.

def ping(url: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OatEasy-KeepAlive/1.0"}
    )
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            duration = round((time.time() - start_time) * 1000, 2)
            code = response.getcode()
            print(f"[{timestamp}] [SUCCESS] Pinged {url} -> Status {code} ({duration}ms)", flush=True)
            return True
    except urllib.error.HTTPError as e:
        duration = round((time.time() - start_time) * 1000, 2)
        print(f"[{timestamp}] [HTTP_ERROR] {url} -> Status {e.code} ({duration}ms)", flush=True)
        return False
    except urllib.error.URLError as e:
        print(f"[{timestamp}] [NET_ERROR] {url} -> {e.reason}", flush=True)
        return False
    except Exception as e:
        print(f"[{timestamp}] [ERROR] Unexpected error: {e}", flush=True)
        return False

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    interval_minutes = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_INTERVAL_MINUTES
    interval_seconds = interval_minutes * 60

    print("=" * 60, flush=True)
    print(" OatEasy Render Keep-Alive Daemon", flush=True)
    print(f" Target URL : {url}", flush=True)
    print(f" Frequency  : Every {interval_minutes} minutes ({interval_seconds}s)", flush=True)
    print("=" * 60, flush=True)

    # Initial ping immediately
    ping(url)

    while True:
        try:
            time.sleep(interval_seconds)
            ping(url)
        except KeyboardInterrupt:
            print("\nKeep-alive monitor stopped by user.")
            break

if __name__ == "__main__":
    main()
