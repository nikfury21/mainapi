from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
import aiohttp
import aiofiles
import os
import hashlib

app = FastAPI()

CACHE_DIR = "/tmp/download_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_path(url: str) -> str:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.mp3")

@app.get("/download")
async def download_file(url: str = Query(...)):
    cache_path = get_cache_path(url)

    # Return cached file if exists
    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="audio/mpeg")

    # Download the file
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Failed to download media")

                async with aiofiles.open(cache_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(131072):
                        await f.write(chunk)

        return FileResponse(cache_path, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
