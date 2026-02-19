#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_api.py — FastAPI HTTP server que expone el MCP Chat Session al frontend de IAOPS.

Corre en puerto 8001 (o configurable via MCP_API_PORT env).

Endpoints:
  GET  /api/ai/aws/status          — health check + servidores activos
  POST /api/ai/aws/chat            — procesa un mensaje, devuelve respuesta
  POST /api/ai/aws/reset           — limpia el historial de conversación
  GET  /api/ai/aws/history         — devuelve el historial de una sesión

Gestión de sesiones: cada session_id tiene su propio historial. Las sesiones
son compartidas; los servidores MCP se inicializan una sola vez (singleton).
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ─── Añadir el paquete al path ───────────────────────────────────────────────
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from config import Configuration
from llm.client import LLMClient
from orchestration.session import ChatSession
from servers.base import Server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Modelos HTTP ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    # Pista de modo que el frontend puede enviar para condicionar el LLM
    # "auto" | "diagram" | "infrastructure" | "both"
    mode: Optional[str] = "auto"


class ChatResponse(BaseModel):
    mode: str           # "answer" | "tool" | "raw"
    text: str
    diagram_path: Optional[str] = None
    cfn_data: Optional[Dict[str, Any]] = None
    session_id: str


class ResetResponse(BaseModel):
    status: str
    session_id: str


# ─── Estado global (singleton de servidores MCP) ─────────────────────────────

_global_lock = asyncio.Lock()
_global_session: Optional[ChatSession] = None      # servidores MCP compartidos
_histories: Dict[str, List[Dict[str, str]]] = {}   # historial por session_id
_aws_account_id: Optional[str] = None              # Account ID real de las credenciales


