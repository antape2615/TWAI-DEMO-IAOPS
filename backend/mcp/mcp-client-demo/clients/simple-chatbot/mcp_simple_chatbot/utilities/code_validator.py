import ast

def ensure_trailing_newline(s: str) -> str:
    return s if s.endswith("\n") else (s + "\n")

def has_with_diagram(code: str) -> bool:
    return "with Diagram(" in code

def has_rshift(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
            return True
    return False

def validate_for_server(code: str, imports_present: bool) -> tuple[bool, list[str]]:
    errs = []
    if not code.strip():
        errs.append("Código vacío.")
    if not has_with_diagram(code):
        errs.append("Falta el bloque 'with Diagram(...)'.")
    if not has_rshift(code):
        errs.append("No hay conexiones '>>'.")
    if imports_present:
        errs.append("No se permiten imports en este servidor.")
    try:
        ast.parse(code)
    except SyntaxError as e:
        errs.append(f"SyntaxError: {e}")
    return (len(errs) == 0), errs
