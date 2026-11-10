import ast
from pathlib import Path
from typing import Dict, Any, List

def parse_python_file(file_path: str) -> Dict[str, Any]:
    """Parses a Python file using AST to extract imports, classes, functions, and docstrings."""
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".py":
        return {"error": "Invalid or non-Python file"}

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    try:
        tree = ast.parse(code, filename=str(path))
    except SyntaxError as e:
        return {"error": f"SyntaxError during AST parsing: {e}"}

    imports = []
    functions = []
    classes = []

    for node in ast.iter_child_nodes(tree):
        # Extract Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"name": alias.name, "as": alias.asname})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({"from": module, "name": alias.name, "as": alias.asname})

        # Extract Top-level Functions
        elif isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": [arg.arg for arg in node.args.args],
                "docstring": ast.get_docstring(node)
            })

        # Extract Classes and Method Metadata
        elif isinstance(node, ast.ClassDef):
            class_methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    class_methods.append({
                        "name": item.name,
                        "line": item.lineno,
                        "args": [arg.arg for arg in item.args.args],
                        "docstring": ast.get_docstring(item)
                    })
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "docstring": ast.get_docstring(node),
                "methods": class_methods
            })

    return {
        "file_path": str(path),
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "line_count": len(code.splitlines())
    }