import re
from .code_validator import ensure_trailing_newline

IMPORT_LINE_RE = re.compile(r"^\s*(?:from\s+\S+\s+import\s+.*|import\s+.+)$", re.MULTILINE)

def soften_llm_text(code: str) -> str:
    code = re.sub(r"^```(?:python|json)?\s*|\s*```$", "", code.strip(), flags=re.I | re.S)
    code = (code.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'"))
    code = code.replace("\r\n", "\n").replace(" \\\n", " ").replace("\\\n", " ").replace("\r", "\n")
    for zw in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        code = code.replace(zw, "")
    return ensure_trailing_newline(code)

def _strip_all_imports(code: str) -> str:
    return IMPORT_LINE_RE.sub("", code)

def _fix_cluster_assignment(code: str) -> str:
    pat = re.compile(r"^(?P<i>\s*)(?P<v>[A-Za-z_]\w*)\s*=\s*Cluster\((?P<a>[^)]*)\)\s*$", re.M)
    aliases = []
    def repl(m):
        aliases.append(m.group("v"))
        return f"{m.group('i')}with Cluster({m.group('a')}):"
    code = pat.sub(repl, code)
    for v in set(aliases):
        code = re.sub(rf"^\s*with\s+{re.escape(v)}\s*:\s*$", "", code, flags=re.M)
    return code

def _ensure_with_colons(code: str) -> str:
    def add_colon(m): 
        lead = m.group("lead")
        return lead if lead.rstrip().endswith(":") else (lead.rstrip() + ":")
    code = re.sub(r'^(?P<lead>\s*with\s+Diagram\([^\n]*\))\s*:?\s*$', add_colon, code, flags=re.M)
    code = re.sub(r'^(?P<lead>\s*with\s+Cluster\([^\n]*\))\s*:?\s*$', add_colon, code, flags=re.M)
    return code

def normalize_code_for_server(raw_code: str) -> str:
    code = soften_llm_text(raw_code)
    code = _strip_all_imports(code)
    code = _fix_cluster_assignment(code)
    code = _ensure_with_colons(code)
    return ensure_trailing_newline(code)

def imports_present(code: str) -> bool:
    return bool(IMPORT_LINE_RE.search(code))
