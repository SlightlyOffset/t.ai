import os
import json
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None

from engines.config import get_setting

@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    auto_approve: bool = False
    timeout: int = 30

class MCPClientManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MCPClientManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.configs: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self._exit_stacks: Dict[str, Any] = {}
        
        # We need to run MCP SDK in an async loop since it's fully async.
        # Create a dedicated background thread with an event loop.
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="MCPClientManagerThread")
        self._thread.start()
        
        self._initialized = True
        
        # Automatically load configs and connect to enabled servers
        self.load_server_configs()
        if get_setting("mcp_enabled", False):
            threading.Thread(target=self.connect_all, daemon=True, name="MCPConnectAllThread").start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coroutine(self, coro):
        """Run a coroutine on the background event loop and wait for result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def load_server_configs(self) -> List[MCPServerConfig]:
        """Scans mcp_servers directory and loads all JSON configurations."""
        self.configs.clear()
        
        mcp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_servers")
        if not os.path.exists(mcp_dir):
            return []
            
        for filename in os.listdir(mcp_dir):
            if not filename.endswith(".json"):
                continue
                
            filepath = os.path.join(mcp_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Validate config
                name = data.get("name", filename[:-5])
                command = data.get("command")
                if not command:
                    if get_setting("debug_mode", False):
                        print(f"[MCP] Missing command in {filename}")
                    continue
                    
                config = MCPServerConfig(
                    name=name,
                    command=command,
                    args=data.get("args", []),
                    env=data.get("env", {}),
                    enabled=data.get("enabled", True),
                    auto_approve=data.get("auto_approve", False),
                    timeout=data.get("timeout", 30)
                )
                self.configs[name] = config
            except Exception as e:
                if get_setting("debug_mode", False):
                    print(f"[MCP] Error loading {filename}: {e}")
                    
        return list(self.configs.values())

    async def _connect_server_async(self, config: MCPServerConfig):
        """Async implementation of server connection."""
        if config.name in self.sessions:
            return True
            
        try:
            from contextlib import AsyncExitStack
            
            # Setup environment mapping
            env = os.environ.copy()
            env.update(config.env)
            
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=env
            )
            
            exit_stack = AsyncExitStack()
            transport = await exit_stack.enter_async_context(stdio_client(server_params))
            read, write = transport
            
            session = await exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            self.sessions[config.name] = session
            self._exit_stacks[config.name] = exit_stack
            
            if get_setting("debug_mode", False):
                print(f"[MCP] Successfully connected to {config.name}")
                
            return True
        except Exception as e:
            if get_setting("debug_mode", False):
                print(f"[MCP] Failed to connect to {config.name}: {e}")
            return False

    def connect(self, server_name: str) -> bool:
        """Connect to a specific server by name synchronously."""
        if ClientSession is None:
            return False
            
        config = self.configs.get(server_name)
        if not config or not config.enabled:
            return False
            
        return self._run_coroutine(self._connect_server_async(config))

    def connect_all(self):
        """Connect to all enabled servers."""
        if ClientSession is None:
            return
            
        for name in self.configs:
            self.connect(name)

    async def _disconnect_server_async(self, server_name: str):
        """Async implementation of server disconnection."""
        if server_name in self._exit_stacks:
            try:
                await self._exit_stacks[server_name].aclose()
            except Exception as e:
                if get_setting("debug_mode", False):
                    print(f"[MCP] Error disconnecting {server_name}: {e}")
                    
            self.sessions.pop(server_name, None)
            self._exit_stacks.pop(server_name, None)

    def disconnect(self, server_name: str):
        """Disconnect a specific server synchronously."""
        if ClientSession is None:
            return
        self._run_coroutine(self._disconnect_server_async(server_name))

    def disconnect_all(self):
        """Disconnect all connected servers."""
        if ClientSession is None:
            return
            
        server_names = list(self.sessions.keys())
        for name in server_names:
            self.disconnect(name)

    async def _get_available_tools_async(self) -> List[Dict[str, Any]]:
        """Fetch and format tools from all connected servers async."""
        tools = []
        for server_name, session in list(self.sessions.items()):
            try:
                # Tools is an object with a .tools property containing the list
                result = await asyncio.wait_for(session.list_tools(), timeout=10.0)
                
                for tool in result.tools:
                    # Convert to OpenAI compatible format
                    # Namespace the tool name to avoid collisions
                    namespaced_name = f"{server_name}__{tool.name}"
                    
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": namespaced_name,
                            "description": tool.description or f"Tool {tool.name} from {server_name}",
                            "parameters": tool.inputSchema
                        }
                    })
            except Exception as e:
                if get_setting("debug_mode", False):
                    print(f"[MCP] Failed to list tools for {server_name}: {e}")
                # Optional: trigger reconnect or cleanup if connection is dead
                pass
                
        return tools

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return aggregated tool schemas from all connected servers."""
        if ClientSession is None or not self.sessions:
            return []
            
        return self._run_coroutine(self._get_available_tools_async())

    async def _call_tool_async(self, server_name: str, tool_name: str, arguments: Dict[str, Any], timeout: int) -> str:
        """Call a specific tool on a specific server async."""
        session = self.sessions.get(server_name)
        if not session:
            return json.dumps({"error": f"Server {server_name} is not connected."})
            
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout
            )
            
            if result.isError:
                return json.dumps({"error": "Tool execution returned an error.", "details": [c.text for c in result.content if hasattr(c, 'text')]})
                
            # Aggregate content
            content_pieces = []
            for item in result.content:
                if hasattr(item, 'text') and item.text:
                    content_pieces.append(item.text)
                elif hasattr(item, 'data') and hasattr(item, 'mimeType'):
                    # Handle binary/image data if present (for now just returning info)
                    content_pieces.append(f"[Media: {item.mimeType}]")
                    
            if not content_pieces:
                return json.dumps({"result": "Success, no output"})
                
            return "\n".join(content_pieces)
            
        except asyncio.TimeoutError:
            return json.dumps({"error": f"Tool execution timed out after {timeout} seconds."})
        except Exception as e:
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    def call_tool(self, namespaced_name: str, arguments: Dict[str, Any]) -> str:
        """Route and execute a tool call synchronously."""
        if ClientSession is None:
            return json.dumps({"error": "MCP is not available. Please ensure mcp SDK is installed."})
            
        if "__" not in namespaced_name:
            return json.dumps({"error": f"Invalid tool name format: {namespaced_name}. Expected server__tool."})
            
        server_name, tool_name = namespaced_name.split("__", 1)
        
        config = self.configs.get(server_name)
        timeout = config.timeout if config else 30
        
        return self._run_coroutine(self._call_tool_async(server_name, tool_name, arguments, timeout))

    def get_status(self) -> Dict[str, Any]:
        """Return connection status of all loaded server configs."""
        status = {}
        for name, config in self.configs.items():
            status[name] = {
                "enabled": config.enabled,
                "auto_approve": config.auto_approve,
                "connected": name in self.sessions
            }
        return status

    def update_auto_approve(self, server_name: str, auto_approve: bool):
        """Update auto-approve state in config and persist."""
        if server_name in self.configs:
            self.configs[server_name].auto_approve = auto_approve
            
            # Persist to JSON
            mcp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_servers")
            filepath = os.path.join(mcp_dir, f"{server_name}.json")
            
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        
                    data["auto_approve"] = auto_approve
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4)
                        
                    if get_setting("debug_mode", False):
                        print(f"[MCP] Updated auto_approve for {server_name} to {auto_approve}")
                except Exception as e:
                    if get_setting("debug_mode", False):
                        print(f"[MCP] Failed to save config for {server_name}: {e}")

# Global instance for easy access
mcp_manager = MCPClientManager()
