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

# ✅ Cookies path (place cookies.txt in same folder as this script)
ABS_COOKIES_PATH = os.path.join(os.path.dirname(__file__), "cookies.txt")
COOKIES_PATH = ABS_COOKIES_PATH if os.path.exists(ABS_COOKIES_PATH) else None


def get_cache_path(url: str) -> str:
    """Generate a unique cache path based on the URL hash."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.m4a")


@app.get("/")
async def root():
    return {"status": "✅ Download service running"}


@app.get("/download")
async def download_file(url: str = Query(...)):
    cache_path = get_cache_path(url)
    temp_path = cache_path + ".part"  # temp file during download

    # ✅ Return cached file if already exists
    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="audio/mpeg")

    # ✅ YouTube link → yt-dlp
    if "youtube.com" in url or "youtu.be" in url:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": temp_path,  # temp file first
            "quiet": True,
            "nocheckcertificate": True,
            "cookiefile": COOKIES_PATH if COOKIES_PATH else None,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
                "Accept-Language": "en-US,en;q=0.5",
            },
            "extractor_args": {"youtube": {"player_client": ["web"]}},
            "retries": 5,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            # ✅ Rename temp file → final cache file
            if os.path.exists(temp_path):
                os.rename(temp_path, cache_path)
            else:
                raise HTTPException(status_code=500, detail="Download failed: no file created")

            return FileResponse(cache_path, media_type="audio/mpeg")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Clean up temp if failed
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(status_code=500, detail=f"yt-dlp error: {e}\n{tb}")

    # ✅ Direct file URLs (non-YouTube)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Failed to download media")

                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):
                        await f.write(chunk)

        # ✅ Rename after full success
        os.rename(temp_path, cache_path)
        return FileResponse(cache_path, media_type="audio/mpeg")

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error: {e}\n{tb}")
