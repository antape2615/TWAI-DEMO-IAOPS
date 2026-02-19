import json, os

def extract_text_blob(result) -> str | None:
    if hasattr(result, "content"):
        for c in getattr(result, "content", []):
            if getattr(c, "type", None) == "text" and getattr(c, "text", None):
                return c.text
    return None

def normalize_paths(payload: dict) -> list[str]:
    gen_paths = []
    if isinstance(payload.get("paths"), list) and payload["paths"]:
        gen_paths = payload["paths"]
    elif isinstance(payload.get("path"), str):
        gen_paths = [payload["path"]]
    norm = []
    for p in gen_paths:
        p = p.strip()
        if p.startswith("file://"):
            p = p[7:]
        norm.append(p)
    return norm

def choose_existing_path(norm_paths: list[str], fallback: str) -> str:
    for p in norm_paths:
        if os.path.exists(p):
            return p
    return fallback
