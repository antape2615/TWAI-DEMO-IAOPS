import json, os, logging
from typing import Tuple, Dict, Any
from utilities.code_normalizer import normalize_code_for_server, imports_present
from utilities.code_validator import validate_for_server
from utilities.code_injection import inject_filename_into_diagram, resolve_paths
from utilities.common_fixes import apply_common_fixes
from utilities.postprocess import extract_text_blob, normalize_paths, choose_existing_path

async def prewarm(server) -> None:
    try:
        logging.info("Executing get_diagram_examples...")
        await server.execute_tool("get_diagram_examples", {"diagram_type": "aws"})
    except Exception as e:
        logging.info("get_diagram_examples error (no bloqueante): %s", e)
    try:
        logging.info("Executing list_icons...")
        await server.execute_tool("list_icons", {"provider_filter": "aws"})
    except Exception as e:
        logging.info("list_icons error (no bloqueante): %s", e)

def preprocess_generate_diagram(envelope: Dict[str, Any], source_dir: str) -> Tuple[str, Dict[str, Any], str]:
    raw_code = (envelope.get("arguments", {}) or {}).get("code", "")
    filename = (envelope.get("arguments", {}) or {}).get("filename") or "diagram"

    # normalizar + fixes + filename
    code = normalize_code_for_server(raw_code)
    code = apply_common_fixes(code)
    abs_no_ext, expected_png = resolve_paths(filename, source_dir)
    code = inject_filename_into_diagram(code, abs_no_ext)

    ok, errs = validate_for_server(code, imports_present(code))
    if not ok:
        raise ValueError("Validación fallida:\n- " + "\n- ".join(errs))

    tool_args = {
        "code": code,
        "filename": filename,
        "workspace_dir": source_dir,
        "timeout": 120,
    }
    return expected_png, tool_args, (envelope.get("explanation") or "")

def postprocess_generate_diagram(result, expected_png: str, filename: str, source_dir: str) -> Tuple[bool, str]:
    text_blob = extract_text_blob(result)
    if isinstance(text_blob, str) and text_blob.strip().startswith("{"):
        payload = json.loads(text_blob)
        status = payload.get("status")
        server_msg = payload.get("message")
        norm_paths = normalize_paths(payload)
        src_path = choose_existing_path(norm_paths, expected_png)

        # limpieza opcional
        try:
            gd_path = os.path.join(source_dir, "generated-diagrams", f"{filename}.png")
            weird = os.path.join(source_dir, f"{filename}',_show=false).png")
            for p in (gd_path, weird):
                if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(src_path):
                    os.remove(p)
        except Exception:
            pass

        if status == "success" and os.path.exists(src_path):
            return True, f"Diagrama generado: {filename}.png.\nArchivo generado exitosamente"
        return False, f"No se generó el diagrama. Mensaje del servidor: {server_msg or 'Error desconocido.'}"

    # Respuesta no estándar
    return True, f"Herramienta ejecutada. Respuesta parcial: {str(result)[:200]}"
