#!/usr/bin/env python3
"""
Standalone LLM Bridge for Colab/Kaggle with optional Cloudflare Quick Tunnel support.

This script can run as a standalone HTTP server that bridges local requests to
a remote LLM endpoint. It supports both Ngrok and Cloudflare Quick Tunnels for
exposing the bridge to the internet.

Usage:
    python standalone_llm_bridge.py --tunnel cloudflare
    python standalone_llm_bridge.py --tunnel ngrok
    python standalone_llm_bridge.py  # No tunnel, local only
"""

import argparse
import asyncio
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence noisy third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

# Disable TQDM progress bars (HF downloads)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

FALLBACK_UNAVAILABLE_MESSAGE = "System busy/unavailable. Please retry in a moment."


def _get_gpu_metrics():
    gpus = []
    vram_allocated = None
    vram_reserved = None
    vram_total = None
    try:
        # Run nvidia-smi command to get memory details
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(",")
            if len(parts) == 3:
                gpu_id = int(parts[0].strip())
                used_mib = float(parts[1].strip())
                total_mib = float(parts[2].strip())
                
                # Convert to GiB
                used_gib = used_mib / 1024.0
                total_gib = total_mib / 1024.0
                
                gpus.append({
                    "id": gpu_id,
                    "allocated_gib": used_gib,
                    "reserved_gib": used_gib,
                    "total_gib": total_gib
                })
        if gpus:
            vram_allocated = gpus[0]["allocated_gib"]
            vram_reserved = gpus[0]["reserved_gib"]
            vram_total = gpus[0]["total_gib"]
    except Exception:
        pass
    return gpus, vram_allocated, vram_reserved, vram_total


