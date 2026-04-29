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
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    max_tokens: int = 1024
    temperature: float = 0.8
    model: str = "default"


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
            logger.info(f"No tunnel enabled. Server running on http://localhost:{self.local_port}")
            return None
    
    def _start_cloudflare(self) -> Optional[str]:
        """Start Cloudflare Quick Tunnel."""
        logger.info("Starting Cloudflare Quick Tunnel...")
        
        # Download cloudflared binary if not present
        cf_path = self._get_cloudflared_path()
        if not os.path.exists(cf_path):
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
            
            # Wait for tunnel URL to appear in output
            logger.info("Waiting for Cloudflare tunnel URL...")
            time.sleep(3)
            
            # Read output to extract URL
            self.public_url = self._extract_cloudflare_url()
            
            if self.public_url:
                logger.info(f"🚀 Cloudflare tunnel online: {self.public_url}")
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
                logger.info("NGROK_TOKEN loaded")
            else:
                logger.warning("NGROK_TOKEN not found in environment")
            
            logger.info("Starting Ngrok tunnel...")
            self.public_url = ngrok.connect(self.local_port).public_url
            logger.info(f"🚀 Ngrok tunnel online: {self.public_url}")
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
        logger.info("Downloading cloudflared binary...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        
        try:
            result = subprocess.run(
                ["curl", "-L", "-o", cf_path, url],
                capture_output=True,
                text=True,
                check=True
            )
            os.chmod(cf_path, 0o755)
            logger.info(f"Downloaded cloudflared to {cf_path}")
        except Exception as e:
            logger.error(f"Failed to download cloudflared: {e}")
            raise
    
    def _extract_cloudflare_url(self) -> Optional[str]:
        """Extract Cloudflare URL from process output (reads stderr and stdout)."""
        if not self.process:
            return None
        
        try:
            import select
            
            # cloudflared outputs the tunnel URL to stderr, not stdout
            # We need to read both stderr and stdout
            output_lines = []
            
            for attempt in range(15):  # Try for ~15 seconds
                if self.process.poll() is not None:
                    # Process ended
                    if self.process.stderr:
                        remaining = self.process.stderr.read()
                        if remaining:
                            output_lines.append(remaining)
                    if self.process.stdout:
                        remaining = self.process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                    break
                
                # Try to read from stderr (non-blocking)
                try:
                    if self.process.stderr:
                        line = self.process.stderr.readline()
                        if line:
                            output_lines.append(line)
                            logger.debug(f"cloudflared: {line.strip()}")
                except Exception:
                    pass
                
                # Check accumulated output for URL
                combined = ''.join(output_lines)
                match = re.search(r'(https://[a-z0-9\-]+\.trycloudflare\.com)', combined)
                if match:
                    logger.info(f"Found tunnel URL: {match.group(1)}")
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


def create_app(tunnel_manager: Optional[TunnelManager] = None) -> FastAPI:
    """Create FastAPI app for the bridge."""
    app = FastAPI(title="LLM Bridge", version="1.0.0")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "tunnel_type": tunnel_manager.tunnel_type if tunnel_manager else "none",
            "public_url": tunnel_manager.public_url if tunnel_manager else None
        }
    
    @app.post("/chat")
    async def chat(request: ChatRequest):
        """Chat endpoint that streams responses."""
        logger.info(f"Chat request with {len(request.messages)} messages")
        
        # This is a placeholder implementation
        # In a real scenario, this would connect to an LLM
        async def generate():
            yield "This is a placeholder response from the LLM Bridge. "
            yield "In a production setup, this would connect to your actual LLM endpoint."
        
        return StreamingResponse(generate(), media_type="text/plain")
    
    return app


def main():
    parser = argparse.ArgumentParser(
        description="Standalone LLM Bridge with optional tunneling"
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
    
    args = parser.parse_args()
    
    # Create tunnel manager
    tunnel_manager = TunnelManager(tunnel_type=args.tunnel, local_port=args.port)
    
    # Start tunnel if enabled
    if args.tunnel != "none":
        public_url = tunnel_manager.start()
        if not public_url:
            logger.error(f"Failed to start {args.tunnel} tunnel")
            sys.exit(1)
    
    # Create FastAPI app
    app = create_app(tunnel_manager)
    
    # Run server
    logger.info(f"Starting server on {args.host}:{args.port}")
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
    finally:
        if tunnel_manager:
            tunnel_manager._cleanup()


if __name__ == "__main__":
    main()
