import os
import hashlib
import requests
import shutil
import subprocess
from PIL import Image

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".cache", "optimized_images"))
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")

def ensure_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_image(url: str) -> str:
    """Download a remote image and cache the download. Returns cached local path."""
    ensure_dirs()
    # Unique name based on url hash
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    # Try to guess extension from URL
    ext = ".jpg"
    for e in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]:
        if e in url.lower():
            ext = e
            break
            
    local_path = os.path.join(DOWNLOAD_DIR, f"{url_hash}{ext}")
    
    if os.path.exists(local_path):
        return local_path
        
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return local_path
    except Exception:
        pass
    return ""

def get_or_create_optimized_image(image_path_or_url: str, max_dim: int = 800) -> str:
    """
    Downloads, checks size, and optimizes an image.
    Returns the path to the cached optimized image, or the original path if optimization is unnecessary/fails.
    """
    if not image_path_or_url:
        return ""
        
    ensure_dirs()
    
    # 1. Resolve path/URL
    if image_path_or_url.startswith(("http://", "https://")):
        local_path = download_image(image_path_or_url)
        if not local_path:
            # Downloading failed, return original URL as fallback
            return image_path_or_url
    else:
        local_path = os.path.abspath(image_path_or_url)
        if not os.path.exists(local_path):
            return image_path_or_url
            
    # 2. Get file stats to check if we already have it optimized
    try:
        mtime = os.path.getmtime(local_path)
        size = os.path.getsize(local_path)
    except Exception:
        mtime = 0
        size = 0
        
    # Generate cache key
    path_hash = hashlib.sha256(f"{local_path}_{mtime}_{size}_{max_dim}".encode('utf-8')).hexdigest()
    _, ext = os.path.splitext(local_path)
    if not ext:
        ext = ".jpg"
    cache_path = os.path.join(CACHE_DIR, f"{path_hash}{ext.lower()}")
    
    # 3. If cached optimized image exists, return it immediately
    if os.path.exists(cache_path):
        return cache_path
        
    # 4. Check if size needs optimization
    try:
        with Image.open(local_path) as img:
            w, h = img.size
            if w <= max_dim and h <= max_dim:
                # No resize needed, just return original/downloaded path
                return local_path
    except Exception:
        return local_path
        
    # 5. Optimize the image
    try:
        is_gif = ext.lower() == ".gif"
        has_ffmpeg = shutil.which("ffmpeg") is not None
        
        if is_gif and has_ffmpeg:
            cmd = [
                "ffmpeg", "-y", "-i", local_path,
                "-vf", f"scale=w={max_dim}:h={max_dim}:force_original_aspect_ratio=decrease",
                cache_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(cache_path):
                return cache_path
                
        # Pillow resizing fallback
        with Image.open(local_path) as img:
            if is_gif:
                frames = []
                durations = []
                disposals = []
                try:
                    while True:
                        frame = img.copy().convert("RGBA")
                        frame.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                        frames.append(frame)
                        durations.append(img.info.get("duration", 100))
                        disposals.append(img.info.get("disposal", 2))
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
                    
                if frames:
                    frames[0].save(
                        cache_path,
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        disposal=disposals,
                        loop=img.info.get("loop", 0),
                        optimize=True
                    )
                else:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    img.save(cache_path)
            else:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                img.save(cache_path)
                
        if os.path.exists(cache_path):
            return cache_path
            
    except Exception:
        pass
        
    return local_path
