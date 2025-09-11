from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
import aiohttp
import aiofiles
import os
import hashlib
import yt_dlp

app = FastAPI()

# Cache folder
CACHE_DIR = "/tmp/download_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ✅ Hybrid cookies handling: absolute path if exists, else fallback to relative
ABS_COOKIES_PATH = os.path.join(os.path.dirname(__file__), "cookies.txt")
COOKIES_PATH = ABS_COOKIES_PATH if os.path.exists(ABS_COOKIES_PATH) else "cookies.txt"


def get_cache_path(url: str) -> str:
    """Generate a unique cache path based on the URL hash."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.mp3")


@app.get("/")
async def root():
    return {"status": "✅ Download service running"}


@app.get("/download")
async def download_file(url: str = Query(...)):
    cache_path = get_cache_path(url)

    # ✅ Return cached file if already exists
    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="audio/mpeg")

    # ✅ If YouTube link → use yt-dlp with cookies + anti-429 options
    if "youtube.com" in url or "youtu.be" in url:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": cache_path,
            "quiet": True,
            "nocheckcertificate": True,
            "cookiefile": COOKIES_PATH,  # ✅ hybrid path
            "retries": 20,               # ✅ keep retrying
            "sleep_interval": [1, 3],    # ✅ random pause between requests
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "android", "ios"]  # ✅ rotate device fingerprints
                }
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
                "Accept-Language": "en-US,en;q=0.5",
            },
            # "proxy": "http://user:pass@proxyserver:port",  # ✅ optional proxy support
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return FileResponse(cache_path, media_type="audio/mpeg")
        except Exception as e:
            # 🔹 Prevent Telegram crash (truncate error messages)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "... (truncated)"
            raise HTTPException(status_code=500, detail=f"yt-dlp error: {error_msg}")

    # ✅ Otherwise, treat it as a direct file URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to download media (HTTP {response.status})"
                    )

                async with aiofiles.open(cache_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):
                        await f.write(chunk)

        return FileResponse(cache_path, media_type="audio/mpeg")

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (truncated)"
        raise HTTPException(status_code=500, detail=f"Error: {error_msg}")
