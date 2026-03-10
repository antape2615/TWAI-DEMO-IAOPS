import asyncio, os, shutil, logging
from contextlib import AsyncExitStack
from typing import Any, Optional, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class Tool:
    def __init__(self, name: str, description: str, input_schema: dict, title: Optional[str] = None):
        self.name, self.description, self.input_schema, self.title = name, description, input_schema, title

class Server:
    def __init__(self, name: str, config: dict) -> None:
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        cmd_cfg = self.config.get("command")
        command = shutil.which("npx") if cmd_cfg == "npx" else cmd_cfg
        if not command:
            raise ValueError(f"[{self.name}] Invalid 'command'")
        params = StdioServerParameters(
            command=command,
            args=self.config.get("args", []),
            env={**os.environ, **self.config.get("env", {})} if self.config.get("env") else None,
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()

    async def list_tools(self) -> List[Tool]:
        if not self.session: return []
        tools_response = await self.session.list_tools()
        tools: List[Tool] = []
        for item in tools_response:
            if hasattr(item, "name") and hasattr(item, "inputSchema"):
                tools.append(Tool(item.name, getattr(item, "description", ""),
                                  getattr(item, "inputSchema", {}), getattr(item, "title", None)))
            elif isinstance(item, tuple) and item and item[0] == "tools":
                for tool in item[1]:
                    tools.append(Tool(tool.name, getattr(tool, "description", ""),
                                      getattr(tool, "inputSchema", {}), getattr(tool, "title", None)))
        return tools

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        return await self.session.call_tool(tool_name, arguments)

    async def cleanup(self) -> None:
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
            finally:
                self.session = None