class LoreManager:
    """Manages vector embeddings and semantic retrieval of lore entries."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        # Do not mutate global SENTENCE_TRANSFORMERS_AVAILABLE here; keep availability as a read-only
        # environment probe and track instance-level availability on the object.
        self.model_name = model_name
        self.model = None
        self.lore_entries = []
        self.embeddings = None
        self.st_available = SENTENCE_TRANSFORMERS_AVAILABLE

        if self.st_available:
            try:
                # Still show this one as it's the main progress indicator
                print(f"[*] Initializing Lore Engine on CPU ({model_name})...")
                self.model = SentenceTransformer(model_name, device="cpu")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # Mark instance-level availability as False; do not change module-global flag
                self.st_available = False

    def embed_and_index(self, lorebook: dict) -> bool:
        """
        Embed all lore entries and store them in memory.

        Args:
            lorebook: Dictionary with 'entries' list containing lore items

        Returns:
            bool: True if indexing succeeded, False otherwise
        """
        if not self.model:
            logger.warning("Embedding model not available; RAG disabled")
            return False

        try:
            entries = lorebook.get("entries", [])
            if not entries:
                self.lore_entries = []
                self.embeddings = np.array([])
                return True

            # Filter and prepare entries
            self.lore_entries = [
                entry for entry in entries
                if entry.get("enabled", True)
            ]

            if not self.lore_entries:
                self.embeddings = np.array([])
                return True

            # Extract text content to embed
            texts_to_embed = [
                f"{entry.get('title', '')} {entry.get('content', '')}"
                for entry in self.lore_entries
            ]

            self.embeddings = self.model.encode(texts_to_embed, convert_to_numpy=True)
            print(f"[+] Successfully indexed {len(self.lore_entries)} lore entries")
            return True

        except Exception as e:
            logger.error(f"Failed to embed and index lorebook: {e}")
            return False

    def retrieve_top_k(self, query: str, k: int = 3) -> list[str]:
        """
        Retrieve top K most similar lore entries using cosine similarity.

        Args:
            query: User's message to search for
            k: Number of top entries to retrieve

        Returns:
            list[str]: Formatted lore entries, or empty list if retrieval failed
        """
        if not self.model or not self.lore_entries or len(self.lore_entries) == 0:
            return []

        try:
            # Embed the query
            query_embedding = self.model.encode(query, convert_to_numpy=True)

            # Compute cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity([query_embedding], self.embeddings)[0]

            # Get top K indices
            top_k_indices = np.argsort(similarities)[::-1][:k]

            # Filter by threshold (only return if similarity > 0.3)
            relevant_entries = []
            for idx in top_k_indices:
                if similarities[idx] > 0.3:
                    entry = self.lore_entries[idx]
                    relevant_entries.append(
                        f"[LORE: {entry.get('title', 'Unknown')}]\n{entry.get('content', '')}"
                    )

            return relevant_entries

        except Exception as e:
            logger.error(f"Error retrieving lore: {e}")
            return []


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    max_tokens: int = 512
    temperature: float = 0.8
    repetition_penalty: float = 1.15
    n: int = 1
    model: str = "default"
    use_rag: bool = False


class SyncLoreRequest(BaseModel):
    entries: list = []


class LLMEngine:
    """Ollama-backed inference engine that manages a local Ollama server process."""

    def __init__(self, model_id: str, hf_token: Optional[str] = None):
        self.model_id = model_id
        self.error: Optional[str] = None
        self.ready = False
        self.ollama_url = "http://localhost:11434"
        
        # Match expected interface for the health check endpoint
        self.workers = {}
        self.multi_gpu = False
        
        self._initialize_ollama()

    def _initialize_ollama(self):
        print(f"[*] Initializing Ollama backend for model: {self.model_id}")
        
        # 1. Check if Ollama is installed (executable exists in system path)
        import shutil
        if not shutil.which("ollama"):
            self.error = "Ollama CLI is not installed or not in PATH. Please run the installer cell first."
            logger.error(self.error)
            return

        # 2. Check if Ollama server is already running, if not, start it
        if not self._is_ollama_running():
            print("[*] Ollama server is not running. Starting Ollama daemon in background...")
            try:
                # Start ollama serve in background
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True
                )
                
                # Wait for Ollama to spin up (up to 15 seconds)
                for i in range(15):
                    time.sleep(1.0)
                    if self._is_ollama_running():
                        print("[+] Ollama server started successfully.")
                        break
                else:
                    self.error = "Failed to start Ollama server within 15 seconds."
                    logger.error(self.error)
                    return
            except Exception as e:
                self.error = f"Error launching Ollama server: {e}"
                logger.error(self.error)
                return
        else:
            print("[+] Ollama server is already running.")

        # 3. Check if the model is downloaded. If not, pull it.
        if not self._is_model_downloaded():
            print(f"[*] Model '{self.model_id}' is not in local registry. Pulling from Ollama registry (this may take a few minutes)...")
            try:
                process = subprocess.Popen(
                    ["ollama", "pull", self.model_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                # Stream the pulling progress to standard output
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    print(line.strip())
                process.wait()
                if process.returncode != 0:
                    self.error = f"Failed to pull model '{self.model_id}'. Return code: {process.returncode}"
                    logger.error(self.error)
                    return
                print(f"[+] Model '{self.model_id}' pulled successfully.")
            except Exception as e:
                self.error = f"Error pulling model: {e}"
                logger.error(self.error)
                return
        else:
            print(f"[+] Model '{self.model_id}' is ready.")

        self.ready = True
        self.workers = {0: {}}  # Mock single worker for health check metrics

    def _is_ollama_running(self) -> bool:
        import requests
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _is_model_downloaded(self) -> bool:
        import requests
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                
                # Check for exact match or normalized tags
                model_names = [m.get("name") for m in models]
                normalized_target = self.model_id.lower()
                if ":" not in normalized_target:
                    normalized_target += ":latest"
                
                for name in model_names:
                    norm_name = name.lower()
                    if ":" not in norm_name:
                        norm_name += ":latest"
                    if norm_name == normalized_target or norm_name.endswith("/" + normalized_target):
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking downloaded models: {e}")
            return False

    def generate_stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.8,
        repetition_penalty: float = 1.15,
        **kwargs,
    ):
        import requests
        import json
        
        if not self.ready:
            yield FALLBACK_UNAVAILABLE_MESSAGE
            return

        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "repeat_penalty": repetition_penalty,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                stream=True,
                timeout=60
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"Ollama streaming generation error: {e}")
            yield FALLBACK_UNAVAILABLE_MESSAGE

    def generate_batch(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.8,
        repetition_penalty: float = 1.15,
        n: int = 1,
        **kwargs,
    ) -> list[str]:
        import requests
        
        if not self.ready:
            return [FALLBACK_UNAVAILABLE_MESSAGE for _ in range(max(1, n))]

        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "repeat_penalty": repetition_penalty,
                "num_predict": max_tokens
            }
        }
        
        results = []
        for i in range(max(1, n)):
            try:
                # Add slight temp variation for subsequent candidates if n > 1
                if i > 0:
                    payload["options"]["temperature"] = min(1.2, temperature + (0.05 * i))
                
                response = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=90
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "").strip()
                results.append(content or FALLBACK_UNAVAILABLE_MESSAGE)
            except Exception as e:
                logger.error(f"Ollama batch generation error on candidate {i}: {e}")
                results.append(FALLBACK_UNAVAILABLE_MESSAGE)
        return results



class TunnelManager:
    """Manager for Cloudflare and Ngrok tunnels."""

    def __init__(self, tunnel_type: str = "none", local_port: int = 8000):
        self.tunnel_type = tunnel_type
        self.local_port = local_port
        self.public_url: Optional[str] = None
        self.process = None

    def start(self) -> Optional[str]:
        """Start the tunnel and return the public URL."""
        if self.tunnel_type == "cloudflare":
            return self._start_cloudflare()
        elif self.tunnel_type == "ngrok":
            return self._start_ngrok()
        else:
            print(f"[*] Local mode: http://localhost:{self.local_port}")
            return None

    def _start_cloudflare(self) -> Optional[str]:
        """Start Cloudflare Quick Tunnel."""
        cf_path = self._get_cloudflared_path()
        if not os.path.exists(cf_path):
            print("[*] Downloading cloudflared...")
            self._download_cloudflared(cf_path)

        try:
            # Start cloudflared tunnel
            self.process = subprocess.Popen(
                [cf_path, "tunnel", "--url", f"http://localhost:{self.local_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Read output to extract URL
            self.public_url = self._extract_cloudflare_url()

            if self.public_url:
                print(f"\n[🚀] BRIDGE ONLINE: {self.public_url}\n")
                return self.public_url
            else:
                logger.error("Failed to extract Cloudflare URL")
                self._cleanup()
                return None

        except Exception as e:
            logger.error(f"Failed to start Cloudflare tunnel: {e}")
            self._cleanup()
            return None

    def _start_ngrok(self) -> Optional[str]:
        """Start Ngrok tunnel (requires pyngrok and NGROK_TOKEN env var)."""
        try:
            from pyngrok import ngrok
        except ImportError:
            logger.error("pyngrok not installed. Install with: pip install pyngrok")
            return None

        try:
            ngrok_token = os.getenv("NGROK_TOKEN")
            if ngrok_token:
                ngrok.set_auth_token(ngrok_token)

            self.public_url = ngrok.connect(self.local_port).public_url
            print(f"\n[🚀] BRIDGE ONLINE: {self.public_url}\n")
            return self.public_url

        except Exception as e:
            logger.error(f"Failed to start Ngrok tunnel: {e}")
            return None

    def _get_cloudflared_path(self) -> str:
        """Get path to cloudflared binary."""
        home = os.path.expanduser("~")
        cf_dir = os.path.join(home, ".cloudflared")
        os.makedirs(cf_dir, exist_ok=True)
        return os.path.join(cf_dir, "cloudflared")

    def _download_cloudflared(self, cf_path: str):
        """Download cloudflared binary for Linux amd64."""
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"

        try:
            subprocess.run(
                ["curl", "-L", "-s", "-o", cf_path, url],
                check=True
            )
            os.chmod(cf_path, 0o755)
        except Exception as e:
            logger.error(f"Failed to download cloudflared: {e}")
            raise

    def _extract_cloudflare_url(self) -> Optional[str]:
        """Extract Cloudflare URL from process output (reads stderr and stdout)."""
        if not self.process:
            return None

        try:
            output_lines = []
            for attempt in range(20):  # Wait up to 20s
                if self.process.poll() is not None:
                    break

                # Try to read from stderr (non-blocking)
                try:
                    if self.process.stderr:
                        line = self.process.stderr.readline()
                        if line:
                            output_lines.append(line)
                except Exception:
                    pass

                # Check accumulated output for URL
                combined = ''.join(output_lines)
                match = re.search(r'(https://[a-z0-9\-]+\.trycloudflare\.com)', combined)
                if match:
                    return match.group(1)

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error extracting Cloudflare URL: {e}")

        return None

    def _cleanup(self):
        """Clean up tunnel process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass


def _inject_rag_into_messages(messages: list[dict], lore_manager: LoreManager) -> list[dict]:
    """Retrieve relevant lore and prepend it to the system context."""
    if not lore_manager.model or not messages:
        return messages

    user_message = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content")
            break

    if not user_message:
        return messages

    retrieved_lore = lore_manager.retrieve_top_k(user_message, k=3)
    if not retrieved_lore:
        return messages

    lore_text = "\n\n".join(retrieved_lore)
    updated_messages = list(messages)
    for i, msg in enumerate(updated_messages):
        if msg.get("role") == "system":
            updated_messages[i] = {
                "role": "system",
                "content": f"{lore_text}\n\n{msg.get('content', '')}",
            }
            return updated_messages

    return [{"role": "system", "content": lore_text}, *updated_messages]


def create_app(
    tunnel_manager: Optional[TunnelManager] = None,
    lore_manager: Optional[LoreManager] = None,
    llm_engine: Optional[LLMEngine] = None,
) -> FastAPI:
    """Create FastAPI app for the bridge."""
    app = FastAPI(title="LLM Bridge", version="1.0.0")

    if lore_manager is None:
        lore_manager = LoreManager()

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        gpus, vram_allocated, vram_reserved, vram_total = _get_gpu_metrics()
        return {
            "status": "healthy",
            "tunnel_type": tunnel_manager.tunnel_type if tunnel_manager else "none",
            "public_url": tunnel_manager.public_url if tunnel_manager else None,
            "rag_enabled": bool(lore_manager.model),
            "lore_entries_indexed": len(lore_manager.lore_entries),
            "llm_ready": bool(llm_engine and llm_engine.ready),
            "llm_model": llm_engine.model_id if llm_engine else None,
            "llm_workers": len(llm_engine.workers) if llm_engine else 0,
            "llm_multi_gpu": bool(llm_engine and llm_engine.multi_gpu),
            "vram_allocated_gib": vram_allocated,
            "vram_reserved_gib": vram_reserved,
            "vram_total_gib": vram_total,
            "gpus": gpus,
        }

    @app.post("/sync_lore")
    async def sync_lore(request: dict):
        """Sync and index lorebook entries for semantic retrieval."""
        try:
            if not lore_manager.model:
                return {
                    "status": "error",
                    "message": "Embedding model not available; RAG disabled"
                }

            lorebook = {"entries": request.get("entries", [])}
            success = lore_manager.embed_and_index(lorebook)

            if success:
                return {
                    "status": "success",
                    "message": f"Indexed {len(lore_manager.lore_entries)} lore entries",
                    "entries_count": len(lore_manager.lore_entries)
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to index lorebook"
                }
        except Exception:
            # Log full exception locally but do not expose stack traces or internal errors to callers.
            logger.exception("Unhandled exception in /sync_lore")
            return {
                "status": "error",
                "message": "Internal server error while indexing lore"
            }

    @app.post("/chat")
    async def chat(request: ChatRequest):
        """Chat endpoint that streams responses, with optional server-side RAG."""
        # Visual feedback for the bridge operator
        user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "...")
        # Only log snippet if debug mode (simulated here via environment) is on to protect PII
        if os.getenv("BRIDGE_DEBUG", "0").lower() in ("1", "true", "yes"):
            logger.info(f"[*] Received request (n={request.n}): {user_msg[:50]}...")
        else:
            logger.info(f"[*] Received request (n={request.n}, messages={len(request.messages)})")
        
        # Prepare messages for LLM
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        # Server-side RAG: retrieve lore and inject into system prompt
        if request.use_rag:
            messages = _inject_rag_into_messages(messages, lore_manager)

        if not llm_engine:
            if request.n > 1:
                return {"candidates": [FALLBACK_UNAVAILABLE_MESSAGE for _ in range(max(1, request.n))]}
            return StreamingResponse(iter([FALLBACK_UNAVAILABLE_MESSAGE]), media_type="text/plain")

        if request.n > 1:
            candidates = llm_engine.generate_batch(
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                repetition_penalty=request.repetition_penalty,
                n=request.n,
            )
            return {"candidates": candidates}

        stream = llm_engine.generate_stream(
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            repetition_penalty=request.repetition_penalty,
        )
        return StreamingResponse(stream, media_type="text/plain")

    return app



