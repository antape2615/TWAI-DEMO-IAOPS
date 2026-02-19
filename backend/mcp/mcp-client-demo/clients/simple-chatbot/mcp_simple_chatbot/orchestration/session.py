import os, json, logging, asyncio, re
from typing import List, Dict, Any
from servers.base import Server
from llm.client import LLMClient
from servers.hooks import aws_diagram
from servers.hooks import cfn as cfn_hook


def _extract_first_json(text: str):
    """
    Extrae el primer objeto JSON válido de un texto libre.
    - Primero intenta parsear el texto completo (limpiando código fences).
    - Luego busca el primer '{' balanceado en el texto.
    """
    # 1) Limpiar código fences y probar parse directo
    cleaned = re.sub(r"^```(?:\s*json)?\s*(.*?)\s*```$", r"\1", text, flags=re.S | re.I).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2) Buscar el primer bloque JSON balanceado
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if start is None:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    start = None  # seguir buscando
    return None

class ChatSession:
    def __init__(self, servers: List[Server], llm_client: LLMClient) -> None:
        self.servers = servers
        self.llm_client = llm_client

    async def _prewarm_servers(self):
        for s in self.servers:
            if s.name.endswith("aws-diagram-mcp-server"):
                await aws_diagram.prewarm(s)

    async def cleanup_servers(self) -> None:
        for server in reversed(self.servers):
            try:
                await server.cleanup()
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        try:
            envelope = _extract_first_json(llm_response)
            if envelope is None:
                return {"mode": "raw", "text": llm_response}

            decision = envelope.get("decision")

            if decision == "answer":
                return {"mode": "answer", "text": envelope.get("answer") or "Entendido."}

            if decision == "tool":
                tool_name = envelope.get("tool")
                if not tool_name:
                    return {"mode": "answer", "text": "No tool specified."}

                # ---- Tool pipelines por nombre (extensible)
                pipelines = {
                    "generate_diagram": self._run_generate_diagram_pipeline,
                    **{t: self._run_cfn_tool_pipeline for t in cfn_hook.CFN_TOOLS},
                }
                if tool_name not in pipelines:
                    return {"mode": "answer", "text": f"No hay pipeline para la tool '{tool_name}'."}
                return await pipelines[tool_name](envelope)

            return {"mode": "raw", "text": llm_response}
        except Exception:
            return {"mode": "raw", "text": llm_response}

    async def _run_generate_diagram_pipeline(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        # localizar server compatible
        for server in self.servers:
            tools = await server.list_tools()
            if any(t.name == "generate_diagram" for t in tools):
                try:
                    source_dir = os.path.dirname(os.path.abspath(__file__))
                except NameError:
                    source_dir = os.getcwd()
                source_dir = os.path.abspath(os.path.join(source_dir, ".."))  # raiz del proyecto

                # pre
                expected_png, tool_args, explanation = aws_diagram.preprocess_generate_diagram(envelope, source_dir)

                # exec
                result = await server.execute_tool("generate_diagram", tool_args)

                # post
                ok, msg = aws_diagram.postprocess_generate_diagram(
                    result, expected_png, tool_args["filename"], source_dir
                )
                if ok:
                    if explanation:
                        msg = (explanation.strip() or "") + ("\n" if explanation else "") + msg
                    return {"mode": "tool", "text": msg}
                return {"mode": "answer", "text": msg}

        return {"mode": "answer", "text": "No se encontró un servidor con 'generate_diagram'."}

    async def _run_cfn_tool_pipeline(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta cualquier herramienta del CloudFormation MCP Server."""
        tool_name, tool_args = cfn_hook.preprocess_cfn_tool(envelope)
        explanation = envelope.get("explanation") or ""

        for server in self.servers:
            tools = await server.list_tools()
            if any(t.name == tool_name for t in tools):
                try:
                    logging.info(f"CFN: ejecutando '{tool_name}' en servidor '{server.name}'")
                    result = await server.execute_tool(tool_name, tool_args)
                    ok, msg, data = cfn_hook.postprocess_cfn_result(result, tool_name)
                    if explanation:
                        msg = f"{explanation.strip()}\n\n{msg}"
                    # Devolver siempre inmediatamente; el polling lo maneja el stream SSE
                    return {"mode": "tool", "text": msg, "cfn_data": data, "_server": server}
                except Exception as exc:
                    logging.exception(f"Error ejecutando CFN tool {tool_name}")
                    return {"mode": "answer", "text": f"Error al ejecutar `{tool_name}`: {exc}"}

        return {"mode": "answer", "text": f"No se encontró un servidor con la herramienta '{tool_name}'."}

    async def poll_cfn_token(self, server, request_token: str) -> Dict[str, Any]:
        """
        Consulta el estado de una operación asíncrona de Cloud Control API
        usando boto3 directamente (el tool get_request_status del MCP server
        no está disponible en la versión instalada).
        """
        import asyncio
        import os
        import boto3

        region = os.getenv("AWS_REGION", "us-east-1")
        key_id = os.getenv("AWS_ACCESS_KEY_ID")
        secret = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

        def _boto_poll():
            kwargs: Dict[str, Any] = dict(
                region_name=region,
                aws_access_key_id=key_id,
                aws_secret_access_key=secret,
            )
            if session_token:
                kwargs["aws_session_token"] = session_token
            client = boto3.client("cloudcontrol", **kwargs)
            return client.get_resource_request_status(RequestToken=request_token)

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, _boto_poll)
        except Exception as exc:
            logging.warning(f"boto3 poll error token={request_token}: {exc}")
            data = {"status": "UNKNOWN", "is_complete": False, "request_token": request_token}
            return {"mode": "tool", "text": f"⚠️ Error consultando estado: {exc}", "cfn_data": data}

        pe     = response.get("ProgressEvent", {})
        status = pe.get("OperationStatus", "UNKNOWN")
        rt     = pe.get("TypeName", "")
        ident  = pe.get("Identifier", "N/A")
        err    = pe.get("StatusMessage", "")
        is_done = status in ("SUCCESS", "FAILED", "CANCEL_COMPLETE")

        logging.info(f"boto3 poll token={request_token} status={status} rt={rt} ident={ident}")

        data: Dict[str, Any] = {
            "status":        status,
            "is_complete":   is_done,
            "resource_type": rt,
            "identifier":    ident,
            "request_token": request_token,
            "error_message": err,
        }

        emoji = {"SUCCESS": "✅", "FAILED": "❌", "IN_PROGRESS": "⏳"}.get(status, "🔄")
        msg = (
            f"**Estado de la operación:** {emoji}\n"
            f"- Tipo: `{rt}`\n"
            f"- Estado: `{status}`\n"
            f"- Identificador: `{ident}`"
        )
        if err:
            msg += f"\n- Mensaje: {err}"
        if is_done and status == "SUCCESS":
            msg += f"\n\n✅ **Recurso desplegado exitosamente.** Identificador: `{ident}`"

        return {"mode": "tool", "text": msg, "cfn_data": data}

    async def start(self) -> None:
        try:
            # init servers
            alive, errors = [], []
            for s in self.servers:
                try:
                    await s.initialize()
                    if s.session: alive.append(s)
                except Exception as e:
                    errors.append((s.name, str(e)))
            if not alive:
                for nm, err in errors:
                    logging.error("Server '%s' error: %s", nm, err)
                logging.error("No MCP servers available.")
                return
            self.servers = alive

            await self._prewarm_servers()

            messages: List[Dict[str, str]] = []
            while True:
                try:
                    user_input = input("You: ").strip()
                    # comandos de salida
                    if user_input.lower() in {"exit", "quit", "salir", "q", "x"}:
                        logging.info("Exiting...")
                        break
                    # ignorar entradas vacías
                    if not user_input:
                        continue

                    # agrega el turno del usuario
                    messages.append({"role": "user", "content": user_input})

                    # --- llamada al LLM (async) con manejo de errores ---
                    try:
                        llm_response = await self.llm_client.get_response(messages)  # ahora es async
                    except Exception as e:
                        # Manejo suave de throttling u otros errores del modelo
                        msg = str(e)
                        if "Throttling" in msg or "Too many requests" in msg:
                            friendly = ("Estoy recibiendo muchas solicitudes al modelo ahora mismo. "
                                        "Intentemos de nuevo en unos segundos.")
                            print("Assistant (answer): ", friendly)
                            # No agregamos turno de asistente al historial para no contaminar contexto
                            await asyncio.sleep(1.5)
                            continue
                        else:
                            friendly = f"Ocurrió un error al invocar el modelo: {e}"
                            print("Assistant (answer): ", friendly)
                            # Tampoco añadimos al historial; seguimos el loop
                            continue

                    # --- postproceso normal ---
                    out = await self.process_llm_response(llm_response, messages)

                    if out["mode"] == "answer":
                        print("Assistant (answer): ", out["text"])
                    elif out["mode"] == "tool":
                        print("\nAssistant (tool): ", out["text"])
                    else:
                        print("Assistant (raw): ", out["text"])

                    # agrega la respuesta del asistente al historial
                    messages.append({"role": "assistant", "content": out["text"]})

                except (KeyboardInterrupt, EOFError):
                    logging.info("\nExiting...")
                    break
        finally:
            await self.cleanup_servers()
