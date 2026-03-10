#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio, logging
from config import Configuration
from servers.base import Server
from llm.client import LLMClient
from orchestration.session import ChatSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def main() -> None:
    _ = Configuration()
    import json
    with open("servers_config.json") as f:
        cfg = json.load(f)
    servers = [Server(name, conf) for name, conf in cfg.get("mcpServers", {}).items()]
    chat_session = ChatSession(servers, LLMClient())
    await chat_session.start()

if __name__ == "__main__":
    asyncio.run(main())