async def _get_or_init_mcp_session() -> ChatSession:
    """Inicializa los servidores MCP una sola vez. Thread-safe."""
    global _global_session, _aws_account_id
    async with _global_lock:
        # Re-inicializar si ningún servidor sigue vivo
        needs_init = (
            _global_session is None
            or not any(s.session for s in _global_session.servers)
        )
        if not needs_init:
            return _global_session

        logger.info("Inicializando servidores MCP...")
        _ = Configuration()

        # Obtener el Account ID real de las credenciales
        if _aws_account_id is None:
            try:
                import boto3 as _boto3
                sts = _boto3.client(
                    "sts",
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    aws_session_token=os.getenv("AWS_SESSION_TOKEN") or None,
                )
                _aws_account_id = sts.get_caller_identity()["Account"]
                logger.info(f"AWS Account ID: {_aws_account_id}")
            except Exception as e:
                logger.warning(f"No se pudo obtener el Account ID: {e}")
        _ = Configuration()

        cfg_path = _HERE / "servers_config.json"
        with open(cfg_path) as f:
            cfg = json.load(f)

        servers = [
            Server(name, conf)
            for name, conf in cfg.get("mcpServers", {}).items()
            if not conf.get("disabled", False)
        ]

        llm_client = LLMClient()
        cs = ChatSession(servers, llm_client)

        alive, errors = [], []
        for s in servers:
            try:
                await s.initialize()
                if s.session:
                    alive.append(s)
                    logger.info(f"  ✅ Servidor '{s.name}' iniciado")
            except Exception as e:
                errors.append((s.name, str(e)))
                logger.warning(f"  ❌ Servidor '{s.name}' falló: {e}")

        if not alive:
            raise RuntimeError(
                "No hay servidores MCP disponibles. "
                + "; ".join(f"{n}: {e}" for n, e in errors)
            )

        cs.servers = alive
        await cs._prewarm_servers()
        _global_session = cs
        logger.info(f"MCP Session lista con {len(alive)} servidor(es).")
        return _global_session


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio: pre-inicializar para reducir latencia en primer request
    try:
        await _get_or_init_mcp_session()
    except Exception as e:
        logger.warning(f"Pre-init MCP falló (se reintentará en primer request): {e}")
    yield
    # Apagado: limpiar conexiones MCP
    if _global_session:
        await _global_session.cleanup_servers()
        logger.info("MCP Session cerrada.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IAOPS MCP API",
    description="Puente HTTP entre el frontend IAOPS y los servidores MCP de AWS",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

MODE_HINTS = {
    "diagram":        "[MODO: Solo genera el diagrama visual, NO crear recursos reales]",
    "infrastructure": "[MODO: Crear/gestionar recursos reales en AWS via CloudFormation API]",
    "both":           "[MODO: Genera DIAGRAMA y también CREA los recursos reales en AWS]",
}


def _get_history(session_id: str) -> List[Dict[str, str]]:
    if session_id not in _histories:
        _histories[session_id] = []
    return _histories[session_id]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/ai/aws/status")
async def status():
    """Health check: devuelve estado de los servidores MCP."""
    if _global_session is None:
        return {"status": "not_initialized", "servers": []}
    servers_info = [
        {
            "name": s.name,
            "alive": s.session is not None,
        }
        for s in _global_session.servers
    ]
    return {
        "status": "ok",
        "servers": servers_info,
        "active_sessions": len(_histories),
    }


@app.post("/api/ai/aws/reset", response_model=ResetResponse)
async def reset_session(session_id: str = "default"):
    """Limpia el historial de conversación de una sesión."""
    _histories[session_id] = []
    return ResetResponse(status="reset", session_id=session_id)


@app.get("/api/ai/aws/history")
async def get_history(session_id: str = "default"):
    """Devuelve el historial de mensajes de una sesión."""
    return {
        "session_id": session_id,
        "messages": _get_history(session_id),
    }


@app.post("/api/ai/aws/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Procesa un mensaje de usuario a través del LLM + MCP servers.
    Implementa un agentic loop: ejecuta una herramienta por turno,
    pasa el resultado al LLM, repite hasta que decida 'answer' o se
    alcance el máximo de iteraciones.
    """
    session_id = req.session_id or "default"
    history = _get_history(session_id)

    try:
        mcp_session = await _get_or_init_mcp_session()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Servidores MCP no disponibles: {e}")

    # Inyectar hint de modo
    user_content = req.message
    if req.mode and req.mode in MODE_HINTS:
        user_content = f"{MODE_HINTS[req.mode]}\n{req.message}"

    history.append({"role": "user", "content": user_content})

    MAX_ITERATIONS = 8
    accumulated_steps: List[str] = []
    final_out: Dict[str, Any] = {"mode": "answer", "text": ""}

    try:
        for iteration in range(MAX_ITERATIONS):
            llm_response = await mcp_session.llm_client.get_response(history)
            out = await mcp_session.process_llm_response(llm_response, history)
            mode = out.get("mode", "answer")

            # Si el LLM quiere responder directamente → fin del loop
            if mode in ("answer", "raw"):
                if accumulated_steps:
                    steps_summary = "\n\n".join(accumulated_steps)
                    final_text = out.get("text", "").strip()
                    out["text"] = (
                        steps_summary + ("\n\n" + final_text if final_text else "")
                    ).strip()
                final_out = out
                history.append({"role": "assistant", "content": out.get("text", "")})
                break

            # Ejecutó una herramienta → acumular resultado
            step_text = out.get("text", "")
            accumulated_steps.append(step_text)
            logger.info(f"Agentic loop iter={iteration + 1}: herramienta ejecutada")

            # Pasar resultado al LLM para que decida el siguiente paso
            history.append({"role": "assistant", "content": step_text})
            history.append({
                "role": "user",
                "content": (
                    "[RESULTADO DE HERRAMIENTA]\n"
                    + step_text
                    + "\n\nContinúa con el siguiente paso del plan original. "
                    "Si ya completaste todos los pasos, responde con "
                    '{"decision": "answer", "answer": "<resumen en español de todo lo realizado>"}'
                ),
            })
            final_out = out  # por si se agota el límite

        else:
            # Límite de iteraciones alcanzado
            summary = "\n\n".join(accumulated_steps)
            final_out = {
                "mode": "tool",
                "text": summary + "\n\n⚠️ Se completaron todas las operaciones disponibles.",
            }

    except Exception as e:
        logger.exception("Error procesando mensaje")
        history.pop()  # quitar el mensaje de usuario que falló
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        mode=final_out.get("mode", "answer"),
        text=final_out.get("text", ""),
        diagram_path=final_out.get("diagram_path"),
        cfn_data=final_out.get("cfn_data"),
        session_id=session_id,
    )


# ─── SSE helpers ──────────────────────────────────────────────────────────────

def _sse(event: str, data: Any) -> str:
    """Serializa un evento SSE."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


_ASYNC_CFN_TOOLS = {"create_resource", "update_resource", "delete_resource"}
_POLL_INTERVAL   = 6    # segundos entre polls
_POLL_MAX_WAIT   = 600  # 10 minutos máximo


async def _poll_with_sse(
    mcp_session, server, request_token: str, resource_type: str,
    result_holder: Optional[List] = None,
) -> AsyncGenerator[str, None]:
    """
    Hace polling via boto3 emitiendo un SSE 'thinking' por tick.
    Al terminar, emite un 'step' con el resultado final y opcionalmente
    almacena el poll_out en result_holder[0] para que el caller lo use.
    """
    elapsed = 0
    while elapsed < _POLL_MAX_WAIT:
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL
        minutes, secs = divmod(elapsed, 60)
        time_str = f"{minutes}m {secs}s" if minutes else f"{secs}s"
        yield _sse("thinking", {
            "iteration": 0,
            "message": f"⏳ Esperando que `{resource_type}` esté listo... ({time_str})"
        })
        try:
            poll_out = await mcp_session.poll_cfn_token(server, request_token)
            data     = poll_out.get("cfn_data") or {}
            status   = data.get("status", "")
            is_done  = data.get("is_complete", False)
            logger.info(f"CFN poll token={request_token} status={status} elapsed={elapsed}s")
            if is_done or status in ("SUCCESS", "FAILED", "CANCEL_COMPLETE"):
                yield _sse("step", {
                    "iteration": 0,
                    "mode": "tool",
                    "text": poll_out.get("text", ""),
                    "cfn_data": data,
                })
                if result_holder is not None:
                    result_holder.append(poll_out)  # pasar resultado al caller
                return
        except Exception as exc:
            logger.warning(f"CFN poll error (token={request_token}): {exc}")

    timeout_out = {
        "mode": "tool",
        "text": (
            f"⚠️ Tiempo de espera agotado ({_POLL_MAX_WAIT}s).\n"
            f"La operación sigue en progreso. Token: `{request_token}`"
        ),
        "cfn_data": {"request_token": request_token, "status": "IN_PROGRESS", "is_complete": False},
    }
    yield _sse("step", {"iteration": 0, "mode": "tool", **{k: v for k, v in timeout_out.items() if k != "mode"}})
    if result_holder is not None:
        result_holder.append(timeout_out)


async def _agentic_stream(
    mcp_session, history: List[Dict[str, str]], mode_hint: Optional[str]
) -> AsyncGenerator[str, None]:
    """
    Generador async que ejecuta el agentic loop y emite SSE para cada paso:
      thinking  — el LLM está procesando
      step      — una herramienta fue ejecutada (resultado intermedio)
      done      — respuesta final
      error     — error irrecuperable
    """
    MAX_ITERATIONS = 8
    accumulated: List[str] = []

    try:
        for iteration in range(MAX_ITERATIONS):
            yield _sse("thinking", {
                "iteration": iteration + 1,
                "message": "🤔 Analizando..." if iteration == 0 else f"⚙️ Paso {iteration + 1}..."
            })

            llm_response = await mcp_session.llm_client.get_response(history)
            out  = await mcp_session.process_llm_response(llm_response, history)
            mode = out.get("mode", "answer")

            if mode in ("answer", "raw"):
                text = out.get("text", "")
                if accumulated and text.strip():
                    text = "\n\n".join(accumulated) + "\n\n" + text
                elif accumulated:
                    text = "\n\n".join(accumulated)
                history.append({"role": "assistant", "content": text})
                yield _sse("done", {
                    "mode": mode,
                    "text": text,
                    "cfn_data": out.get("cfn_data"),
                })
                return

            # Herramienta ejecutada
            step_text = out.get("text", "")
            cfn_data  = out.get("cfn_data") or {}
            server    = out.get("_server")   # servidor que ejecutó la tool

            # ── Polling SSE para operaciones asíncronas de CFN ────────────────
            token       = cfn_data.get("request_token") or ""
            is_complete = cfn_data.get("is_complete", True)
            res_type    = cfn_data.get("resource_type") or "recurso"

            if token and not is_complete and server:
                # Emitir el "iniciando" inmediatamente
                yield _sse("step", {
                    "iteration": iteration + 1,
                    "mode": "tool",
                    "text": step_text,
                    "cfn_data": cfn_data,
                })
                # Polling visible — result_holder recibe el resultado final
                result_holder: List[Dict] = []
                async for sse_chunk in _poll_with_sse(
                    mcp_session, server, token, res_type, result_holder
                ):
                    yield sse_chunk

                # Construir step_text con el identificador REAL para el historial
                if result_holder:
                    final_poll = result_holder[0]
                    poll_data  = final_poll.get("cfn_data") or {}
                    identifier = poll_data.get("identifier", "") or ""
                    p_status   = poll_data.get("status", "")
                    err_msg    = poll_data.get("error_message", "") or ""
                    if p_status == "FAILED":
                        # Detener el loop: no reintentar, informar el error
                        step_text = (
                            f"❌ La operación sobre `{res_type}` FALLÓ.\n"
                            f"- Error: {err_msg or 'desconocido'}\n\n"
                            "NO reintentes esta operación. Informa el error al usuario."
                        )
                    elif identifier and identifier != "N/A":
                        # Construir referencia al identificador según el tipo de recurso
                        id_label = {
                            "AWS::EC2::VPC":    "VpcId",
                            "AWS::EC2::Subnet": "SubnetId",
                            "AWS::IAM::Role":   "RoleArn (construye como arn:aws:iam::" + (_aws_account_id or "ACCOUNT_ID") + ":role/" + identifier + ")",
                            "AWS::SQS::Queue":  "QueueUrl",
                            "AWS::Lambda::Function": "FunctionName",
                            "AWS::S3::Bucket":  "BucketName",
                        }.get(res_type, "identificador")
                        step_text = (
                            f"Recurso `{res_type}` creado exitosamente.\n"
                            f"- Estado: `{p_status}`\n"
                            f"- {id_label}: `{identifier}`\n\n"
                            f"Usa exactamente ese valor en los siguientes pasos."
                        )
                    else:
                        step_text = final_poll.get("text", f"Operación `{res_type}` estado: {p_status}")
                else:
                    step_text = f"Operación sobre `{res_type}` completada (token: `{token}`)."

                # Si falló, detener el loop agentic aquí
                if result_holder and (result_holder[0].get("cfn_data") or {}).get("status") == "FAILED":
                    # Texto limpio para el usuario (sin instrucciones internas al LLM)
                    poll_data_fail = result_holder[0].get("cfn_data") or {}
                    user_facing_error = (
                        f"❌ La operación sobre `{res_type}` FALLÓ.\n"
                        f"- Error: {poll_data_fail.get('error_message') or 'Ver mensaje de error arriba.'}"
                    )
                    accumulated.append(user_facing_error)
                    # Texto con instrucción para el LLM (lleva el "NO reintentes")
                    llm_fail_text = user_facing_error + "\n\nNO reintentes esta operación."
                    history.append({"role": "assistant", "content": llm_fail_text})
                    # Pedir al LLM que explique el error (una sola vez, sin retry)
                    history.append({"role": "user", "content": (
                        "[OPERACIÓN FALLIDA]\n" + llm_fail_text +
                        "\n\nExplica el error al usuario en español y responde con "
                        '{"decision": "answer", "answer": "<explicación del error>"}'
                    )})
                    continue  # el LLM responderá con answer en la siguiente iteración
            else:
                yield _sse("step", {
                    "iteration": iteration + 1,
                    "mode": "tool",
                    "text": step_text,
                    "cfn_data": cfn_data,
                })

            accumulated.append(step_text)
            history.append({"role": "assistant", "content": step_text})
            # Construir mensaje de continuación enfatizando IDs reales
            continuation_msg = (
                "[RESULTADO DE HERRAMIENTA]\n"
                + step_text
                + "\n\n⚠️ IMPORTANTE: Usa ÚNICAMENTE los identificadores reales mostrados arriba. "
                "NO inventes ni reutilices IDs de recursos anteriores.\n\n"
                "Continúa con el siguiente paso del plan original. "
                "Si ya completaste todos los pasos, responde con "
                '{"decision": "answer", "answer": "<resumen en español de todo lo realizado>"}'
            )
            history.append({"role": "user", "content": continuation_msg})
        summary = "\n\n".join(accumulated)
        yield _sse("done", {
            "mode": "tool",
            "text": summary + "\n\n⚠️ Se completaron todas las operaciones disponibles.",
            "cfn_data": None,
        })

    except Exception as exc:
        logger.exception("Error en agentic stream")
        yield _sse("error", {"message": str(exc)})


@app.post("/api/ai/aws/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Versión SSE del endpoint de chat.
    Emite eventos en tiempo real para cada paso del agentic loop.
    Tipos: thinking | step | done | error
    """
    session_id = req.session_id or "default"
    history = _get_history(session_id)

    try:
        mcp_session = await _get_or_init_mcp_session()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Servidores MCP no disponibles: {e}")

    user_content = req.message
    if req.mode and req.mode in MODE_HINTS:
        user_content = f"{MODE_HINTS[req.mode]}\n{req.message}"

    history.append({"role": "user", "content": user_content})

    # Inyectar contexto del account ID al inicio del historial (una sola vez por sesión)
    if _aws_account_id and not any(
        "[CONTEXTO AWS]" in (m.get("content") or "") for m in history
    ):
        history.insert(0, {
            "role": "system",
            "content": (
                f"[CONTEXTO AWS] Account ID: {_aws_account_id} | "
                f"Región: {os.getenv('AWS_REGION', 'us-east-1')}\n"
                "Usa este Account ID al construir ARNs de IAM roles. "
                "NUNCA uses ARNs de otra cuenta."
            ),
        })

    return StreamingResponse(
        _agentic_stream(mcp_session, history, req.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("MCP_API_PORT", "8001"))
    uvicorn.run(
        "main_api:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
