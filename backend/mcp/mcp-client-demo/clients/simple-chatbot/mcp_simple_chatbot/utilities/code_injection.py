import os, re

_DIAGRAM_RE = re.compile(
    r'^(?P<indent>\s*)with\s+Diagram\((?P<inside>.*?)\)\s*:',
    flags=re.MULTILINE | re.DOTALL
)

def inject_filename_into_diagram(code: str, abs_no_ext_filename: str) -> str:
    def _repl(m):
        indent, inside = m.group("indent"), m.group("inside")
        inside = re.sub(
            r'^(\s*)"([^"]+)"',
            lambda mm: f'{mm.group(1)}"{re.sub(r"[(),]", " ", mm.group(2))}"',
            inside, count=1
        )
        if re.search(r'\bfilename\s*=', inside):
            inside = re.sub(r'\bfilename\s*=\s*"[^"]*"', f'filename="{abs_no_ext_filename}"', inside)
        else:
            inside = f'{inside}, filename="{abs_no_ext_filename}"' if not inside.strip().endswith(",") \
                     else f'{inside} filename="{abs_no_ext_filename}"'
        return f'{indent}with Diagram({inside}):'
    return _DIAGRAM_RE.sub(_repl, code, count=1)

def resolve_paths(filename: str, source_dir: str):
    final_abs_no_ext = os.path.join(source_dir, filename or "diagram")
    expected_png = f"{final_abs_no_ext}.png"
    return final_abs_no_ext, expected_png
