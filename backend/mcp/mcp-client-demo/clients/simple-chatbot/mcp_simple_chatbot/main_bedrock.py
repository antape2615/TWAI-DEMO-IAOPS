#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
import re
import shutil
import ast
from contextlib import AsyncExitStack
from typing import Any, Optional, Literal

from dotenv import load_dotenv
import boto3

# MCP client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain (Bedrock)
from pydantic import BaseModel, Field
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser

MCP_DEBUG_CODE = "0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

#----------------------------------------
# Intention Schema
#----------------------------------------
class IntentEnvelope(BaseModel):
    intent: Literal["diagram", "text", "both", "neither"] = Field(..., description="Qué quiere el usuario")
    confidence: float = Field(..., ge=0, le=1)
    rationale: Optional[str] = Field(None, description="Por qué decidió eso (breve)")

# ---------------------------------------
# Config
# ---------------------------------------
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


# ---------------------------------------
# Tool metadata wrapper
# ---------------------------------------
class Tool:
    def __init__(self, name: str, description: str, input_schema: dict[str, Any], title: Optional[str] = None) -> None:
        self.name = name
        self.title = title
        self.description = description
        self.input_schema = input_schema

    def format_for_llm(self) -> str:
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = f"- {param_name}: {param_info.get('description', 'No description')}"
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)
        out = f"Tool: {self.name}\n"
        if self.title:
            out += f"User-readable title: {self.title}\n"
        out += f"Description: {self.description}\nArguments:\n" + "\n".join(args_desc) + "\n"
        return out


