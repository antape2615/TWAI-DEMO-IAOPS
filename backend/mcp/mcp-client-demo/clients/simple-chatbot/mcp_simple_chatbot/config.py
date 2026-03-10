import json, os
from dotenv import load_dotenv
from typing import Any, Dict

class Configuration:
    def __init__(self) -> None:
        load_dotenv()

    @staticmethod
    def load_config(path: str) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

MCP_DEBUG_CODE = os.getenv("MCP_DEBUG_CODE", "0")
