"""
Hook para el MCP Server de CloudFormation (awslabs.cfn-mcp-server).

Herramientas disponibles:
  - create_resource          → crea un recurso via Cloud Control API
  - get_resource             → describe un recurso existente
  - update_resource          → actualiza un recurso con patch
  - delete_resource          → elimina un recurso
  - list_resources           → lista recursos de un TypeName
  - get_resource_schema_information → devuelve el schema CloudFormation del TypeName
  - get_request_status       → estado de una operación asíncrona
  - create_template          → genera template CFN de recursos listados/creados
"""

import json
import logging
from typing import Any, Dict, Tuple

CFN_TOOLS = {
    "create_resource",
    "get_resource",
    "update_resource",
    "delete_resource",
    "list_resources",
    "get_resource_schema_information",
    # "get_request_status" — no está en la versión instalada del cfn-mcp-server;
    #                        el polling se hace via boto3 directamente en session.py
    "create_template",
}


def is_cfn_tool(tool_name: str) -> bool:
    return tool_name in CFN_TOOLS


# Mapeo de nombres legacy (formato CloudControl nativo) → nombres del cfn-mcp-server
_LEGACY_KEY_MAP = {
    "TypeName":      "resource_type",
    "Identifier":    "identifier",
    "DesiredState":  "properties",
    "PatchDocument": "patch_document",
    "RequestToken":  "request_token",
    "TemplateName":  "template_name",
    "Resources":     "resources",
}