# ---------------------------------------
# MCP Server wrapper
# ---------------------------------------
class Server:
    """Manages MCP server connections and tool execution."""
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        cmd_cfg = self.config.get("command")
        command = shutil.which("npx") if cmd_cfg == "npx" else cmd_cfg
        if not command:
            raise ValueError(f"[{self.name}] Invalid 'command' in servers_config.json")
        server_params = StdioServerParameters(
            command=command,
            args=self.config.get("args", []),
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

    async def list_tools(self) -> list[Tool]:
        if not self.session:
            return []
        tools_response = await self.session.list_tools()
        tools: list[Tool] = []
        # FastMCP responde con objetos con atributos o con tuplas ("tools", [...])
        for item in tools_response:
            if hasattr(item, "name") and hasattr(item, "inputSchema"):
                tools.append(
                    Tool(
                        item.name,
                        getattr(item, "description", ""),
                        getattr(item, "inputSchema", {}),
                        getattr(item, "title", None),
                    )
                )
            elif isinstance(item, tuple) and item and item[0] == "tools":
                for tool in item[1]:
                    tools.append(
                        Tool(
                            tool.name,
                            getattr(tool, "description", ""),
                            getattr(tool, "inputSchema", {}),
                            getattr(tool, "title", None),
                        )
                    )
        return tools

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        logging.info(f"Executing {tool_name}...")
        return await self.session.call_tool(tool_name, arguments)

    async def cleanup(self) -> None:
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")
            finally:
                self.session = None


# ---------------------------------------
# LLM (LangChain + Bedrock) con JSON forzado
# ---------------------------------------
class DecisionEnvelope(BaseModel):
    decision: Literal["tool", "answer"] = Field(..., description="Elige 'tool' o 'answer'")
    tool: Optional[str] = Field(None, description="Nombre de la herramienta a invocar (p.ej. 'generate_diagram')")
    arguments: dict = Field(default_factory=dict, description="Argumentos para la herramienta")
    answer: Optional[str] = Field(None, description="Respuesta en texto libre cuando decision='answer'")
    explanation: Optional[str] = Field(None, description="Explicación breve para el usuario sobre lo generado y el archivo")

# ---- Prompts ----
SYSTEM_PROMPT_BASE = r"""
Eres un generador de **código Python** para el “AWS Diagram MCP Server” (usa la librería `diagrams`).

OBJETIVO:
Devuelve **solo JSON válido** (sin backticks) que invoque la tool `generate_diagram` con un único bloque Python en `arguments.code`. El bloque debe **empezar EXACTAMENTE** con:
with Diagram("<título corto, sin comillas dobles internas>", show=False):

REGLAS DURO-ESTRUCTURALES:
1) **Prohibido** todo `import`. El runtime ya importa `Diagram`, `Cluster` y los nodos.
2) Usa **sangría de 4 espacios**.
3) Para agrupar, **siempre**: `with Cluster("…"):`
   - Nunca `Cluster("…")` sin `with`.
   - Nunca asignar `Cluster` a variables.
4) Debe haber **≥1 conexión** con `>>` dentro del bloque `Diagram`.
5) Máximo **35 nodos** y **60 conexiones** por diagrama (evita timeouts). Prioriza lo esencial.
6) No uses bucles, recursión ni generación de listas por comprensión para crear nodos.
7) Puedes usar `Edge(...)` con kwargs (`label`, `style`, etc.) con moderación.

NOMBRES VÁLIDOS (ejemplos frecuentes):
- compute: EC2, Lambda, ECS, EKS, Batch
- network: APIGateway, ELB, Route53, InternetGateway, NATGateway, VPC, PublicSubnet, PrivateSubnet, RouteTable
- storage: S3, EFS
- database/analytics: RDS, Dynamodb, Redshift
- security: Cognito, WAF, NetworkFirewall, SecretsManager, KMS
- integration: SQS, SNS, Eventbridge, StepFunctions
- observability: Cloudwatch

MAPEO DE ERRORES COMUNES (usa exactamente la **derecha**):
- `DynamoDB`, `DynamoDb`, `DynamoDBTable`  → **Dynamodb**
- `CognitoUserPools`, `CognitoIdp`         → **Cognito**
- `SecurityGroup` (no existe)              → **NetworkFirewall** o **WAF** con label "SG"
- `ALB`                                    → **ELB**
- `EventBridge`                            → **Eventbridge**

PATRONES A EVITAR:
- No crear variables para `Cluster`.
- No colocar texto explicativo ni comentarios en el bloque de código.
- No repetir 20+ recursos idénticos; usa 2–3 como muestra y etiquetas claras.

METADATOS DEL DIAGRAMA:
- El servidor inyectará `filename`, no lo agregues tú.
- El `title` debe ser corto, sin comillas dobles internas, p. ej.: `Arquitectura serverless con Cognito`.

FORMATO DE RESPUESTA (JSON **solo**):
{
  "decision": "tool",
  "tool": "generate_diagram",
  "arguments": {
    "code": "<bloque Python único QUE EMPIEZA con 'with Diagram(' y cumple TODAS las reglas>",
    "filename": "<nombre-kebab-case-sin-.png>"
  },
  "explanation": "Breve texto en español indicando qué representa el diagrama y el nombre de archivo."
}

EJEMPLO DE BLOQUE CORTO Y VÁLIDO (usa clases correctas):
with Diagram("Arquitectura serverless con Cognito", show=False):
    with Cluster("Front"):
        api = APIGateway("API")
    with Cluster("AuthN/Z"):
        auth = Cognito("Cognito")
    with Cluster("Lógica"):
        fn = Lambda("Functions")
        bus = Eventbridge("Event bus")
    with Cluster("Datos"):
        db = Dynamodb("Tabla")
        bucket = S3("Assets")
    api >> auth >> fn
    fn >> db
    fn >> bucket
    fn >> bus

"""

CHAT_SYSTEM = r"""
Eres un asistente útil y conciso. Responde en el mismo idioma del usuario (por defecto, español).
- Sé claro y directo.
- Si el usuario pide un diagrama/arquitectura visual, entonces genera el JSON requerido por la herramienta.
- Si NO piden diagrama, responde normalmente en texto.
"""

INTENT_PROMPT = """
Eres un clasificador de intención. Devuelve SOLO JSON válido.

INTENCIONES:
- "diagram": el usuario pide explícitamente un diagrama/gráfico/visualización de arquitectura (p.ej., "dibuja", "haz un diagrama", "ilustra", "visualiza").
- "text": el usuario pide explicación, opinión, guía o lista; no pide diagrama.
- "both": el usuario quiere explicación y además diagrama.
- "neither": irreconocible.

REGLAS:
- No inventes diagramas si el usuario no los pide.
- Si hay duda razonable, prefiere "text".
- Responde SOLO JSON con: { "intent": "...", "confidence": 0.0-1.0, "rationale": "..." }

EJEMPLOS:
Q: "Genera un diagrama de AWS con Cognito y API Gateway."
A: {"intent":"diagram","confidence":0.98,"rationale":"Pide explícitamente un diagrama"}

Q: "¿Qué servicios de AWS recomiendas para una app web?"
A: {"intent":"text","confidence":0.93,"rationale":"Pide recomendación, no diagrama"}

Q: "Explícame la arquitectura y, si puedes, dibújala."
A: {"intent":"both","confidence":0.87,"rationale":"Pide explicación y dibujo"}

Q: "hola"
A: {"intent":"text","confidence":0.6,"rationale":"Conversación general"}

Ahora clasifica:
Q: {consulta}
A:
"""


class LLMClient:
    def __init__(self, model_id=None, region=None):
        self.model_id = model_id or os.getenv("BEDROCK_MODEL")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        self._model = ChatBedrock(
            client=bedrock_runtime,
            model_id=self.model_id,
            temperature=0.2,
            max_tokens=3000,
        )
        self._parser = PydanticOutputParser(pydantic_object=DecisionEnvelope)
        self._str_parser = StrOutputParser()

    def classify_intent(self, last_user: str) -> IntentEnvelope:
        parser = PydanticOutputParser(pydantic_object=IntentEnvelope)
        prompt = INTENT_PROMPT.replace("{consulta}", last_user.strip())
        msgs = [SystemMessage(content="Eres un modelo estricto. Devuelve solo JSON."), HumanMessage(content=prompt)]
        raw = StrOutputParser().invoke(self._model.invoke(msgs))
        try:
            return parser.parse(raw)
        except Exception:
            # Fallback conservador
            return IntentEnvelope(intent="text", confidence=0.5, rationale="Fallback por parseo")
        
    def _to_lc_messages(self, messages: list[dict[str, str]]):
        """Convierte dicts de mensajes a objetos de LangChain."""
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

    def get_response(self, messages: list[dict[str, str]]) -> str:
        # Detectar intención de diagrama
        last_user = ""
        # se carga el último mensaje del usuario
        for m in reversed(messages):
            if (m.get("role") or "").lower() == "user":
                last_user = (m.get("content") or "").lower()
                break
        
        intent_env = self.classify_intent(last_user.lower())

        lc_msgs = self._to_lc_messages(messages)
        non_system_msgs = [m for m in lc_msgs if not isinstance(m, SystemMessage)]

        # Un SOLO SystemMessage al inicio
        if intent_env.intent in ["diagram", "both"]:
            system_content = SYSTEM_PROMPT_BASE.strip()
            call_msgs = [SystemMessage(content=system_content)] + non_system_msgs
        else:
            call_msgs = [SystemMessage(content=CHAT_SYSTEM.strip())] + non_system_msgs

        raw = self._str_parser.invoke(self._model.invoke(call_msgs))
        # Intentar parsear a nuestro sobre
        try:
            env = self._parser.parse(raw)
        except Exception:
            # Si no es JSON válido del esquema, tratarlo como respuesta de chat normal
            env = DecisionEnvelope(decision="answer", answer=raw)
        return env.model_dump_json()


# ---------------------------------------
# Normalizado + validación (alineado al server)
# ---------------------------------------
def ensure_trailing_newline(s: str) -> str:
    return s if s.endswith("\n") else (s + "\n")

def soften_llm_text(code: str) -> str:
    code = re.sub(r"^```(?:python|json)?\s*|\s*```$", "", code.strip(), flags=re.IGNORECASE | re.DOTALL)
    code = (code.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'"))
    code = code.replace("\r\n", "\n").replace(" \\\n", " ").replace("\\\n", " ").replace("\r", "\n")
    for zw in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        code = code.replace(zw, "")
    return ensure_trailing_newline(code)

IMPORT_LINE_RE = re.compile(r"^\s*(?:from\s+\S+\s+import\s+.*|import\s+.+)$", re.MULTILINE)

def _strip_all_imports(code: str) -> str:
    return IMPORT_LINE_RE.sub("", code)

def _fix_cluster_assignment(code: str) -> str:
    """
    Convierte 'vpc = Cluster("X")' (línea sola) en 'with Cluster("X"):' y
    elimina luego posibles 'with vpc:'.
    """
    pattern = re.compile(r"^(?P<i>\s*)(?P<v>[A-Za-z_]\w*)\s*=\s*Cluster\((?P<a>[^)]*)\)\s*$", re.MULTILINE)
    aliases: list[str] = []

    def repl(m: re.Match) -> str:
        aliases.append(m.group("v"))
        return f"{m.group('i')}with Cluster({m.group('a')}):"

    code = pattern.sub(repl, code)
    for v in set(aliases):
        code = re.sub(rf"^\s*with\s+{re.escape(v)}\s*:\s*$", "", code, flags=re.MULTILINE)
    return code

def _ensure_with_colons(code: str) -> str:
    """
    Asegura que las líneas 'with Diagram(...)' y 'with Cluster(...)' terminen con ':'.
    No duplica dos puntos si ya existen.
    """
    def add_colon(match: re.Match) -> str:
        lead = match.group("lead")
        return lead if lead.rstrip().endswith(":") else (lead.rstrip() + ":")

    # with Diagram(...)
    code = re.sub(
        r'^(?P<lead>\s*with\s+Diagram\([^\n]*\))\s*:?\s*$',
        add_colon,
        code,
        flags=re.MULTILINE
    )
    # with Cluster(...)
    code = re.sub(
        r'^(?P<lead>\s*with\s+Cluster\([^\n]*\))\s*:?\s*$',
        add_colon,
        code,
        flags=re.MULTILINE
    )
    return code

def normalize_code_for_server(raw_code: str) -> str:
    code = soften_llm_text(raw_code)
    code = _strip_all_imports(code)
    code = _fix_cluster_assignment(code)
    code = _ensure_with_colons(code)
    return ensure_trailing_newline(code)

def _has_with_diagram(code: str) -> bool:
    return "with Diagram(" in code

def _has_rshift(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
            return True
    return False

def _imports_present(code: str) -> bool:
    return bool(IMPORT_LINE_RE.search(code))

def validate_for_server(code: str) -> tuple[bool, list[str]]:
    errs = []
    if not code.strip():
        errs.append("Código vacío.")
    if not _has_with_diagram(code):
        errs.append("Falta el bloque 'with Diagram(...)'.")
    if not _has_rshift(code):
        errs.append("No hay conexiones '>>'.")
    if _imports_present(code):
        errs.append("No se permiten imports en este servidor.")
    try:
        ast.parse(code)
    except SyntaxError as e:
        errs.append(f"SyntaxError: {e}")
    return (len(errs) == 0), errs


_DIAGRAM_RE = re.compile(
    r'^(?P<indent>\s*)with\s+Diagram\((?P<inside>.*?)\)\s*:',
    flags=re.MULTILINE | re.DOTALL
)

def inject_filename_into_diagram(code: str, abs_no_ext_filename: str) -> str:
    """
    Inserta o reescribe filename="<ABSOLUTO_SIN_.png>" dentro de Diagram(...).
    """
    def _repl(m: re.Match) -> str:
        indent = m.group("indent")
        inside = m.group("inside")

        # Reescribe título para evitar que otros parsers deriven nombres raros del title
        # (opcional, no afecta el archivo final porque filename manda)
        inside = re.sub(
            r'^(\s*)"([^"]+)"',
            lambda mm: f'{mm.group(1)}"{re.sub(r"[(),]", " ", mm.group(2))}"',
            inside,
            count=1
        )

        if re.search(r'\bfilename\s*=', inside):
            inside = re.sub(r'\bfilename\s*=\s*"[^"]*"', f'filename="{abs_no_ext_filename}"', inside)
        else:
            if inside.strip().endswith(","):
                inside = f'{inside} filename="{abs_no_ext_filename}"'
            else:
                inside = f'{inside}, filename="{abs_no_ext_filename}"'
        return f'{indent}with Diagram({inside}):'

    return _DIAGRAM_RE.sub(_repl, code, count=1)


# ---------------------------------------
# Orquestador
# ---------------------------------------
class ChatSession:
    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        self.servers = servers
        self.llm_client = llm_client

    async def _prewarm_aws_diagram_server(self, server: Server) -> None:
        """ Ejecuta las herramientas previas como listra los iconos y ejemplos (no bloqueante). """
        try:
            logging.info("Executing get_diagram_examples...")
            await server.execute_tool("get_diagram_examples", {"diagram_type": "aws"})
        except Exception as e:
            logging.info("get_diagram_examples error (no bloqueante): %s", e)

        try:
            logging.info("Executing list_icons...")
            res = await server.execute_tool("list_icons", {"provider_filter": "aws"})
            providers = 0
            services = 0
            icons = 0
            text_blob = None
            if hasattr(res, "content"):
                for c in getattr(res, "content", []):
                    if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                        text_blob = c.text
                        break
            if isinstance(text_blob, str):
                try:
                    data = json.loads(text_blob)
                    providers = len(data.get("providers", [])) if isinstance(data.get("providers"), list) else 1
                    if isinstance(data, dict) and "aws" in data and isinstance(data["aws"], dict):
                        for _, lst in data["aws"].items():
                            services += 1
                            if isinstance(lst, list):
                                icons += len(lst)
                except Exception:
                    pass
        except Exception as e:
            logging.info("list_icons error (no bloqueante): %s", e)

    async def cleanup_servers(self) -> None:
        for server in reversed(self.servers):
            try:
                await server.cleanup()
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str, messages: list[dict[str, str]]) -> dict:
        def _clean_json_string(json_string: str) -> str:
            pattern = r"^```(?:\s*json)?\s*(.*?)\s*```$"
            return re.sub(pattern, r"\1", json_string, flags=re.DOTALL | re.IGNORECASE).strip()

        try:
            envelope = json.loads(_clean_json_string(llm_response))
            decision = envelope.get("decision")

            # ───────────────────────────────────────────────────────────────────
            # Modo "answer": chat normal (texto)
            # ───────────────────────────────────────────────────────────────────
            if decision == "answer":
                answer = envelope.get("answer") or "Entendido."
                return {"mode": "answer", "text": answer}

            # ───────────────────────────────────────────────────────────────────
            # Modo "tool": ejecutar herramienta
            # ───────────────────────────────────────────────────────────────────
            elif decision == "tool":
                tool_name = envelope.get("tool")
                tool_args = envelope.get("arguments", {}) or {}
                if not tool_name:
                    return {"mode": "answer", "text": "No tool specified."}

                # Pre-normalización/validación cuando es generate_diagram
                if tool_name == "generate_diagram":
                    raw_code = tool_args.get("code", "")
                    filename = tool_args.get("filename") or "diagram"

                    # 1) Directorio del main (source path) y workspace del server
                    try:
                        source_dir = os.path.dirname(os.path.abspath(__file__))
                    except NameError:
                        # Fallback si __file__ no está disponible (entorno interactivo)
                        source_dir = os.getcwd()
                    workspace_dir = source_dir

                    # 2) Ruta ABSOLUTA (sin .png) donde queremos el PNG final
                    final_abs_no_ext = os.path.join(source_dir, filename)

                    # 3) Normaliza + inyecta filename dentro de Diagram(...)
                    code = normalize_code_for_server(raw_code)
                    code = inject_filename_into_diagram(code, final_abs_no_ext)

                    # 4) Validación
                    ok, errs = validate_for_server(code)
                    if MCP_DEBUG_CODE == 1:
                        logging.info("Código para tool (AWS server, post-normalizado):\n%s", code)
                    if not ok:
                        return {
                            "mode": "answer",
                            "text": "No se ejecutó la herramienta. El código no pasó la validación:\n- " + "\n- ".join(errs),
                        }

                    # 5) Armar argumentos finales para el server
                    tool_args = {
                        "code": code,
                        "filename": filename,     # compat con server; pero Diagram ya escribe en final_abs_no_ext
                        "workspace_dir": workspace_dir,
                        "timeout": 120,
                    }
                # Buscar un servidor que tenga la tool
                for server in self.servers:
                    tools = await server.list_tools()
                    if any(t.name == tool_name for t in tools):
                        result = await server.execute_tool(tool_name, tool_args)

                        # ── Post-proceso y mensaje humano breve
                        try:
                            text_blob = None
                            if hasattr(result, "content"):
                                for c in getattr(result, "content", []):
                                    if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                                        text_blob = c.text
                                        break

                            # Payload JSON estándar esperado del aws-diagram-mcp-server
                            if isinstance(text_blob, str) and text_blob.strip().startswith("{"):
                                payload = json.loads(text_blob)
                                status = payload.get("status")
                                server_msg = payload.get("message")

                                # Aceptar path o paths, normalizar file:// y elegir existente
                                gen_paths = []
                                if isinstance(payload.get("paths"), list) and payload["paths"]:
                                    gen_paths = payload["paths"]
                                elif isinstance(payload.get("path"), str):
                                    gen_paths = [payload["path"]]

                                norm_paths = []
                                for p in gen_paths:
                                    p = p.strip()
                                    if p.startswith("file://"):
                                        p = p[7:]
                                    norm_paths.append(p)

                                # Ruta esperada si el server no devuelve nada útil
                                expected_png = os.path.join(source_dir, f"{(tool_args.get('filename') or 'diagram')}.png")
                                src_path = next((p for p in norm_paths if os.path.exists(p)), None) or expected_png
                                
                                # Limpiezas opcionales de residuos en el source dir
                                try:
                                    gd_path = os.path.join(source_dir, "generated-diagrams",
                                                           f"{(tool_args.get('filename') or 'diagram')}.png")
                                    if os.path.exists(gd_path) and os.path.abspath(gd_path) != os.path.abspath(src_path):
                                        os.remove(gd_path)
                                    weird = os.path.join(source_dir,
                                                         f"{(tool_args.get('filename') or 'diagram')}',_show=false).png")
                                    if os.path.exists(weird) and os.path.abspath(weird) != os.path.abspath(src_path):
                                        os.remove(weird)
                                except Exception:
                                    pass
                                if status == "success" and os.path.exists(src_path):
                                    llm_explanation = envelope.get("explanation") or ""
                                    user_friendly_text = (llm_explanation.strip() or
                                                          f"Diagrama generado: {(tool_args.get('filename') or 'diagram')}.png.")
                                    user_friendly_text += f"\nArchivo generado exitosamente"
                                    return {"mode": "tool", "text": user_friendly_text}
                                return {
                                    "mode": "answer",
                                    "text": f"No se generó el diagrama. Mensaje del servidor: {server_msg or 'Error desconocido.'}",
                                }
                            # Si la tool no devolvió JSON estándar
                            short_desc = f"Herramienta ejecutada. Respuesta parcial: {str(result)[:200]}"
                            return {"mode": "tool", "text": short_desc}
                        except Exception as ex:
                            logging.exception("Post-process error")
                            return {"mode": "answer", "text": f"Error procesando el resultado del diagrama: {ex}"}
                # Ningún servidor tenía esa tool
                return {"mode": "answer", "text": "No se encontró un servidor con esa herramienta."}
            # Si el contenido del modelo no es JSON o no calza con el esquema
            return {"mode": "raw", "text": llm_response}
    
        except json.JSONDecodeError:
            # Devolver crudo si llegó algo no parseable
            return {"mode": "raw", "text": llm_response}

    async def start(self) -> None:
        try:
            # Inicializa servers
            alive = []
            server_errors = []
            for server in self.servers:
                try:
                    await server.initialize()
                    if server.session:
                        alive.append(server)
                except Exception as e:
                    server_errors.append((server.name, str(e)))
            if not alive:
                logging.error("No MCP servers available.")
                if server_errors:
                    for nm, err in server_errors:
                        logging.error("Server '%s' error: %s", nm, err)
                return
            self.servers = alive

            # Precalienta si existe aws-diagram
            for server in self.servers:
                """ Preejecución de herrmainetas de los servidores"""
                if server.name.endswith("aws-diagram-mcp-server"):
                    await self._prewarm_aws_diagram_server(server)

            messages: list[dict[str, str]] = []

            while True:
                try:
                    user_input = input("You: ")
                    if user_input in ["exit", "quit", "salir", "q", "x"]:
                        logging.info("Exiting...")
                        break
                    if not user_input:
                        continue

                    messages.append({"role": "user", "content": user_input})

                    llm_response = self.llm_client.get_response(messages)
                    out = await self.process_llm_response(llm_response, messages)

                    if out["mode"] == "answer":
                        print("Assistant (answer): ", out["text"])
                        messages.append({"role": "assistant", "content": out["text"]})
                    elif out["mode"] == "tool":
                        print("\nAssistant (tool): ", out["text"])
                        messages.append({"role": "assistant", "content": out["text"]})
                    else:
                        messages.append({"role": "assistant", "content": out["text"]})
                except KeyboardInterrupt:
                    logging.info("\nExiting...")
                    break
        finally:
            await self.cleanup_servers()


# ---------------------------------------
# Entrypoint
# ---------------------------------------
async def main() -> None:
    config = Configuration()
    server_config = config.load_config("servers_config.json")
    servers = [Server(name, srv_config) for name, srv_config in server_config.get("mcpServers", {}).items()]
    llm_client = LLMClient()
    chat_session = ChatSession(servers, llm_client)
    await chat_session.start()

if __name__ == "__main__":
    asyncio.run(main())