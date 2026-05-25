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

# Reduce CUDA allocator fragmentation unless caller already set a policy.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

try:
    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TextIteratorStreamer,
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    BitsAndBytesConfig = None
    TextIteratorStreamer = None


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
DEFAULT_GPU_MAX_MEMORY_GIB = int(os.getenv("LLM_WORKER_GPU_MAX_GIB", "13"))
DEFAULT_CPU_MAX_MEMORY_GIB = int(os.getenv("LLM_WORKER_CPU_MAX_GIB", "24"))


def _is_oom_or_gpu_error(exc: Exception) -> bool:
    message = str(exc).lower()
    gpu_markers = (
        "out of memory",
        "cuda error",
        "cublas",
        "cudnn",
        "device-side assert",
    )
    return any(marker in message for marker in gpu_markers)


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
    max_tokens: int = 1024
    temperature: float = 0.8
    repetition_penalty: float = 1.15
    n: int = 1
    model: str = "default"
    use_rag: bool = False


class SyncLoreRequest(BaseModel):
    entries: list = []


class LLMEngine:
    """Transformers-backed inference engine with dual-worker GPU pool support."""

    def __init__(self, model_id: str, hf_token: Optional[str] = None):
        self.model_id = model_id
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.workers: dict[int, dict] = {}
        self.error: Optional[str] = None
        self.ready = False
        self.multi_gpu = False
        self._initialize_workers()

    def _initialize_workers(self):
        if not TRANSFORMERS_AVAILABLE:
            self.error = "transformers stack is not installed"
            logger.error("LLM engine unavailable: transformers stack is not installed")
            return

        worker_targets: list[int | None]
        if torch and torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            worker_targets = [0, 1] if gpu_count > 1 else [0]
            self.multi_gpu = gpu_count > 1
            mode_label = "Dual-Worker Pool" if self.multi_gpu else "Single-Worker GPU"
            print(f"[*] Initializing {mode_label} for model: {self.model_id}")
        else:
            worker_targets = [None]
            self.multi_gpu = False
            print(f"[*] Initializing CPU fallback worker for model: {self.model_id}")

        for worker_id, device_id in enumerate(worker_targets):
            worker = self._load_worker(worker_id, device_id)
            if worker:
                self.workers[worker_id] = worker

        self.ready = bool(self.workers)
        if not self.ready:
            self.error = self.error or f"Failed to load any worker for model '{self.model_id}'"
            logger.error(self.error)
        else:
            print(f"[+] LLM worker pool ready with {len(self.workers)} worker(s)")

    def _load_worker(self, worker_id: int, device_id: int | None) -> Optional[dict]:
        try:
            device_label = f"cuda:{device_id}" if device_id is not None else "cpu"
            print(f"[*] Loading worker {worker_id} on {device_label}...")

            tokenizer_kwargs = {"trust_remote_code": True}
            if self.hf_token:
                tokenizer_kwargs["token"] = self.hf_token
            tokenizer = AutoTokenizer.from_pretrained(self.model_id, **tokenizer_kwargs)
            if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Suppress clean_up_tokenization_spaces warning for BPE tokenizers
            # This is specifically for BPE (like Llama-3) where cleanup can be destructive.
            if hasattr(tokenizer, "clean_up_tokenization_spaces") and "TokenizerFast" in str(type(tokenizer)):
                tokenizer.clean_up_tokenization_spaces = False

            model_kwargs = {"trust_remote_code": True}
            if self.hf_token:
                model_kwargs["token"] = self.hf_token

            if device_id is not None:
                model_kwargs["device_map"] = f"cuda:{device_id}"
                model_kwargs["torch_dtype"] = torch.float16
                model_kwargs["low_cpu_mem_usage"] = True
                model_kwargs["attn_implementation"] = "sdpa"
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                )
            else:
                model_kwargs["device_map"] = "cpu"
                model_kwargs["torch_dtype"] = torch.float32

            try:
                model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)
            except Exception as exc:
                if device_id is None or not _is_oom_or_gpu_error(exc):
                    raise

                logger.warning(
                    f"Worker {worker_id} hit OOM on {device_label}. Retrying with strict VRAM packing..."
                )
                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # Tighter packing: force strict device map and maximize GPU usage (14GiB)
                retry_kwargs = dict(model_kwargs)
                # Correct device_map syntax: {"": device_id} pins the whole model
                retry_kwargs["device_map"] = {"": device_id}
                retry_kwargs["max_memory"] = {device_id: "14GiB", "cpu": f"{DEFAULT_CPU_MAX_MEMORY_GIB}GiB"}
                model = AutoModelForCausalLM.from_pretrained(self.model_id, **retry_kwargs)

            model.eval()
            if torch and device_id is not None and torch.cuda.is_available():
                torch.cuda.set_device(device_id)
                torch.cuda.empty_cache()
            return {
                "worker_id": worker_id,
                "device_id": device_id,
                "device_label": device_label,
                "model": model,
                "tokenizer": tokenizer,
                "lock": threading.Lock(),
            }
        except Exception as exc:
            self.error = str(exc)
            logger.error(f"Failed to load worker {worker_id}: {exc}")
            return None

    def _build_inputs(self, worker: dict, messages: list[dict]):
        tokenizer = worker["tokenizer"]
        device_label = worker["device_label"]
        if tokenizer.chat_template:
            return tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            ).to(device_label)

        prompt_lines = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt_lines.append(f"{role.upper()}: {content}")
        prompt_lines.append("ASSISTANT:")
        prompt = "\n".join(prompt_lines)
        return tokenizer(prompt, return_tensors="pt").to(device_label)

    def _generation_kwargs(self, tokenizer, max_tokens: int, temperature: float, repetition_penalty: float) -> dict:
        use_sampling = temperature > 0
        safe_repetition_penalty = repetition_penalty if repetition_penalty > 0 else 1.15
        return {
            "max_new_tokens": max_tokens,
            "temperature": temperature if use_sampling else 1.0,
            "do_sample": use_sampling,
            "repetition_penalty": safe_repetition_penalty,
            "pad_token_id": tokenizer.pad_token_id or (tokenizer.eos_token_id[0] if isinstance(tokenizer.eos_token_id, list) else tokenizer.eos_token_id),
            "use_cache": True,
        }

    def _fallback_candidates(self, n: int) -> list[str]:
        return [FALLBACK_UNAVAILABLE_MESSAGE for _ in range(max(1, n))]

    def _worker_generate_once(
        self,
        worker: dict,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        repetition_penalty: float,
        **kwargs,
    ) -> str:
        model = worker["model"]
        tokenizer = worker["tokenizer"]
        device_id = worker["device_id"]
        device_label = worker["device_label"]
        with worker["lock"]:
            if torch and device_id is not None and torch.cuda.is_available():
                torch.cuda.set_device(device_id)
            
            inputs = self._build_inputs(worker, messages)
            
            # Context Truncation: Prevent RoPE kernel crashes by enforcing model limits
            max_pos = getattr(model.config, "max_position_embeddings", 8192)
            
            # Ensure max_tokens doesn't exceed 90% of the total context window
            max_tokens = min(max_tokens, int(max_pos * 0.9))
            
            input_len = inputs.input_ids.shape[1]
            if input_len + max_tokens > max_pos:
                # Slicing from the left (keep the most recent context)
                keep_len = max_pos - max_tokens - 10 # 10 token safety buffer
                
                # If keep_len is too small, force at least 128 tokens of context by shrinking max_tokens
                if keep_len < 128:
                    keep_len = 128
                    max_tokens = max_pos - keep_len - 10

                # Truncate all tensor keys uniformly to avoid shape mismatches
                for key in list(inputs.keys()):
                    if hasattr(inputs[key], "shape") and inputs[key].shape[-1] == input_len:
                        inputs[key] = inputs[key][:, -keep_len:]
                input_len = inputs.input_ids.shape[1]
                logger.info(f"Worker {worker['worker_id']} truncated context to {input_len} tokens")

            gen_kwargs = self._generation_kwargs(
                tokenizer,
                max_tokens=max_tokens,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )
            # Add any extra kwargs from the caller
            gen_kwargs.update(kwargs)
            
            with torch.no_grad():
                output_tokens = model.generate(
                    **inputs,
                    **gen_kwargs,
                    num_return_sequences=1,
                )
            result = tokenizer.decode(output_tokens[0][input_len:], skip_special_tokens=True).strip()
            if torch and device_id is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
            return result

    def _pick_stream_worker(self) -> dict:
        ordered_ids = sorted(self.workers.keys())
        if len(ordered_ids) > 1:
            primary = self.workers[ordered_ids[0]]
            secondary = self.workers[ordered_ids[1]]
            if primary["lock"].locked() and not secondary["lock"].locked():
                return secondary
        return self.workers[ordered_ids[0]]

    def generate_batch(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.8,
        repetition_penalty: float = 1.15,
        n: int = 1,
        **kwargs,
    ) -> list[str]:
        if not self.ready:
            return self._fallback_candidates(n)

        task_total = max(1, n)
        results: list[str] = [""] * task_total
        task_queue: queue.Queue[int] = queue.Queue()
        for idx in range(task_total):
            task_queue.put(idx)

        def pool_manager(worker: dict):
            device_id = worker["device_id"]
            if torch and device_id is not None and torch.cuda.is_available():
                torch.cuda.set_device(device_id)

            while True:
                try:
                    task_idx = task_queue.get_nowait()
                except queue.Empty:
                    break

                try:
                    candidate = self._worker_generate_once(
                        worker,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        repetition_penalty=repetition_penalty,
                        **kwargs,
                    )
                    results[task_idx] = candidate or FALLBACK_UNAVAILABLE_MESSAGE
                except Exception as exc:
                    if _is_oom_or_gpu_error(exc):
                        logger.error(f"GPU generation error (worker {worker['worker_id']}): {exc}")
                        if torch and device_id is not None and torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        results[task_idx] = FALLBACK_UNAVAILABLE_MESSAGE
                    else:
                        logger.error(f"Batch generation failed on worker {worker['worker_id']}: {exc}")
                        results[task_idx] = FALLBACK_UNAVAILABLE_MESSAGE
                finally:
                    task_queue.task_done()

        threads = []
        for worker_id in sorted(self.workers.keys()):
            thread = threading.Thread(target=pool_manager, args=(self.workers[worker_id],), daemon=True)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        return [candidate if candidate else FALLBACK_UNAVAILABLE_MESSAGE for candidate in results]

    def generate_stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.8,
        repetition_penalty: float = 1.15,
        **kwargs,
    ):
        if not self.ready:
            yield FALLBACK_UNAVAILABLE_MESSAGE
            return

        worker = self._pick_stream_worker()
        model = worker["model"]
        tokenizer = worker["tokenizer"]
        worker_id = worker["worker_id"]
        device_id = worker["device_id"]
        
        with worker["lock"]:
            generation_thread = None
            try:
                if torch and device_id is not None and torch.cuda.is_available():
                    torch.cuda.set_device(device_id)

                inputs = self._build_inputs(worker, messages)
                
                # Context Truncation for Stream: Prevent RoPE kernel crashes
                max_pos = getattr(model.config, "max_position_embeddings", 8192)
                max_tokens = min(max_tokens, int(max_pos * 0.9))
                input_len = inputs.input_ids.shape[1]
                
                if input_len + max_tokens > max_pos:
                    keep_len = max_pos - max_tokens - 10
                    if keep_len < 128:
                        keep_len = 128
                        max_tokens = max_pos - keep_len - 10
                    
                    # Truncate all tensor keys uniformly to avoid shape mismatches
                    for key in list(inputs.keys()):
                        if hasattr(inputs[key], "shape") and inputs[key].shape[-1] == input_len:
                            inputs[key] = inputs[key][:, -keep_len:]
                    logger.info(f"Worker {worker_id} truncated stream context to {inputs.input_ids.shape[1]} tokens")

                streamer = TextIteratorStreamer(
                    tokenizer,
                    skip_prompt=True,
                    skip_special_tokens=True,
                )
                gen_kwargs = self._generation_kwargs(
                    tokenizer,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                )
                generation_kwargs = {
                    **inputs,
                    **gen_kwargs,
                    **kwargs,
                    "streamer": streamer,
                }

                def threaded_generate():
                    if torch and device_id is not None and torch.cuda.is_available():
                        torch.cuda.set_device(device_id)
                    model.generate(**generation_kwargs)

                generation_thread = threading.Thread(
                    target=threaded_generate,
                    daemon=True,
                )
                generation_thread.start()

                for chunk in streamer:
                    if chunk:
                        yield chunk

            except Exception as exc:
                if _is_oom_or_gpu_error(exc):
                    logger.error(f"GPU generation error (stream worker {worker_id}): {exc}")
                else:
                    logger.error(f"Streaming generation failed on worker {worker_id}: {exc}")
                yield FALLBACK_UNAVAILABLE_MESSAGE
            finally:
                # Ensure the generation thread finishes before releasing the lock.
                # This prevents subsequent requests from colliding with a dangling thread.
                if generation_thread is not None and generation_thread.is_alive():
                    generation_thread.join()
                if torch and device_id is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()



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