def preprocess_cfn_tool(envelope: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Extrae nombre y argumentos del envelope del LLM.
    - Remapea claves legacy (TypeName/DesiredState/...) a los nombres reales
      que usa el cfn-mcp-server (resource_type/properties/...).
    - Serializa 'properties' y 'patch_document' a JSON string cuando son dicts/lists,
      ya que la Cloud Control API los espera como string.
    """
    tool_name = envelope.get("tool", "")
    raw_args = dict(envelope.get("arguments", {}) or {})

    # Remapar claves legacy → nombres del servidor MCP
    args = {}
    for k, v in raw_args.items():
        canonical = _LEGACY_KEY_MAP.get(k, k)
        args[canonical] = v

    # 'properties' debe ser string JSON (Cloud Control API lo exige)
    if tool_name in {"create_resource", "update_resource"}:
        if "properties" in args and isinstance(args["properties"], dict):
            args["properties"] = json.dumps(args["properties"])

    # 'patch_document' también debe ser string JSON (RFC 6902)
    if tool_name == "update_resource":
        if "patch_document" in args and isinstance(args["patch_document"], (dict, list)):
            args["patch_document"] = json.dumps(args["patch_document"])

    return tool_name, args


def postprocess_cfn_result(
    result: Any, tool_name: str
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Procesa el resultado de una herramienta CFN y devuelve
    (éxito: bool, mensaje_markdown: str, datos_raw: dict).
    """
    from utilities.postprocess import extract_text_blob

    raw = extract_text_blob(result) or str(result)
    data: Dict[str, Any] = {}

    if isinstance(raw, str):
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}

    # ─── Formateo por tipo de operación ───────────────────────────────────────

    if tool_name == "create_resource":
        # Formato normalizado del cfn-mcp-server
        status    = data.get("status") or ""
        rt        = data.get("resource_type") or ""
        token     = data.get("request_token") or ""
        is_done   = data.get("is_complete", True)
        ident     = data.get("identifier") or "pendiente"
        # Fallback: formato ProgressEvent legacy
        pe = data.get("ProgressEvent") or {}
        if pe:
            status  = pe.get("OperationStatus", status)
            rt      = pe.get("TypeName", rt)
            ident   = pe.get("Identifier", ident)
            token   = pe.get("RequestToken", token)
            is_done = (status == "SUCCESS")
        # Normalizar data para que el pipeline de polling lo lea
        data["status"]        = status
        data["is_complete"]   = is_done
        data["request_token"] = token
        data.setdefault("resource_type", rt)
        if not is_done:
            msg = (
                f"⏳ **Creación en progreso...**\n"
                f"- Tipo: `{rt}`\n"
                f"- Token: `{token}`"
            )
        elif status in ("SUCCESS", "COMPLETE"):
            msg = (
                f"✅ **Recurso creado exitosamente.**\n"
                f"- Tipo: `{rt}`\n"
                f"- Identificador: `{ident}`"
            )
        else:
            msg = (
                f"**Recurso procesado.** 🔄\n"
                f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:500]}\n```"
            )

    elif tool_name == "list_resources":
        items = data.get("ResourceDescriptions") or []
        count = len(items)
        if count == 0:
            msg = "No se encontraron recursos de ese tipo en la región."
        else:
            lines = [f"- `{r.get('Identifier', '?')}`" for r in items[:20]]
            msg = f"**{count} recurso(s) encontrado(s):**\n" + "\n".join(lines)
            if count > 20:
                msg += f"\n… y {count - 20} más."

    elif tool_name == "get_resource":
        rd = data.get("ResourceDescription") or data
        props_str = json.dumps(rd, indent=2, ensure_ascii=False)
        msg = f"**Detalles del recurso:**\n```json\n{props_str[:2000]}\n```"
        if len(props_str) > 2000:
            msg += "\n*(truncado)*"

    elif tool_name in {"update_resource", "delete_resource"}:
        op_label  = "Actualización" if tool_name == "update_resource" else "Eliminación"
        # Formato normalizado
        status    = data.get("status") or ""
        rt        = data.get("resource_type") or ""
        token     = data.get("request_token") or ""
        is_done   = data.get("is_complete", True)
        ident     = data.get("identifier") or "N/A"
        pe = data.get("ProgressEvent") or {}
        if pe:
            status  = pe.get("OperationStatus", status)
            rt      = pe.get("TypeName", rt)
            ident   = pe.get("Identifier", ident)
            token   = pe.get("RequestToken", token)
            is_done = (status == "SUCCESS")
        data["status"]        = status
        data["is_complete"]   = is_done
        data["request_token"] = token
        data.setdefault("resource_type", rt)
        if not is_done:
            msg = (
                f"⏳ **{op_label} en progreso...**\n"
                f"- Tipo: `{rt}`\n"
                f"- Identificador: `{ident}`\n"
                f"- Token: `{token}`"
            )
        else:
            msg = (
                f"✅ **{op_label} completada.**\n"
                f"- Tipo: `{rt}`\n"
                f"- Identificador: `{ident}`"
            )

    elif tool_name == "get_request_status":
        # ── Extraer status desde todos los posibles formatos ──────────────────
        # 1. Formato normalizado cfn-mcp-server: {status, resource_type, identifier, is_complete}
        # 2. Formato ProgressEvent legacy: {ProgressEvent: {OperationStatus, TypeName, ...}}
        # 3. Formato texto plano / raw si JSON falló
        status  = data.get("status") or data.get("OperationStatus") or ""
        rt      = data.get("resource_type") or data.get("TypeName") or ""
        ident   = data.get("identifier") or data.get("Identifier") or "N/A"
        is_done = data.get("is_complete", False)
        err_msg = data.get("error_message") or data.get("StatusMessage") or ""
        token   = data.get("request_token") or data.get("RequestToken") or ""

        # Fallback ProgressEvent (formato legacy CloudControl)
        pe = data.get("ProgressEvent") or {}
        if pe:
            status  = pe.get("OperationStatus") or status
            rt      = pe.get("TypeName") or rt
            ident   = pe.get("Identifier") or ident
            err_msg = pe.get("StatusMessage") or err_msg
            token   = pe.get("RequestToken") or token

        # Fallback: si el raw no pudo parsearse como JSON, buscar en texto
        if not status and "raw" in data:
            raw_text = data["raw"]
            import re as _re
            m = _re.search(r'OperationStatus["\s:]+([A-Z_]+)', raw_text)
            if m:
                status = m.group(1)
            m2 = _re.search(r'TypeName["\s:]+([\w:]+)', raw_text)
            if m2:
                rt = m2.group(1)
            m3 = _re.search(r'Identifier["\s:]+([\w\-/]+)', raw_text)
            if m3:
                ident = m3.group(1)

        is_done = (status in ("SUCCESS", "COMPLETE")) or is_done

        data["status"]        = status
        data["is_complete"]   = is_done
        data["request_token"] = token
        data.setdefault("resource_type", rt)

        logging.getLogger(__name__).info(
            f"get_request_status parsed: status={status} is_done={is_done} rt={rt} ident={ident}"
        )

        status_emoji = {"SUCCESS": "✅", "FAILED": "❌", "IN_PROGRESS": "⏳"}.get(status, "🔄")
        msg = (
            f"**Estado de la operación:** {status_emoji}\n"
            f"- Tipo: `{rt}`\n"
            f"- Estado: `{status}`\n"
            f"- Identificador: `{ident}`"
        )
        if err_msg:
            msg += f"\n- Mensaje: {err_msg}"
        if is_done and status in ("SUCCESS", "COMPLETE"):
            msg += f"\n\n✅ **Recurso desplegado exitosamente.** Identificador: `{ident}`"

    elif tool_name == "create_template":
        tmpl = (
            data.get("TemplateBody")
            or data.get("template")
            or json.dumps(data, indent=2)
        )
        preview = str(tmpl)[:3000]
        msg = f"**Template CloudFormation generado:** 📄\n```yaml\n{preview}\n```"
        if len(str(tmpl)) > 3000:
            msg += "\n*(template truncado para visualización)*"

    elif tool_name == "get_resource_schema_information":
        schema = data.get("Schema") or data
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        msg = f"**Schema del recurso:**\n```json\n{schema_str[:2500]}\n```"
        if len(schema_str) > 2500:
            msg += "\n*(schema truncado)*"

    else:
        # Fallback genérico
        msg = (
            f"**`{tool_name}` ejecutado.**\n"
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:800]}\n```"
        )

    return True, msg, data
