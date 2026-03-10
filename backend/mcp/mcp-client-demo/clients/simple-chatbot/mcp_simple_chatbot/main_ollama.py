#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain (modelo chat vía Ollama)
from typing import Optional, Literal
from pydantic import BaseModel, Field

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# -------------------------------------------------
# Utilidades de lectura de recursos/catálogos/ejemplos
# -------------------------------------------------
def ensure_min_edge(code: str) -> str:
    
    import re
    if ">>" in code:
        return code

    # Clases AWS reconocidas y orden lógico
    classes = ["S3", "Lambda", "SQS", "EC2", "ECS", "APIGateway", "Amplify", "RDS", "Dynamodb"]
    pattern = r"^\s*(?:(%s)\s*\([^)]*\))" % "|".join(classes)
    nodes = []

    for line in code.splitlines():
        m = re.search(pattern, line.strip())
        if m:
            nodes.append(m.group(0))

    # Si hay al menos dos nodos, crea un flujo encadenado
    if len(nodes) >= 2:
        chain = " >> ".join(nodes)
        # Inserta dentro del bloque with Diagram (una vez)
        code = re.sub(
            r"(with\s+Diagram\([^)]*\)\s*:\s*)(\n)",
            r"\1\n    " + chain + r"\2",
            code,
            count=1,
            flags=re.DOTALL,
        )
    return code

async def try_load_resources(session: ClientSession, max_chars: int = 6000) -> str | None:
    """Intenta leer resources (p.ej. catálogo de iconos/servicios). Devuelve texto resumido o None."""
    try:
        resources = await session.list_resources()
        if not resources:
            return None

        targets = [
            r for r in resources
            if any(k in (getattr(r, "name", "") + " " + getattr(r, "uri", "")).lower()
                   for k in ["icon", "icons", "service", "services", "catalog"])
        ]

        text_chunks = []
        for r in targets[:3]:
            try:
                data = await session.read_resource(r.uri)
                blob = ""
                if hasattr(data, "contents") and data.contents:
                    for c in data.contents:
                        if getattr(c, "text", None):
                            blob += c.text + "\n"
                elif hasattr(data, "text") and data.text:
                    blob = data.text
                if blob:
                    text_chunks.append(blob)
            except Exception:
                continue

        if not text_chunks:
            return None

        joined = "\n".join(text_chunks)
        return joined[:max_chars]
    except Exception:
        return None


async def try_call_catalog_tools(server: "Server", session: ClientSession, max_items: int = 120) -> str | None:
    """Si hay tools tipo list_icons/list_services/icons/catalog, llámalas y devuelve un resumen."""
    try:
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}
        candidate = None
        for name in ["list_icons", "list_services", "list_catalog", "icons", "catalog"]:
            if name in tool_names:
                candidate = name
                break
        if not candidate:
            return None

        result = await session.call_tool(candidate, {})
        text = ""
        if hasattr(result, "content"):
            for c in getattr(result, "content", []):
                if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                    text += c.text + "\n"

        if not text:
            return None

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        cleaned, seen = [], set()
        for ln in lines:
            if len(ln) > 140:
                continue
            key = ln.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(ln)
            if len(cleaned) >= max_items:
                break

        return "\n".join(cleaned)
    except Exception:
        return None


async def try_call_examples_tool(server: "Server", session: ClientSession, max_chars: int = 6000) -> str | None:
    """Si existe tool de ejemplos (list_examples/get_examples/examples), la usa y devuelve un resumen."""
    try:
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}
        candidate = None
        for name in ["list_examples", "get_examples", "examples", "get_diagram_examples"]:
            if name in tool_names:
                candidate = name
                break
        if not candidate:
            return None

        result = await session.call_tool(candidate, {})
        text = ""
        if hasattr(result, "content"):
            for c in getattr(result, "content", []):
                if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                    text += c.text + "\n"

        if not text:
            return None

        return text[:max_chars]
    except Exception:
        return None