def main():
    parser = argparse.ArgumentParser(
        description="Standalone LLM Bridge with optional tunneling and semantic RAG"
    )
    parser.add_argument(
        "--tunnel",
        choices=["none", "cloudflare", "ngrok"],
        default="none",
        help="Tunnel type to use for exposing the bridge"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Local port to run the server on"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--model",
        default="Sao10K/L3-8B-Stheno-v3.2",
        help="HuggingFace model ID for CausalLM generation"
    )
    parser.add_argument(
        "--hf_token",
        default=None,
        help="HuggingFace token (or use HF_TOKEN env var)"
    )

    args = parser.parse_args()

    # Create tunnel manager
    tunnel_manager = TunnelManager(tunnel_type=args.tunnel, local_port=args.port)

    # Create LoreManager for semantic RAG
    lore_manager = LoreManager()
    llm_engine = LLMEngine(model_id=args.model, hf_token=args.hf_token)

    # Start tunnel if enabled
    if args.tunnel != "none":
        public_url = tunnel_manager.start()
        if not public_url:
            logger.error(f"Failed to start {args.tunnel} tunnel")
            sys.exit(1)

    # Create FastAPI app
    app = create_app(tunnel_manager, lore_manager, llm_engine)

    # Run server
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="warning"
        )
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel_manager:
            tunnel_manager._cleanup()



if __name__ == "__main__":
    main()
