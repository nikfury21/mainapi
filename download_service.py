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


def get_cache_path(url: str) -> str:
    """
    Generate a unique cache path based on the URL hash.
    """
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

    # ✅ If YouTube link → use yt-dlp with cookies only (no anti-429 tweaks)
    if "youtube.com" in url or "youtu.be" in url:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": cache_path,
            "quiet": True,
            "nocheckcertificate": True,
            "cookiefile": "cookies.txt",   # <── direct cookies.txt
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return FileResponse(cache_path, media_type="audio/mpeg")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"yt-dlp error: {e}")

    # ✅ Otherwise, treat it as a direct file URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400, detail="Failed to download media"
                    )

                async with aiofiles.open(cache_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):
                        await f.write(chunk)

        return FileResponse(cache_path, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