# -------------------------------------------------
# Sanitizadores y normalizadores de código
# -------------------------------------------------
def normalize_indentation(code: str) -> str:
    """Quita indentación común y espacios de encabezado/cola para evitar 'unexpected indent'."""
    import textwrap
    if not code:
        return code
    return textwrap.dedent(code).lstrip("\n").rstrip()


def harden_quotes_and_fences(code: str) -> str:
    """Elimina fences ``` y comillas tipográficas; limpia BOM."""
    import re
    code = code or ""
    code = re.sub(r"^```(?:python)?\s*|\s*```$", "", code.strip(), flags=re.IGNORECASE | re.DOTALL)
    code = code.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    if code and code[0] == "\ufeff":
        code = code[1:]
    return code


def sanitize_known_typos(code: str) -> str:
    """
    Corrige imports mal formateados, elimina Edge(...), normaliza '>>', corrige capitalización,
    y arregla rutas de import comunes (APIGateway, Amplify, etc.). Asegura filename base (sin .png).
    """
    import re
    fixed = code or ""

    # APIGateway: normaliza SIEMPRE a diagrams.aws.network
    fixed = re.sub(
        r"(^|\n)\s*diagrams\.aws\.network\s+import\s+APIGateway",
        "\nfrom diagrams.aws.network import APIGateway",
        fixed
    )
    fixed = fixed.replace("from diagrams.aws.integration import APIGateway", "from diagrams.aws.network import APIGateway")
    fixed = fixed.replace("from diagrams.aws.compute import APIGateway", "from diagrams.aws.network import APIGateway")
    fixed = fixed.replace("from diagrams.aws.apigateway import APIGateway", "from diagrams.aws.network import APIGateway")
    fixed = fixed.replace("import diagrams.aws.network.APIGateway", "from diagrams.aws.network import APIGateway")

    # Amplify mal importado desde desktop -> mobile
    fixed = fixed.replace("from diagrams.aws.desktop import Amplify", "from diagrams.aws.mobile import Amplify")

    # Icono de usuario mal referenciado por ejemplos (general.User)
    fixed = fixed.replace("general.User(", "User(")

    # Edge(...) fuera
    fixed = re.sub(r">>\s*Edge\([^)]*\)\s*>>", " >> ", fixed)
    fixed = re.sub(r"\bEdge\([^)]*\)", "", fixed)
    fixed = re.sub(r">>\s*>>", " >> ", fixed)
    fixed = re.sub(r"with\s+Edge\([^)]*\)\s*:\s*", "", fixed)

    # Capitalización de clases comunes
    fixed = re.sub(r"\bSqs\(", "SQS(", fixed)   # Sqs -> SQS
    fixed = re.sub(r"\bEcs\(", "ECS(", fixed)   # Ecs -> ECS
    fixed = re.sub(r"\bS3Bucket\(", "S3(", fixed)
    fixed = fixed.replace("DynamoDB(", "Dynamodb(")

    # Evita imports inválidos tipo "import diagrams.aws.xxx.YYY"
    fixed = re.sub(r"\n\s*import\s+diagrams\.aws\.[^\n]+", "", fixed)

    # Asegura que filename en el código sea base (sin .png) si apareciera
    fixed = re.sub(r"filename\s*=\s*['\"]([^'\"]+)\.png['\"]", r"filename='\1'", fixed)

    return fixed


def strip_wrappers(code: str) -> str:
    """Deja solo el bloque 'with Diagram(...)' y su cuerpo si existe; de lo contrario devuelve tal cual."""
    import re
    if not code:
        return code
    m = re.search(r"(with\s+Diagram\([^)]*\)\s*:\s*(?:\n|\r\n)(?:[ \t]+.+\n?)+)", code)
    return m.group(1) if m else code


