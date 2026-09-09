"""
Documentation vs Implementation Verification Engine (knowledge_agent/doc_verifier.py)
Cross-references claims in documentation (README.md, docs, KNOWLEDGE.md) against
actual source code AST and symbol definitions to surface implementation drift.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set


class DiscrepancyType:
    MISSING_IMPLEMENTATION = "MISSING_IMPLEMENTATION"
    SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH"
    MISSING_ENV_VAR = "MISSING_ENV_VAR"
    UNDOCUMENTED_PUBLIC_API = "UNDOCUMENTED_PUBLIC_API"


COMMON_DOC_STOPWORDS: Set[str] = {
    # Standard Python / JS / common code keywords
    "def", "class", "import", "from", "return", "if", "else", "elif", "for", "while",
    "try", "except", "finally", "with", "as", "async", "await", "lambda", "yield",
    "none", "true", "false", "null", "undefined", "self", "cls", "args", "kwargs",
    "str", "int", "float", "bool", "list", "dict", "set", "tuple", "any", "optional",
    # CLI & Tooling commands
    "git", "pip", "npm", "npx", "python", "python3", "pytest", "docker", "curl", "bash",
    "sh", "cd", "ls", "echo", "make", "source", "venv", "env", "poetry", "uv",
    # Common generic identifiers & placeholders
    "main", "master", "test", "tests", "example", "examples", "demo", "usage",
    "readme", "todo", "fixme", "url", "uri", "id", "key", "token", "status",
    "path", "file", "dir", "data", "result", "response", "request", "error",
    "config", "json", "yaml", "yml", "toml", "md", "txt", "code", "body", "app",
    "license", "mit", "apache", "github", "workflow", "actions", "ci", "cd"
}


class DocClaimExtractor:
    """Extracts verifiable engineering claims from documentation markdown files."""

    HTTP_METHOD_REGEX = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+([/][a-zA-Z0-9_\-\/{}\.]+)", re.IGNORECASE)
    ENV_VAR_REGEX = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")
    FUNC_CALL_REGEX = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)")
    BACKTICK_TOKEN_REGEX = re.compile(r"`([^`\n]+)`")

    @classmethod
    def extract_claims(cls, doc_name: str, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        claims: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        lines = content.splitlines()

        for idx, line in enumerate(lines, 1):
            # 1. Extract HTTP Endpoints (e.g. `POST /api/v1/auth/token` or `GET /users/{id}`)
            for match in cls.HTTP_METHOD_REGEX.finditer(line):
                method = match.group(1).upper()
                endpoint = match.group(2).strip()
                claim_key = f"HTTP:{method}:{endpoint}".lower()
                if claim_key not in seen_keys:
                    seen_keys.add(claim_key)
                    claims.append({
                        "type": "HTTP_ENDPOINT",
                        "method": method,
                        "endpoint": endpoint,
                        "symbol": f"{method} {endpoint}",
                        "source_doc": doc_name,
                        "line": idx,
                        "context": line.strip(),
                    })

            # 2. Extract Documented Function Signatures inside backticks or code blocks
            # e.g. `verify_jwt_token(secret, algorithm="HS256")`
            for bt_match in cls.BACKTICK_TOKEN_REGEX.finditer(line):
                token = bt_match.group(1).strip()
                func_match = cls.FUNC_CALL_REGEX.match(token)
                if func_match:
                    func_name = func_match.group(1)
                    raw_args = func_match.group(2).strip()
                    if func_name.lower() not in COMMON_DOC_STOPWORDS and not func_name.startswith("__"):
                        parsed_args = [
                            a.split("=")[0].strip()
                            for a in raw_args.split(",")
                            if a.strip() and not a.strip().startswith("*")
                        ]
                        claim_key = f"FUNC:{func_name}".lower()
                        if claim_key not in seen_keys:
                            seen_keys.add(claim_key)
                            claims.append({
                                "type": "FUNCTION",
                                "symbol": func_name,
                                "args": parsed_args,
                                "source_doc": doc_name,
                                "line": idx,
                                "context": line.strip(),
                            })
                else:
                    # Token might be a class or standalone code symbol like `AuthManager`
                    clean_token = token.strip()
                    if (
                        re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", clean_token)
                        and clean_token.lower() not in COMMON_DOC_STOPWORDS
                        and len(clean_token) >= 3
                    ):
                        claim_key = f"SYMBOL:{clean_token}".lower()
                        if claim_key not in seen_keys:
                            seen_keys.add(claim_key)
                            claims.append({
                                "type": "SYMBOL",
                                "symbol": clean_token,
                                "source_doc": doc_name,
                                "line": idx,
                                "context": line.strip(),
                            })

            # 3. Extract Environment Variables (e.g. `MISTRAL_API_KEY`, `DATABASE_URL`)
            for env_match in cls.ENV_VAR_REGEX.finditer(line):
                env_var = env_match.group(1)
                # Ignore common uppercase words / markdown noise
                if env_var.lower() not in COMMON_DOC_STOPWORDS and not env_var.startswith("HTTP_"):
                    claim_key = f"ENV:{env_var}".lower()
                    if claim_key not in seen_keys:
                        seen_keys.add(claim_key)
                        claims.append({
                            "type": "ENV_VAR",
                            "symbol": env_var,
                            "source_doc": doc_name,
                            "line": idx,
                            "context": line.strip(),
                        })

        return claims


class CodeSymbolExtractor:
    """Extracts implemented functions, classes, routes, and env vars from source code."""

    @classmethod
    def extract_symbols(cls, filename: str, content: str) -> Dict[str, Any]:
        if not content:
            return {"functions": {}, "classes": {}, "routes": [], "env_vars": set(), "all_exports": set()}

        is_python = filename.endswith(".py")
        if is_python:
            return cls._extract_python_symbols(filename, content)
        else:
            return cls._extract_regex_symbols(filename, content)

    @classmethod
    def _extract_python_symbols(cls, filename: str, content: str) -> Dict[str, Any]:
        functions: Dict[str, Dict[str, Any]] = {}
        classes: Dict[str, Dict[str, Any]] = {}
        routes: List[Dict[str, Any]] = []
        env_vars: Set[str] = set()
        all_exports: Set[str] = set()

        # Parse AST with robust error recovery
        try:
            tree = ast.parse(content, filename=filename)
        except SyntaxError:
            # Fallback to regex if the file has partial / invalid Python syntax
            return cls._extract_regex_symbols(filename, content)

        for node in ast.walk(tree):
            # Function definitions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args_list = [a.arg for a in node.args.args if a.arg != "self" and a.arg != "cls"]
                functions[node.name] = {
                    "name": node.name,
                    "args": args_list,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "file": filename,
                    "line": getattr(node, "lineno", 1),
                }

                # Route decorator detection: e.g. @app.get("/users"), @router.post("/auth/login")
                for dec in node.decorator_list:
                    route_info = cls._parse_route_decorator(dec)
                    if route_info:
                        routes.append({
                            "method": route_info["method"],
                            "path": route_info["path"],
                            "handler": node.name,
                            "file": filename,
                            "line": getattr(node, "lineno", 1),
                        })

            # Class definitions
            elif isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes[node.name] = {
                    "name": node.name,
                    "methods": methods,
                    "file": filename,
                    "line": getattr(node, "lineno", 1),
                }

            # Environment variable lookups (os.getenv, os.environ.get, os.environ[...])
            elif isinstance(node, ast.Call):
                env_var = cls._parse_env_call(node)
                if env_var:
                    env_vars.add(env_var)

            elif isinstance(node, ast.Subscript):
                env_var = cls._parse_env_subscript(node)
                if env_var:
                    env_vars.add(env_var)

            # __all__ exports
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    all_exports.add(elt.value)

        # Also regex-scan for env vars in comments or dynamic calls
        for match in re.finditer(r"""(?:os\.(?:getenv|environ\.get)\(['"]([A-Z0-9_]+)['"]|os\.environ\[['"]([A-Z0-9_]+)['"]\])""", content):
            var = match.group(1) or match.group(2)
            if var:
                env_vars.add(var)

        return {
            "functions": functions,
            "classes": classes,
            "routes": routes,
            "env_vars": env_vars,
            "all_exports": all_exports,
        }

    @classmethod
    def _parse_route_decorator(cls, dec: ast.AST) -> Optional[Dict[str, str]]:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            method = dec.func.attr.upper()
            if method in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "ROUTE"}:
                if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                    path = dec.args[0].value
                    return {"method": method if method != "ROUTE" else "ANY", "path": path}
        return None

    @classmethod
    def _parse_env_call(cls, node: ast.Call) -> Optional[str]:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {"getenv", "get"}:
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        return node.args[0].value
                elif isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "environ":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        return node.args[0].value
        return None

    @classmethod
    def _parse_env_subscript(cls, node: ast.Subscript) -> Optional[str]:
        if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
            if isinstance(node.value.value, ast.Name) and node.value.value.id == "os":
                slice_node = node.slice
                if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                    return slice_node.value
        return None

    @classmethod
    def _extract_regex_symbols(cls, filename: str, content: str) -> Dict[str, Any]:
        functions: Dict[str, Dict[str, Any]] = {}
        classes: Dict[str, Dict[str, Any]] = {}
        routes: List[Dict[str, Any]] = []
        env_vars: Set[str] = set()
        all_exports: Set[str] = set()

        # Functions (JS/TS/Python regex)
        for match in re.finditer(r"""(?:function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)|(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>)""", content):
            name = match.group(1) or match.group(3)
            raw_args = match.group(2) or match.group(4) or ""
            args_list = [a.split(":")[0].strip() for a in raw_args.split(",") if a.strip()]
            if name:
                functions[name] = {"name": name, "args": args_list, "file": filename, "line": 1}

        # Classes
        for match in re.finditer(r"""class\s+([a-zA-Z0-9_]+)""", content):
            cls_name = match.group(1)
            classes[cls_name] = {"name": cls_name, "methods": [], "file": filename, "line": 1}

        # Express / FastAPI regex routes
        for match in re.finditer(r"""\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]""", content, re.IGNORECASE):
            routes.append({
                "method": match.group(1).upper(),
                "path": match.group(2),
                "handler": "",
                "file": filename,
                "line": 1,
            })

        # Process.env or os.getenv
        for match in re.finditer(r"""(?:process\.env\.([A-Z0-9_]+)|os\.(?:getenv|environ\.get)\(['"]([A-Z0-9_]+)['"]|os\.environ\[['"]([A-Z0-9_]+)['"]\])""", content):
            var = match.group(1) or match.group(2) or match.group(3)
            if var:
                env_vars.add(var)

        return {
            "functions": functions,
            "classes": classes,
            "routes": routes,
            "env_vars": env_vars,
            "all_exports": all_exports,
        }


class DocDiscrepancyDetector:
    """Cross-references documented claims with extracted code symbols to detect discrepancies."""

    @classmethod
    def detect_discrepancies(
        cls,
        docs: Dict[str, str],
        code_files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Takes documentation files (e.g. {'README.md': '...', 'docs/api.md': '...'})
        and code files (e.g. {'main.py': '...', 'auth.py': '...'}),
        and cross-references them to surface documentation drift.
        """
        all_claims: List[Dict[str, Any]] = []
        for doc_name, doc_content in docs.items():
            all_claims.extend(DocClaimExtractor.extract_claims(doc_name, doc_content))

        combined_symbols: Dict[str, Any] = {
            "functions": {},
            "classes": {},
            "routes": [],
            "env_vars": set(),
            "all_exports": set(),
        }

        for fname, fcontent in code_files.items():
            syms = CodeSymbolExtractor.extract_symbols(fname, fcontent)
            combined_symbols["functions"].update(syms["functions"])
            combined_symbols["classes"].update(syms["classes"])
            combined_symbols["routes"].extend(syms["routes"])
            combined_symbols["env_vars"].update(syms["env_vars"])
            combined_symbols["all_exports"].update(syms["all_exports"])

        discrepancies: List[Dict[str, Any]] = []

        # If no code files were provided, we cannot establish discrepancies
        if not code_files:
            return {
                "total_discrepancies": 0,
                "discrepancies": [],
                "claims_analyzed": len(all_claims),
                "summary": "No source code files available to verify documentation claims against.",
            }

        # Check HTTP endpoints
        implemented_routes: Set[str] = set()
        for r in combined_symbols["routes"]:
            norm_path = r["path"].rstrip("/").lower()
            implemented_routes.add(f"{r['method']}:{norm_path}")
            implemented_routes.add(f"ANY:{norm_path}")

        for claim in all_claims:
            claim_type = claim["type"]

            # 1. Check HTTP Endpoints
            if claim_type == "HTTP_ENDPOINT":
                method = claim["method"]
                norm_endpoint = claim["endpoint"].rstrip("/").lower()
                expected_key = f"{method}:{norm_endpoint}"
                expected_any = f"ANY:{norm_endpoint}"

                # Match with variable replacement (e.g. /users/{id} vs /users/<id>)
                matched = False
                if expected_key in implemented_routes or expected_any in implemented_routes:
                    matched = True
                else:
                    for ir in implemented_routes:
                        ir_method, ir_path = ir.split(":", 1)
                        if ir_method in {method, "ANY"}:
                            # Normalize path params e.g. {id} -> *
                            p1 = re.sub(r"\{[a-zA-Z0-9_]+\}", "*", norm_endpoint)
                            p2 = re.sub(r"\{[a-zA-Z0-9_]+\}", "*", ir_path)
                            if p1 == p2:
                                matched = True
                                break

                if not matched:
                    discrepancies.append({
                        "type": DiscrepancyType.MISSING_IMPLEMENTATION,
                        "severity": "HIGH",
                        "claim": claim["symbol"],
                        "source_doc": claim["source_doc"],
                        "line": claim["line"],
                        "details": f"Documented HTTP route `{claim['symbol']}` was not found in implemented routes.",
                    })

            # 2. Check Functions & Signatures
            elif claim_type == "FUNCTION":
                func_name = claim["symbol"]
                doc_args = claim.get("args", [])

                if func_name in combined_symbols["functions"]:
                    actual_fn = combined_symbols["functions"][func_name]
                    actual_args = actual_fn.get("args", [])

                    # Check signature mismatch if arguments were specified in the doc claim
                    if doc_args and actual_args:
                        # If none of the documented args match actual args, surface signature mismatch
                        overlap = set(doc_args).intersection(set(actual_args))
                        if not overlap and len(doc_args) > 0 and len(actual_args) > 0:
                            discrepancies.append({
                                "type": DiscrepancyType.SIGNATURE_MISMATCH,
                                "severity": "MEDIUM",
                                "claim": f"{func_name}({', '.join(doc_args)})",
                                "source_doc": claim["source_doc"],
                                "line": claim["line"],
                                "source_file": actual_fn["file"],
                                "details": (
                                    f"Documented signature `{func_name}({', '.join(doc_args)})` in `{claim['source_doc']}` "
                                    f"mismatches implemented parameters `{func_name}({', '.join(actual_args)})` in `{actual_fn['file']}`."
                                ),
                            })
                else:
                    # Function is completely missing in code
                    # Only flag if not a common class method or standard library
                    if func_name.lower() not in COMMON_DOC_STOPWORDS:
                        discrepancies.append({
                            "type": DiscrepancyType.MISSING_IMPLEMENTATION,
                            "severity": "HIGH",
                            "claim": f"{func_name}()",
                            "source_doc": claim["source_doc"],
                            "line": claim["line"],
                            "details": f"Documented function `{func_name}()` was not found in inspected source files.",
                        })

            # 3. Check Standalone Symbols (e.g. `AuthService`)
            elif claim_type == "SYMBOL":
                sym_name = claim["symbol"]
                # Must start with uppercase or have underscores to be considered an explicit component
                if (sym_name[0].isupper() or "_" in sym_name) and len(sym_name) >= 4:
                    in_classes = sym_name in combined_symbols["classes"]
                    in_funcs = sym_name in combined_symbols["functions"]
                    in_exports = sym_name in combined_symbols["all_exports"]

                    if not (in_classes or in_funcs or in_exports):
                        # Verify it's not simply a substring in code files
                        in_code = any(sym_name in code for code in code_files.values())
                        if not in_code:
                            discrepancies.append({
                                "type": DiscrepancyType.MISSING_IMPLEMENTATION,
                                "severity": "MEDIUM",
                                "claim": sym_name,
                                "source_doc": claim["source_doc"],
                                "line": claim["line"],
                                "details": f"Documented symbol `{sym_name}` was not found in implemented classes, functions, or exports.",
                            })

            # 4. Check Environment Variables
            elif claim_type == "ENV_VAR":
                env_name = claim["symbol"]
                if env_name not in combined_symbols["env_vars"]:
                    # Check if referenced anywhere in code texts
                    in_code = any(env_name in code for code in code_files.values())
                    if not in_code:
                        discrepancies.append({
                            "type": DiscrepancyType.MISSING_ENV_VAR,
                            "severity": "MEDIUM",
                            "claim": env_name,
                            "source_doc": claim["source_doc"],
                            "line": claim["line"],
                            "details": f"Documented environment variable `{env_name}` is not referenced or accessed in source code.",
                        })

        summary = format_discrepancy_report(discrepancies)

        return {
            "total_discrepancies": len(discrepancies),
            "discrepancies": discrepancies,
            "claims_analyzed": len(all_claims),
            "symbols_analyzed": len(combined_symbols["functions"]) + len(combined_symbols["classes"]) + len(combined_symbols["routes"]),
            "summary": summary,
        }


def format_discrepancy_report(discrepancies: List[Dict[str, Any]]) -> str:
    """Formats discrepancy findings into a clean, human-readable markdown section."""
    if not discrepancies:
        return "✅ Documentation aligns with inspected source code implementation (0 discrepancies found)."

    lines = [
        f"⚠️ **Documentation vs Implementation Discrepancies ({len(discrepancies)} detected)**:",
        "",
        "| Type | Claim | Document | Details |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for d in discrepancies:
        dtype = d.get("type", "UNKNOWN")
        badge = "❌ Missing" if dtype == DiscrepancyType.MISSING_IMPLEMENTATION else "⚠️ Mismatch" if dtype == DiscrepancyType.SIGNATURE_MISMATCH else "ℹ️ Env Drift"
        claim = f"`{d.get('claim', '')}`"
        doc = f"`{d.get('source_doc', '')}:{d.get('line', '')}`"
        details = d.get("details", "").replace("|", "\\|")
        lines.append(f"| {badge} | {claim} | {doc} | {details} |")

    lines.append("")
    lines.append("> **Note for Contributor**: Verify implementation source files before relying on claims in the documentation.")
    return "\n".join(lines)