def ensure_diagrams_imports(code: str) -> str:
    missing = []

    if "from diagrams import Diagram" not in code:
        missing.append("from diagrams import Diagram")

    if "Cluster(" in code and "from diagrams import Cluster" not in code:
        missing.append("from diagrams import Cluster")

    if "User(" in code and "from diagrams.onprem.client import User" not in code:
        missing.append("from diagrams.onprem.client import User")

    aws_map = {
        "EC2(": "from diagrams.aws.compute import EC2",
        "ECS(": "from diagrams.aws.compute import ECS",
        "Lambda(": "from diagrams.aws.compute import Lambda",
        "S3(": "from diagrams.aws.storage import S3",
        "SQS(": "from diagrams.aws.integration import SQS",
        "APIGateway(": "from diagrams.aws.network import APIGateway",
        "Amplify(": "from diagrams.aws.mobile import Amplify",
        "Dynamodb(": "from diagrams.aws.database import Dynamodb",
        "RDS(": "from diagrams.aws.database import RDS",
    }
    for token, imp in aws_map.items():
        if token in code and imp not in code:
            missing.append(imp)

    if missing:
        return "\n".join(missing) + "\n\n" + code
    return code


def ensure_diagram_context(code: str, default_title="AWS Diagram", default_filename="aws_diagram") -> str:
    """Si no hay 'with Diagram(...):', lo crea y añade imports mínimos."""
    import re
    if "with Diagram(" in code:
        return code

    header = (
        "from diagrams import Diagram\n"
        "from diagrams.aws.compute import EC2, Lambda\n"
        "from diagrams.aws.integration import SQS\n"
        "from diagrams.aws.storage import S3\n"
    )
    body = (code or "").strip()
    if not body:
        body = "EC2('EC2') >> SQS('Queue') >> Lambda('Lambda') >> S3('Bucket')"

    return (
        header +
        f"\nwith Diagram('{default_title}', show=False, filename='{default_filename}', outformat='png', direction='LR'):\n"
        f"    {body}\n"
    )


def normalize_diagram_args(code: str, base_filename: str) -> str:
    """
    Inserta show=False, filename=..., outformat='png', direction='LR' solo si faltan.
    No repite kwargs (evita 'keyword argument repeated').
    """
    import re
    m = re.search(r"with\s+Diagram\((.*?)\)\s*:", code, flags=re.DOTALL)
    if not m:
        return code

    args_str = m.group(1)
    has_show = re.search(r"\bshow\s*=", args_str) is not None
    has_filename = re.search(r"\bfilename\s*=", args_str) is not None
    has_outformat = re.search(r"\boutformat\s*=", args_str) is not None
    has_direction = re.search(r"\bdirection\s*=", args_str) is not None

    additions = []
    if not has_show:
        additions.append("show=False")
    if not has_filename:
        additions.append(f"filename='{base_filename}'")
    if not has_outformat:
        additions.append("outformat='png'")
    if not has_direction:
        additions.append("direction='LR'")

    if additions:
        new_args = args_str.strip()
        if new_args and not new_args.endswith(","):
            new_args += ", "
        new_args += ", ".join(additions)
        code = code.replace(m.group(0), f"with Diagram({new_args}):")

    return code


# -------------------------------------------------
# Configuración
# -------------------------------------------------
class Configuration:
    def __init__(self) -> None:
        self.load_env()

    @staticmethod
    def load_env() -> None:
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> dict[str, Any]:
        with open(file_path, "r") as f:
            return json.load(f)


# -------------------------------------------------
# MCP Server wrapper
# -------------------------------------------------
class Server:
    """Manages MCP server connections and tool execution."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name: str = name
        self.config: dict[str, Any] = config
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize the server connection."""
        command = shutil.which("npx") if self.config["command"] == "npx" else self.config["command"]
        if command is None:
            raise ValueError("The command must be a valid string and cannot be None.")

        server_params = StdioServerParameters(
            command=command,
            args=self.config["args"],
            env={**os.environ, **self.config.get("env", {})} if self.config.get("env") else None,
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[Any]:
        """List available tools from the server."""
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()
        tools: list[Tool] = []

        # Soporta tanto respuestas directas (objetos) como formatos raros
        for item in tools_response:
            # Caso normal: item ya es un objeto con .name, .description, .inputSchema, .title
            if hasattr(item, "name") and hasattr(item, "inputSchema"):
                tools.append(Tool(item.name, getattr(item, "description", ""), getattr(item, "inputSchema", {}), getattr(item, "title", None)))
            # Caso viejo/tupla
            elif isinstance(item, tuple) and item and item[0] == "tools":
                for tool in item[1]:
                    tools.append(Tool(tool.name, getattr(tool, "description", ""), getattr(tool, "inputSchema", {}), getattr(tool, "title", None)))

        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism."""
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)
                return result
            except Exception as e:
                attempt += 1
                logging.warning(f"Error executing tool: {e}. Attempt {attempt} of {retries}.")
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        title: str | None = None,
    ) -> None:
        self.name: str = name
        self.title: str | None = title
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = f"- {param_name}: {param_info.get('description', 'No description')}"
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        output = f"Tool: {self.name}\n"
        if self.title:
            output += f"User-readable title: {self.title}\n"

        output += f"""Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""
        return output


# -------------------------------------------------
# LLM (Ollama)
# -------------------------------------------------
# -------------------------------------------------
# LLM (LangChain + Ollama Llama 3.1) con JSON forzado y fallback seguro
# -------------------------------------------------

class DecisionEnvelope(BaseModel):
    decision: Literal["tool", "answer"] = Field(..., description="Elige 'tool' o 'answer'")
    tool: Optional[str] = Field(None, description="Nombre de la herramienta a invocar (p.ej. 'generate_diagram')")
    arguments: dict = Field(default_factory=dict, description="Argumentos para la herramienta")
    answer: Optional[str] = Field(None, description="Respuesta en texto libre cuando decision='answer'")

class LLMClient:
    """
    Cliente LLM usando LangChain con ChatOllama (Llama 3.1).
    Siempre retorna un JSON conforme al esquema DecisionEnvelope.
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self.model_name = model
        self.base_url = base_url

        # Sugerido: baja temperatura para obedecer formato, y activa modo JSON de Ollama
        self._model = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.2,
            num_ctx=8192,
            format="json",  # Ollama intentará devolver JSON well-formed
        )

        self._parser = PydanticOutputParser(pydantic_object=DecisionEnvelope)
        self._str_parser = StrOutputParser()

    def _to_lc_messages(self, messages: list[dict[str, str]]):
        lc_msgs = []
        for m in messages:
            role = (m.get("role") or "").lower()
            content = m.get("content", "")
            if role == "system":
                lc_msgs.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_msgs.append(AIMessage(content=content))
            else:
                lc_msgs.append(HumanMessage(content=content))
        return lc_msgs

    def _extract_json(self, text: str) -> str:
        """Recorta fences y extrae el primer objeto {...} si viniera texto de más."""
        import re, json
        s = text.strip()
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            json.loads(s)
            return s
        except Exception:
            m = re.search(r"\{(?:[^{}]|(?R))*\}", s, flags=re.DOTALL)  # objeto JSON de primer nivel
            if m:
                return m.group(0)
            return s
    def get_response(self, messages: list[dict[str, str]]) -> str:
        """
        Devuelve string JSON para que ChatSession lo procese:
        { "decision": "tool"|"answer", "tool": "...", "arguments": {...}, "answer": "..." }
        """
        import json as _json

        # 0) Intent detection en el último mensaje del usuario
        last_user = ""
        for m in reversed(messages):
            if (m.get("role") or "").lower() == "user":
                last_user = (m.get("content") or "").lower()
                break
        diagram_intent = any(k in last_user for k in [
            "diagrama", "diagram", "dibujar", "dibuja", "crear", "crea",
            "generar", "genera", "mostrar", "muestra", "visualizar", "visualiza",
            "representar", "representa", "arquitectura aws"
        ])

        # 1) Pasamos TODO el historial...
        lc_messages = self._to_lc_messages(messages)

        # 2) Guard de formato JSON obligatorio
        format_guard = SystemMessage(content=(
            "ATENCIÓN: Debes responder EXCLUSIVAMENTE con un JSON válido que cumpla este esquema:\n"
            "{\n"
            '  "decision": "tool" | "answer",\n'
            '  "tool": "string opcional",\n'
            '  "arguments": {objeto con argumentos},\n'
            '  "answer": "string opcional"\n'
            "}\n"
            "- Si es charla/duda sin pedir diagrama: usa decision='answer' y completa 'answer'.\n"
            "- Si debes llamar una herramienta: usa decision='tool', especifica 'tool' y 'arguments'.\n"
            "- PROHIBIDO: texto fuera del JSON, markdown o fences."
        ))

        # 3) Si hay intención de diagrama, añadimos un guard más duro
        hard_tool_guard = None
        if diagram_intent:
            hard_tool_guard = SystemMessage(content=(
                "REGLA DE ORO: El usuario ha pedido crear/dibujar/mostrar un diagrama de AWS.\n"
                "Debes responder SOLO con:\n"
                '{ "decision": "tool", "tool": "generate_diagram", '
                '"arguments": { "code": "<bloque Python diagrams válido>", "filename": "aws_diagram.png" } }\n'
                "No devuelvas ejemplos, ni texto explicativo, ni JSON distinto."
            ))

        # 4) Invocamos el modelo (modo JSON) y parseamos con Pydantic
        call_msgs = lc_messages + [format_guard] + ([hard_tool_guard] if hard_tool_guard else [])
        raw = self._str_parser.invoke(self._model.invoke(call_msgs))

        json_text = self._extract_json(raw)
        try:
            env = self._parser.parse(json_text)  # valida contra DecisionEnvelope
        except OutputParserException:
            # Fallback 1: si no cumple, encapsulamos como 'answer'
            env = DecisionEnvelope(decision="answer", answer=raw, arguments={}, tool=None)

        # 5) Coerción post-parse: si hay intención de diagrama pero el modelo dijo 'answer', forzamos tool
        if diagram_intent and env.decision != "tool":
            # Construimos un bloque mínimo y dejamos que tus sanitizadores lo perfeccionen
            base_code = (
                "from diagrams import Diagram\n"
                "from diagrams.aws.mobile import Amplify\n"
                "from diagrams.aws.network import APIGateway\n"
                "from diagrams.aws.compute import Lambda, EC2\n"
                "from diagrams.aws.database import Dynamodb\n"
                "from diagrams.aws.storage import S3\n"
                "from diagrams.aws.integration import SQS\n\n"
                "with Diagram('Arquitectura AWS', show=False, filename='aws_diagram', outformat='png', direction='LR'):\n"
                "    Amplify('App')\n"
                "    APIGateway('API')\n"
                "    Lambda('Backend')\n"
                "    Dynamodb('DB')\n"
                "    S3('Assets')\n"
            )
            env = DecisionEnvelope(
                decision="tool",
                tool="generate_diagram",
                arguments={"code": base_code, "filename": "aws_diagram.png"},
                answer=None
            )

        return env.model_dump_json()

# -------------------------------------------------
# Orquestador de chat
# -------------------------------------------------
class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        self.servers: list[Server] = servers
        self.llm_client: LLMClient = llm_client

    async def cleanup_servers(self) -> None:
        for server in reversed(self.servers):
            try:
                await server.cleanup()
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str, messages: list[dict[str, str]]) -> dict:
        import re as _re

        def _clean_json_string(json_string: str) -> str:
            import re as __re
            pattern = r"^```(?:\s*json)?\s*(.*?)\s*```$"
            return __re.sub(pattern, r"\1", json_string, flags=__re.DOTALL | __re.IGNORECASE).strip()

        try:
            envelope = json.loads(_clean_json_string(llm_response))
            decision = envelope.get("decision")
            if decision == "answer":
                answer = envelope.get("answer") or "Entendido."
                return {"mode": "answer", "text": answer}

            elif decision == "tool":
                tool_name = envelope.get("tool")
                tool_args = envelope.get("arguments", {}) or {}
                if not tool_name:
                    return {"mode": "answer", "text": "No tool specified."}

                for server in self.servers:
                    tools = await server.list_tools()
                    if any(t.name == tool_name for t in tools):
                        # --- Sanitización/normalización del código de diagrams ---
                        if tool_name == "generate_diagram":
                            raw_code = tool_args.get("code", "")

                            # --- Limpiezas robustas ---
                            raw_code = harden_quotes_and_fences(raw_code)     # quita fences y comillas raras
                            raw_code = sanitize_known_typos(raw_code)         # corrige imports y clases incorrectas
                            raw_code = strip_wrappers(raw_code)               # deja solo el bloque con 'with Diagram(...)'
                            raw_code = normalize_indentation(raw_code)        # normaliza indentación

                            # --- Asegura imports y contexto ---
                            fixed_code = ensure_diagrams_imports(raw_code)    # agrega imports faltantes de diagrams
                            fixed_code = ensure_diagram_context(fixed_code)   # agrega 'with Diagram(...)' si falta

                            # --- Configuración de filename/base ---
                            arg_filename = tool_args.get("filename")
                            if arg_filename:
                                base = os.path.splitext(arg_filename)[0]
                            else:
                                base = os.path.expanduser("~/aws_diagram")
                                tool_args["filename"] = "aws_diagram.png"

                            # --- Limpieza y conexión mínima ---
                            fixed_code = "\n".join(ln.rstrip() for ln in fixed_code.splitlines())  # quita espacios al final
                            fixed_code = ensure_min_edge(fixed_code)                               # agrega conexión EC2 >> Lambda si falta

                            # --- Normalización final de argumentos del Diagram ---
                            fixed_code = normalize_diagram_args(fixed_code, base_filename=base)

                            # --- Asigna el código final ---
                            tool_args["code"] = fixed_code

                        # Ejecutar tool
                        result = await server.execute_tool(tool_name, tool_args)
                        
                        # Post-proceso (copiar a ~/Downloads si aplica)
                        import json as _json
                        from pathlib import Path

                        final_msg = "Tool execution result: (no details)"
                        try:
                            text_blob = None
                            if hasattr(result, "content"):
                                for c in getattr(result, "content", []):
                                    if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                                        text_blob = c.text
                                        break

                            if isinstance(text_blob, str) and text_blob.strip().startswith("{"):
                                payload = _json.loads(text_blob)
                                status = payload.get("status")
                                gen_path = payload.get("path")
                                msg = payload.get("message")

                                if status == "success" and gen_path and os.path.exists(gen_path):
                                    src_path = gen_path
                                    if src_path.lower().endswith(".png.png") and os.path.exists(src_path[:-4]):
                                        src_path = src_path[:-4]
                                    elif not(src_path.lower().endswith(".png")):
                                        src_path += ".png"

                                    arg_out = tool_args.get("filename")
                                    out_name = os.path.basename(arg_out) if arg_out else os.path.basename(src_path)

                                    dest_dir = os.path.expanduser("~/Downloads")
                                    os.makedirs(dest_dir, exist_ok=True)
                                    dest_path = str(Path(dest_dir) / out_name)

                                    shutil.copyfile(src_path, dest_path)
                                    final_msg = f"Diagram generated: {dest_path}"
                                else:
                                    final_msg = f"Diagram not generated. Server message: {msg or 'Unknown error'}"
                            else:
                                final_msg = f"Tool returned: {str(result)[:300]}"

                        except Exception as ex:
                            logging.exception("Post-process error")
                            final_msg = f"Post-process error: {ex}"

                        return {"mode": "tool", "text": final_msg}

                return {"mode": "answer", "text": "No server found with tool"}

            return {"mode": "raw", "text": llm_response}

        except json.JSONDecodeError:
            return {"mode": "raw", "text": llm_response}

    async def start(self) -> None:
        """Main chat session handler."""
        try:
            # Inicializa servidores
            for server in self.servers:
                try:
                    await server.initialize()
                except Exception as e:
                    logging.error(f"Failed to initialize server: {e}")
                    await self.cleanup_servers()
                    return

            # Lista todas las tools
            all_tools = []
            for server in self.servers:
                tools = await server.list_tools()
                all_tools.extend(tools)

            tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])

            # Pre-carga catálogo/ejemplos (como hace Claude Desktop)
            catalog_text = None
            examples_text = None
            for server in self.servers:
                if not server.session:
                    continue
                catalog_text = await try_load_resources(server.session)
                if not catalog_text:
                    catalog_text = await try_call_catalog_tools(server, server.session)
                examples_text = await try_call_examples_tool(server, server.session)
                if catalog_text or examples_text:
                    break

            catalog_section = ""
            if catalog_text:
                catalog_section = (
                    "\n\nCATÁLOGO (resumen, solo referencia):\n"
                    + catalog_text[:3000] +
                    "\n\nUsa exactamente estos nombres/clases e imports cuando apliquen."
                )

            examples_section = ""
            if examples_text:
                examples_section = (
                    "\n\nEJEMPLOS (del server):\n"
                    + examples_text[:3000] +
                    "\n\nAdáptalos estrictamente a la librería diagrams (clases e imports válidos)."
                )

            system_message = f"""
            Eres un asistente con acceso a herramientas MCP.

            HERRAMIENTAS DISPONIBLES
            {tools_description}

            REFERENCIAS DEL SERVIDOR (opcional)
            {catalog_section}
            {examples_section}

            REGLA DE DECISIÓN (OBLIGATORIA)
            1) Si el usuario pide CREAR/DIBUJAR/GENERAR/MOSTRAR/VISUALIZAR/REPRESENTAR un diagrama de AWS (o cualquier variación),
            debes responder EXCLUSIVAMENTE con JSON:
            {{
                "decision": "tool",
                "tool": "generate_diagram",
                "arguments": {{
                "code": "<bloque Python válido usando diagrams>",
                "filename": "aws_diagram.png"
                }}
            }}
            - Si no incluyes "filename", el cliente pondrá uno por defecto. 
            - Nunca devuelvas texto fuera del JSON, ni ejemplos, ni comentarios.

            2) Si la petición del usuario es SOLO conversacional (saludo, disponibilidad, duda conceptual, explicación sin pedir un diagrama),
            responde EXCLUSIVAMENTE con JSON:
            {{ "decision": "answer", "answer": "<tu texto conciso>" }}

            DISPARADORES DE INTENCIÓN DE DIAGRAMA (match literal, sin acentos también):
            - "diagrama", "diagram", "dibujar", "dibuja", "crear", "crea", "generar", "genera",
            "mostrar", "muestra", "visualizar", "visualiza", "representar", "representa", "arquitectura aws".
            Si cualquiera de estos aparece, debes usar la herramienta `generate_diagram`.

            FORMATO DE SALIDA (SOLO JSON VÁLIDO)
            - Sin herramienta → {{"decision":"answer","answer":"<texto>"}}
            - Con herramienta → {{"decision":"tool","tool":"generate_diagram","arguments":{{"code":"<python diagrams>","filename":"aws_diagram.png"}}}}
            - PROHIBIDO: texto adicional fuera del JSON, markdown, fences ```...```, explicaciones o ejemplos.

            REGLAS ESTRICTAS PARA `generate_diagram`
            1) Devuelve UN único bloque Python válido que use la librería `diagrams`. No declares funciones ni clases propias.
            2) Imports permitidos (usa solo los necesarios):
            from diagrams import Diagram
            from diagrams import Cluster     # solo si usas Cluster(...)
            from diagrams.aws.compute import Lambda, EC2, ECS
            from diagrams.aws.storage import S3
            from diagrams.aws.integration import SQS
            from diagrams.aws.network import APIGateway
            from diagrams.aws.database import Dynamodb, RDS
            from diagrams.aws.mobile import Amplify
            3) Contexto obligatorio (ajusta el título si aplica):
            with Diagram('Título', show=False, filename='nombre_sin_png', outformat='png', direction='LR'):
                NodoA('...') >> NodoB('...')
            - `filename` NO debe llevar .png; `outformat` ya agrega la extensión.
            4) Conectores:
            - Usa `>>` para todas las conexiones.
            - Si el usuario describe un flujo (p.ej., "S3 activa Lambda, luego SQS y lo consume EC2") conéctalo así:
                S3('...') >> Lambda('...') >> SQS('...') >> EC2('...')
            - Si solo menciona dos nodos, conéctalos A >> B.
            5) Prohibido:
            - Edge(...), provider.service, service(), .instance(), diagrams.aws.services, diagrams.aws.desktop,
                S3Bucket, DynamoDB (usa Dynamodb).
            6) Estilo y sintaxis:
            - Indentación de 4 espacios (sin tabs).
            - Sin paréntesis o comillas sin cerrar; sin comillas tipográficas (“ ” ‘ ’).
            - Cada `with` en su propia línea y finaliza con `:`.
            - Importa solo lo que realmente uses.

            AUTOCOMPROBACIÓN (ANTES DE RESPONDER)
            - ¿La salida es SOLO JSON válido (sin texto extra)?
            - Si "decision":"tool":
            - ¿Existe `with Diagram(` y cierra correctamente?
            - ¿Hay al menos una arista `>>` entre nodos, en el orden solicitado?
            - ¿Imports correctos (APIGateway desde aws.network, Amplify desde aws.mobile, Dynamodb desde aws.database)?
            - ¿`filename` en el código no lleva `.png`?
            - Si "decision":"answer": ¿el usuario NO pidió diagrama?

            EJEMPLOS RÁPIDOS (VÁLIDOS)
            1) Con herramienta (mínimo):
            {{
            "decision": "tool",
            "tool": "generate_diagram",
            "arguments": {{
                "code": "from diagrams import Diagram\\nfrom diagrams.aws.compute import Lambda, EC2\\nwith Diagram('EC2 to Lambda', show=False, filename='aws_diagram', outformat='png', direction='LR'):\\n    EC2('EC2') >> Lambda('Lambda')"
            }}
            }}
            2) Conversacional:
            {{ "decision": "answer", "answer": "¡Listo! Puedo generar un diagrama si me indicas el flujo." }}

            EJEMPLO INVÁLIDO (NO HACER)
            - Devolver explicaciones o JSON con 'examples' en lugar de `decision/tool/arguments`.
            - Mezclar texto fuera del JSON.
            """

            messages = [{"role": "system", "content": system_message}]


            while True:
                try:
                    user_input = input("You: ")
                    if user_input is None:
                        continue
                    user_input = user_input.strip()

                    if not user_input:
                        # solo repite el prompt sin invocar modelo/herramienta
                        continue

                    messages.append({"role": "user", "content": user_input})

                    llm_response = self.llm_client.get_response(messages)
                    out = await self.process_llm_response(llm_response, messages)

                    if out["mode"] == "answer":
                        logging.info("\nAssistant (answer): %s", out["text"])
                        messages.append({"role": "assistant", "content": out["text"]})

                    elif out["mode"] == "tool":
                        logging.info("\nAssistant (tool): %s", out["text"])

                    else:
                        logging.info("\nAssistant (raw): %s", out["text"])
                        messages.append({"role": "assistant", "content": out["text"]})

                except KeyboardInterrupt:
                    logging.info("\nExiting...")
                    break


        finally:
            await self.cleanup_servers()

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------
async def main() -> None:
    """Initialize and run the chat session."""
    config = Configuration()
    server_config = config.load_config("servers_config.json")
    servers = [Server(name, srv_config) for name, srv_config in server_config["mcpServers"].items()]
    # Ajusta el modelo ollama si quieres (ej: "llama3.1:8b-instruct-q5_K_M")
    llm_client = LLMClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b-instruct-q5_K_M")  # puedes usar el modelo que tengas instalado
    chat_session = ChatSession(servers, llm_client)
    await chat_session.start()


if __name__ == "__main__":
    asyncio.run(main())
