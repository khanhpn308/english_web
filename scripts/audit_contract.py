#!/usr/bin/env python3
"""T044 static contract conformance analysis; no application imports or execution.

Default: emit Markdown to stdout. --json emits structured evidence.
--write-report is the only write mode and only writes the T044 report.
Exit 0 means all *static* checks have evidence; 1 means violations/owner blockers;
2 means incomplete evidence. Runtime acceptance is never inferred from source.
"""

import argparse
import ast
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

VERSION = "t044-static-contract/1"
REPORT = "docs/reviews/contract-conformance-003.md"
METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})
DEPENDENCIES = ("T013", "T008", "T024", "T027", "T029", "T032", "T035", "T047",
                "T048", "T049", "T037", "T046", "T061")
SEVERITIES = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
# These are the approved C013-08 defaults, not adjustable checker tolerances.
CAPS = {"requestJsonBytes": 1048576, "sourceMarkdownBytes": 8388608,
        "bridgeResponseBytes": 4194304, "contentCodePoints": 4096,
        "collectionItems": 100, "quizTotalMin": 5, "quizTotalMax": 30,
        "quizPerTypeMax": 20, "pageSizeMax": 100, "termCodePoints": 80}
ALIASES = {"WordForm": "WordFormDetail", "WordFormDraft": "LookupForm",
           "SaveExistingSourceRequest": "SaveWordFormsRequest",
           "WritingAnswerDraftRequest": "AnswerDraftRequest", "SourceFile": "SourceFileView",
           "SyncRun": "SyncRunView", "ReviewCard": "ReviewCardView",
           "ReviewEvent": "ReviewEventView", "Page<T>": "WordFormCollection"}
OWNERS = {"lookups": "T008", "word-forms": "T024", "review": "T032",
          "cards": "T032", "dashboard": "T037", "quiz-attempts": "T035",
          "quiz-questions": "T049", "status": "T046", "runbooks": "T061",
          "capabilities": "T006", "operations": "T014", "sources": "T023",
          "sync-runs": "T023", "ai-consent": "T066", "health": "T006"}
FORBIDDEN_FIELDS = frozenset({"bridgekey", "proxykey", "apikey", "authorization", "cookie",
    "cookies", "bootstraptoken", "sessionid", "sessionidentifier", "googletoken",
    "googlesession", "adminpassword", "password", "providerbody", "rawproviderresponse",
    "rawproviderbody", "rawmarkdown", "markdown", "databasepath", "storagepath",
    "stacktrace", "traceback", "accountid", "accountemail", "email", "fullname",
    "accesstoken", "refreshtoken", "sessiontoken", "admincredentials", "googlecredentials",
    "proxyclientkey", "bridgeproxykey", "prompt", "rawprompt", "rawanswer", "secret",
    "clientsecret", "privatekey", "cookievalue", "token"})
DIAGNOSTIC_FIELDS = frozenset({"prompt", "prompten", "answer", "answers", "content",
                              "summaryvi", "meaningsen", "meaningsvi", "examples"})


def label(value):
    """Emit identifiers only; never source snippets, example values or exception text."""
    text = str(value)
    if (len(text) <= 80 and not re.search(r"sk-|AIza|ya29\.|[a-fA-F0-9]{24,}", text)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.<>-]*|[0-9]{3}", text)):
        return text
    return "[redacted-identifier]"


def normalized_path(value):
    value = value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}", "{param}", value)


def route_owner(path, method=""):
    if "/answers/" in path:
        return "T047"
    if path.endswith("/submissions"):
        return "T048"
    if "/word-forms/" in path and method == "patch":
        return "T029"
    if path.endswith("/word-forms") and method == "get":
        return "T027"
    for part in path.split("/"):
        if part in OWNERS:
            return OWNERS[part]
    return "T013"


@dataclass(frozen=True)
class Finding:
    status: str
    severity: str
    check: str
    owner: str
    location: str
    detail: str


class Sources:
    """Only repository-relative, regular non-symlink source files are read."""

    def __init__(self, root):
        self.root = root.resolve()
        self.texts = {}
        self.trees = {}

    def read(self, relative):
        if relative in self.texts:
            return self.texts[relative]
        path = self.root / relative
        if (path.is_symlink() or not path.resolve().is_relative_to(self.root) or any(
                parent.is_symlink() for parent in path.parents if parent != self.root
                and parent.is_relative_to(self.root))):
            raise ValueError("Unsafe source path")
        text = path.read_text(encoding="utf-8")
        self.texts[relative] = text
        return text

    def tree(self, relative):
        if relative not in self.trees:
            self.trees[relative] = ast.parse(self.read(relative))
        return self.trees[relative]

    def glob(self, pattern):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.glob(pattern)
                      if p.is_file())

    def symbol(self, relative, name, seen=frozenset()):
        key = (relative, name)
        if key in seen:
            return None
        seen = seen | {key}
        for node in self.tree(relative).body:
            if isinstance(node, ast.ClassDef) and node.name == name:
                return relative, node
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == name:
                    return relative, node.value
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == name
                       for target in node.targets):
                    return relative, node.value
            if isinstance(node, ast.ImportFrom) and node.module:
                for item in node.names:
                    if (item.asname or item.name) == name and node.module.startswith("backend."):
                        target = node.module.replace(".", "/") + ".py"
                        if (self.root / target).is_file():
                            return self.symbol(target, item.name, seen)
        return None

    def literal(self, relative, node, seen=frozenset()):
        if node is None:
            return None
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            if isinstance(node, ast.Name):
                key = (relative, node.id)
                if key not in seen:
                    found = self.symbol(relative, node.id)
                    if found and not isinstance(found[1], ast.ClassDef):
                        return self.literal(found[0], found[1], seen | {key})
        return None


def keyword(call, name):
    return next((item.value for item in call.keywords if item.arg == name), None)


def node_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def annotation_facts(sources, relative, node, seen=frozenset()):
    """Resolve only explicit types, literals and bounds. Validators are not executed."""
    facts = {"nullable": False, "enum": [], "bounds": {}}
    if isinstance(node, ast.Constant):
        facts["nullable"] = node.value is None
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = annotation_facts(sources, relative, node.left, seen)
        right = annotation_facts(sources, relative, node.right, seen)
        facts["nullable"] = left["nullable"] or right["nullable"]
        facts["enum"] = left["enum"] + right["enum"]
        facts["bounds"] = left["bounds"] | right["bounds"]
        if left.get("type") or right.get("type"):
            facts["type"] = left.get("type") or right["type"]
    elif isinstance(node, ast.Subscript):
        name = node_name(node.value)
        args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if name == "Literal":
            facts["enum"] = [sources.literal(relative, item) for item in args]
            facts["nullable"] = None in facts["enum"]
        elif name in {"Annotated", "Optional", "Union"}:
            for item in args:
                other = annotation_facts(sources, relative, item, seen)
                facts["nullable"] |= other["nullable"]
                facts["enum"] += other["enum"]
                facts["bounds"].update(other["bounds"])
                if other.get("type"):
                    facts["type"] = other["type"]
            facts["nullable"] |= name == "Optional"
        elif name in {"list", "List", "Sequence", "tuple"}:
            facts["type"] = "array"
    elif isinstance(node, ast.Call):
        for item in node.keywords:
            value = sources.literal(relative, item.value)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                facts["bounds"][item.arg] = value
    elif isinstance(node, ast.Name):
        if node.id in {"str", "int", "float", "bool"}:
            facts["type"] = {"str": "string", "int": "integer", "float": "number",
                             "bool": "boolean"}[node.id]
        elif (relative, node.id) not in seen:
            found = sources.symbol(relative, node.id)
            if found:
                path, definition = found
                if isinstance(definition, ast.ClassDef):
                    if any(node_name(base) in {"Enum", "StrEnum", "IntEnum"}
                           for base in definition.bases):
                        facts["enum"] = [sources.literal(path, item.value)
                            for item in definition.body if isinstance(item, ast.Assign)]
                    else:
                        facts["ref"] = definition.name
                else:
                    return annotation_facts(sources, path, definition,
                                            seen | {(relative, node.id)})
    return facts


def uses_camel_alias(sources, relative, definition, seen=frozenset()):
    key = (relative, definition.name)
    if key in seen:
        return False
    for item in definition.body:
        if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
            if node_name(keyword(item.value, "alias_generator")) == "to_camel":
                return True
    for base in definition.bases:
        found = sources.symbol(relative, node_name(base))
        if found and isinstance(found[1], ast.ClassDef):
            if uses_camel_alias(sources, *found, seen | {key}):
                return True
    return False


def schema_fields(sources, relative, definition, seen=frozenset()):
    key = (relative, definition.name)
    if key in seen:
        return {}
    result = {}
    camel = uses_camel_alias(sources, relative, definition)
    for base in definition.bases:
        found = sources.symbol(relative, node_name(base))
        if found and isinstance(found[1], ast.ClassDef):
            result.update(schema_fields(sources, *found, seen | {key}))
    for field in definition.body:
        if not isinstance(field, ast.AnnAssign) or not isinstance(field.target, ast.Name):
            continue
        name = field.target.id
        if name == "model_config" or name.startswith("_"):
            continue
        if camel:
            first, *tail = name.split("_")
            name = first + "".join(part.capitalize() for part in tail)
        facts = annotation_facts(sources, relative, field.annotation)
        facts["required"] = field.value is None
        if isinstance(field.value, ast.Constant) and field.value.value is not Ellipsis:
            facts["default"] = field.value.value
        if isinstance(field.value, ast.Call):
            facts["bounds"].update(annotation_facts(sources, relative, field.value)["bounds"])
            default = keyword(field.value, "default")
            facts["required"] = default is None and keyword(field.value, "default_factory") is None
            if isinstance(default, ast.Constant) and default.value is Ellipsis:
                facts["required"] = True
            elif isinstance(default, ast.Constant):
                facts["default"] = default.value
            if field.value.args:
                facts["required"] = isinstance(field.value.args[0], ast.Constant) and (
                    field.value.args[0].value is Ellipsis)
                if isinstance(field.value.args[0], ast.Constant) and not facts["required"]:
                    facts["default"] = field.value.args[0].value
            alias = sources.literal(relative, keyword(field.value, "serialization_alias")) or (
                sources.literal(relative, keyword(field.value, "alias")))
            if isinstance(alias, str):
                name = alias
        facts["line"] = field.lineno
        result[name] = facts
    return result


def collect_routes(sources, add):
    main = "backend/app/main.py"
    tree = sources.tree(main)
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                imports[item.asname or item.name] = (node.module.replace(".", "/") + ".py",
                                                     item.name)
    registered = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node_name(node.func) == "include_router":
            router = node_name(node.args[0]) if node.args else ""
            if router in imports:
                extra = sources.literal(main, keyword(node, "prefix")) or ""
                registered.append((*imports[router], extra))
            else:
                add("PENDING", "HIGH", "DYNAMIC_ROUTE", "T017", main, node.lineno,
                    "Router registration cannot be statically resolved.")
    routes = {}
    for relative, router_name, extra in sorted(set(registered + [(main, "app", "")])):
        module = sources.tree(relative)
        prefix = ""
        for node in module.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if any(isinstance(t, ast.Name) and t.id == router_name for t in node.targets):
                    prefix_value = sources.literal(relative, keyword(node.value, "prefix"))
                    if prefix_value is not None:
                        prefix = prefix_value
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if node_name(decorator.func.value) != router_name:
                    continue
                method = decorator.func.attr
                if method not in METHODS and method != "api_route":
                    continue
                suffix = sources.literal(relative, decorator.args[0]) if decorator.args else None
                if not isinstance(suffix, str):
                    add("PENDING", "HIGH", "DYNAMIC_ROUTE", "T017", relative, node.lineno,
                        "Route path cannot be statically resolved.")
                    continue
                methods = [method]
                if method == "api_route":
                    methods = sources.literal(relative, keyword(decorator, "methods"))
                    if not isinstance(methods, (list, tuple)):
                        add("PENDING", "HIGH", "DYNAMIC_METHOD", "T017", relative, node.lineno,
                            "HTTP methods cannot be statically resolved.")
                        continue
                path = normalized_path(extra + prefix + suffix)
                for method in methods:
                    model = keyword(decorator, "response_model")
                    status = sources.literal(relative, keyword(decorator, "status_code")) or 200
                    key = (str(method).lower(), path)
                    if key in routes:
                        add("FAIL", "HIGH", "DUPLICATE_ROUTE", route_owner(path), relative,
                            node.lineno, "Duplicate implemented method/path registration.")
                    routes[key] = {"source": relative, "line": node.lineno, "status": str(status),
                                   "model": node_name(model), "function": node,
                                   "responses": keyword(decorator, "responses"),
                                   "in_schema": sources.literal(relative,
                                       keyword(decorator, "include_in_schema")) is not False}
    return routes


def split_fields(text):
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == "," and depth == 0:
            yield text[start:index].strip()
            start = index + 1
    yield text[start:].strip()


def document_contract(text):
    routes = {}
    schemas = {}
    examples = []
    for line, content in enumerate(text.splitlines(), 1):
        if content.startswith("|"):
            endpoints = re.findall(r"`(/(?:api/v1|bootstrap)[^`]*)`", content)
            methods = re.findall(r"`(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)`", content)
            if endpoints and methods:
                cells = [cell.strip() for cell in re.findall(r"\|((?:`[^`]*`|[^|`])*)", content)]
                if cells and not cells[-1]:
                    cells.pop()
                statuses = re.findall(r"\b([1-5][0-9]{2})\b", cells[-1] if cells else "")
                for method in methods:
                    for path in endpoints:
                        routes[(method.lower(), normalized_path(path))] = {
                            "line": line, "statuses": sorted(set(statuses)),
                            "schemas": sorted(set(re.findall(
                                r"\b([A-Z][a-z][A-Za-z0-9]*(?:Request|Result|Summary|View|Page|"
                                r"Attempt|Response|Operation|Consent|File|Run|Card|Event))\b", content))),
                            "historical": bool(re.search(r"historical|deprecated|removed", content,
                                                          re.IGNORECASE))}
    # A compact schema declaration has its own line; nested objects are balanced.
    for match in re.finditer(r"(?m)^([A-Z][A-Za-z0-9_]*)\s*\{", text):
        start = match.end()
        depth = 1
        end = start
        while end < len(text) and depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        if depth:
            continue
        fields = {}
        for part in split_fields(text[start:end - 1]):
            field = re.match(r"([A-Za-z_][A-Za-z0-9_]*)(\?)?(?:\[\])?\s*(?::\s*(.*))?$",
                             part, re.DOTALL)
            if field:
                fields[field[1]] = {"optional": bool(field[2]), "type": field[3] or ""}
        schemas[match[1]] = {"fields": fields, "line": text.count("\n", 0, match.start()) + 1}
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^```(json|http)\s*\n(.*?)^```", text, re.DOTALL):
        body = match[2]
        line = text.count("\n", 0, match.start()) + 1
        context = text[max(0, match.start() - 350):match.start()]
        negative = bool(re.search(r"negative (?:count )?fixture|invalid fixture",
                                  context, re.IGNORECASE))
        if match[1] == "json":
            try:
                value = json.loads(body)
            except ValueError:
                examples.append({"line": line, "invalid": True})
                continue
            named = isinstance(value, dict) and value and all(
                re.fullmatch(r"[A-Z][A-Za-z0-9_<>]*", key) for key in value)
            if named:
                for name, item in sorted(value.items()):
                    examples.append({"name": name, "value": item, "line": line,
                                     "negative": negative})
            else:
                name = "ErrorResponse" if isinstance(value, dict) and "error" in value else ""
                examples.append({"name": name, "value": value, "line": line,
                                 "negative": negative})
        else:
            request = re.search(r"^(GET|POST|PUT|PATCH|DELETE)\s+([^\s]+)", body, re.MULTILINE)
            if request:
                examples.append({"line": line, "query": parse_qsl(urlsplit(request[2]).query,
                    keep_blank_values=True), "route": (request[1].lower(), normalized_path(request[2]))})
            for header in re.finditer(r"(?im)^(Authorization|Cookie|Set-Cookie|X-API-Key):\s*(.*)$", body):
                if not re.search(r"<[^>]+>|\[redacted\]", header[2], re.IGNORECASE):
                    examples.append({"line": line + body.count("\n", 0, header.start()),
                                     "sensitive_header": header[1].lower()})
            offset = 0
            while offset < len(body):
                found = re.search(r"(?m)^[\{\[]", body[offset:])
                if not found:
                    break
                position = offset + found.start()
                try:
                    value, length = decoder.raw_decode(body[position:])
                except ValueError:
                    examples.append({"line": line, "invalid": True})
                    break
                previous = body[:position]
                response = list(re.finditer(r"HTTP/1\.1\s+([1-5][0-9]{2})", previous))
                examples.append({"name": "ErrorResponse" if response and
                                 int(response[-1][1]) >= 400 else "", "value": value,
                                 "line": line + body.count("\n", 0, position),
                                 "negative": negative and not response,
                                 "route": (request[1].lower(), normalized_path(request[2]))
                                 if request else None,
                                 "status": response[-1][1] if response else None})
                offset = position + length
    return routes, schemas, examples


def dereference(schema, components):
    if not isinstance(schema, dict):
        return {}
    reference = schema.get("$ref", "")
    return components.get(reference.rsplit("/", 1)[-1], {}) if reference else schema


def schema_enum(schema, components, depth=0):
    if depth > 20:
        return []
    schema = dereference(schema, components)
    values = list(schema.get("enum", []))
    if "const" in schema:
        values.append(schema["const"])
    for key in ("anyOf", "oneOf", "allOf"):
        for branch in schema.get(key, []):
            values.extend(schema_enum(branch, components, depth + 1))
    return values


def nullable(schema, components, depth=0):
    if depth > 20:
        return False
    schema = dereference(schema, components)
    return schema.get("nullable", False) or schema.get("type") == "null" or any(
        nullable(branch, components, depth + 1) for branch in schema.get("anyOf", []) +
        schema.get("oneOf", []))


def example_errors(value, schema, components, pointer="$", depth=0):
    """Validate the represented JSON Schema subset; errors contain field names only."""
    if depth > 40:
        return [(pointer, "validation-depth-unresolved")]
    if schema is False:
        return [(pointer, "false-schema-rejects-value")]
    if schema is True:
        schema = {}
    if "$ref" in schema and schema["$ref"].rsplit("/", 1)[-1] not in components:
        return [(pointer, "missing-schema-reference")]
    schema = dereference(schema, components)
    errors = []
    for combinator in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(combinator, [])
        if not branches:
            continue
        trials = [example_errors(value, branch, components, pointer, depth + 1)
                  for branch in branches]
        if combinator == "allOf":
            errors.extend(item for trial in trials for item in trial)
        else:
            valid = sum(not trial for trial in trials)
            if valid == 0:
                errors.extend(min(trials, key=lambda trial: (len(trial), repr(trial))))
            elif combinator == "oneOf" and valid != 1:
                errors.append((pointer, "ambiguous-oneOf"))
    if value is None:
        if schema and not nullable(schema, components):
            errors.append((pointer, "null-not-permitted"))
        return errors
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "boolean": isinstance(value, bool),
               "integer": isinstance(value, int) and not isinstance(value, bool),
               "number": isinstance(value, (int, float)) and not isinstance(value, bool),
               "null": False}
    if isinstance(kind, str) and kind in matches and not matches[kind]:
        return errors + [(pointer, "wrong-type")]
    if "enum" in schema and value not in schema["enum"]:
        errors.append((pointer, "enum-value-not-permitted"))
    if "const" in schema and value != schema["const"]:
        errors.append((pointer, "constant-not-permitted"))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in sorted(set(schema.get("required", [])) - value.keys()):
            errors.append((pointer + "." + label(name), "required-field-missing"))
        if "properties" in schema or schema.get("additionalProperties") is False:
            for name in sorted(value):
                child = pointer + "." + label(name)
                if name not in properties:
                    errors.append((child, "field-absent-from-schema"))
                else:
                    errors.extend(example_errors(value[name], properties[name], components,
                                                 child, depth + 1))
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 100):
            errors.append((pointer, "collection-bound-violation"))
        for index, item in enumerate(value):
            errors.extend(example_errors(item, schema.get("items", {}), components,
                                         pointer + f"[{index}]", depth + 1))
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 4096):
            errors.append((pointer, "string-bound-violation"))
        if "pattern" in schema:
            try:
                if not re.search(schema["pattern"], value):
                    symbolic = re.fullmatch(r"[A-Za-z0-9_]+\.\.\.", value) and (
                        re.search(r"\.(?:id|[A-Za-z]+Id)$", pointer))
                    errors.append((pointer, "symbolic-id-unresolved" if symbolic else "pattern-mismatch"))
            except re.error:
                errors.append((pointer, "pattern-dialect-unresolved"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            errors.append((pointer, "non-finite-number"))
        for key, invalid in (("minimum", lambda n: value < n),
                             ("maximum", lambda n: value > n),
                             ("exclusiveMinimum", lambda n: value <= n),
                             ("exclusiveMaximum", lambda n: value >= n)):
            if key in schema and invalid(schema[key]):
                errors.append((pointer, "numeric-bound-violation"))
    return errors


def privacy_errors(value, diagnostic=False, public_question=False, pointer="$", depth=0):
    if depth > 40:
        return [(pointer, "privacy-depth-unresolved")]
    errors = []
    if isinstance(value, dict):
        public_question |= value.get("type") in ("MCQ", "CLOZE", "WRITING") and "id" in value
        for key, item in sorted(value.items()):
            field = re.sub(r"[^a-z]", "", key.lower())
            child = pointer + "." + label(key)
            prohibited = field in FORBIDDEN_FIELDS or (diagnostic and field in DIAGNOSTIC_FIELDS)
            prohibited |= public_question and field in {"correctoptionid", "acceptedanswers",
                                                       "explanationvi", "scoringkey"}
            if prohibited:
                errors.append((child, "sensitive-field-at-public-boundary"))
            errors.extend(privacy_errors(item, diagnostic, public_question, child, depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(privacy_errors(item, diagnostic, public_question,
                                         pointer + f"[{index}]", depth + 1))
    elif isinstance(value, str):
        if re.search(r"(?i)bearer\s+\S+|AIza[\w-]{20,}|-----BEGIN .*PRIVATE KEY|"
                     r"(?:sk-|ya29\.)[\w.-]{12,}|Traceback \(most recent call last\)", value):
            errors.append((pointer, "credential-or-stack-trace-content"))
        if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
            errors.append((pointer, "account-identity-content"))
        if re.search(r"(?i)(?:[A-Z]:\\|/home/|/Users/|/var/).+|\.(?:sqlite3?|db)\b", value):
            errors.append((pointer, "machine-or-database-path-content"))
        for match in re.finditer(r"https?://[^\s\"<>]+", value):
            url = urlsplit(match[0])
            if not (pointer.endswith(".cambridgeUrl") and url.scheme == "https"
                    and url.netloc == "dictionary.cambridge.org"
                    and url.path.startswith("/dictionary/english/") and not url.query
                    and not url.fragment):
                errors.append((pointer, "external-url-content"))
    return errors


def requirement_ids(text):
    result = set()
    pattern = r"(FR-[A-Z]+-|AC-)(\d+)((?:\s*[–-]\s*(?:(?:FR-[A-Z]+-|AC-))?\d+)?(?:/\d+)*)"
    for match in re.finditer(pattern, text):
        prefix, number, suffix = match.groups()
        first = int(number)
        result.add(f"{prefix}{first:02d}")
        if re.search(r"[–-]", suffix):
            end = int(re.findall(r"\d+", suffix)[-1])
            if first <= end <= first + 100:
                result.update(f"{prefix}{n:02d}" for n in range(first, end + 1))
        else:
            result.update(f"{prefix}{int(n):02d}" for n in re.findall(r"/(\d+)", suffix))
    return result


class Audit:
    def __init__(self, root):
        self.sources = Sources(root)
        self.findings = []
        self.coverage = []
        self.route_index = []
        self.dependencies = []
        self.contracts_by_task = {}

    def add(self, status, severity, check, owner, path, line, detail):
        location = path + (f":{line}" if line else "")
        self.findings.append(Finding(status, severity, check, owner, location, detail))

    def run(self):
        sources = self.sources
        add = self.add
        api = sources.read("docs/api-contract.md")
        spec = sources.read("docs/spec.md")
        constraints = sources.read("CONSTRAINTS.md")
        adr_text = "\n".join(sources.read(path) for path in sources.glob("docs/adr/*.md"))
        for path in ("AGENTS.md", "docs/task-plan.md", "scripts/export_contract.py",
                     "scripts/tests/test_contract.py", "scripts/tests/test_architecture_gate.py",
                     "backend/app/http/errors.py", "package.json"):
            sources.read(path)
        if (sources.root / "AGENT.md").is_file():
            sources.read("AGENT.md")
        for path in sources.glob("docs/reviews/contract-conformance-*.md"):
            if path != REPORT:
                sources.read(path)
        sources.read("docs/reviews/spec-architecture-review-001.md")
        snapshot = json.loads(sources.read("contracts/openapi.json"))
        components = snapshot.get("components", {}).get("schemas", {})
        if not isinstance(components, dict) or not isinstance(snapshot.get("paths"), dict):
            raise ValueError("Invalid contract snapshot")
        implemented = collect_routes(sources, add)
        documented, declarations, examples = document_contract(api)
        exported = {(method, normalized_path(path)): operation
                    for path, methods in snapshot["paths"].items()
                    for method, operation in methods.items() if method in METHODS}
        for key in sorted(set(implemented) | set(documented) | set(exported)):
            method, path = key
            source = implemented.get(key)
            doc = documented.get(key)
            owner = route_owner(path, method)
            line = source["line"] if source else (doc["line"] if doc else 0)
            file = source["source"] if source else "docs/api-contract.md"
            ancillary = path in {"/bootstrap", "/{param}"}
            classification = "ANCILLARY_SHELL" if ancillary else "CURRENT"
            if doc and doc["historical"]:
                classification = "DOCUMENTED_HISTORICAL_OR_DEPRECATED"
                add("OWNER_DECISION_REQUIRED", "HIGH", "ROUTE_CLASSIFICATION", "T013",
                    "docs/api-contract.md", doc["line"],
                    "Historical/deprecated table entry requires a current removal/migration decision.")
            if source and not doc and not ancillary:
                add("FAIL", "HIGH", "UNDOCUMENTED_METHOD_PATH", owner, file, line,
                    "Implemented method/path has no current endpoint table declaration.")
            if doc and not source and not doc["historical"]:
                add("FAIL", "HIGH", "MISSING_METHOD_PATH", owner, file, line,
                    "Current documented method/path has no production registration.")
            if source and source["in_schema"] and key not in exported:
                add("FAIL", "HIGH", "STALE_OPENAPI_ROUTE", "T017", file, line,
                    "Production method/path is absent from the checked OpenAPI snapshot.")
            if key in exported and not source:
                add("FAIL", "HIGH", "STALE_OPENAPI_ROUTE", "T017", "contracts/openapi.json", 0,
                    "Snapshot method/path has no production registration.")
            self.route_index.append({"method": method.upper(), "path": self.safe_path(path),
                                     "owner": owner, "classification": classification,
                                     "implementation": f"{file}:{line}" if source else "MISSING",
                                     "documentation": f"docs/api-contract.md:{doc['line']}"
                                     if doc else "MISSING"})
            if key not in exported:
                continue
            operation = exported[key]
            route_schemas = sorted({node["$ref"].rsplit("/", 1)[-1]
                                    for node in self.walk(operation) if "$ref" in node})
            self.contracts_by_task.setdefault(owner, []).append({
                "method": method.upper(), "path": self.safe_path(path),
                "schemas": [label(name) for name in route_schemas],
                "snapshot": "contracts/openapi.json"})
            if doc:
                for name in doc["schemas"]:
                    target = ALIASES.get(name, name)
                    if target not in route_schemas:
                        add("FAIL", "HIGH", "ENDPOINT_SCHEMA_ALIAS_DRIFT", owner,
                            "docs/api-contract.md", doc["line"],
                            "Documented schema " + label(name) + " is not referenced by this operation.")
            responses = operation.get("responses", {})
            if not responses or not any(code.startswith("2") for code in responses):
                add("FAIL", "HIGH", "RESPONSE_STATUS", owner, "contracts/openapi.json", 0,
                    "Operation has no successful response status declaration.")
            if source and source["status"] not in responses:
                add("FAIL", "HIGH", "STALE_RESPONSE_STATUS", "T017", file, line,
                    "Declared production success status is absent from snapshot.")
            if doc and doc["statuses"]:
                for code in doc["statuses"]:
                    if code not in responses:
                        add("FAIL", "HIGH", "MISSING_DOCUMENTED_STATUS", owner,
                            "docs/api-contract.md", doc["line"],
                            "Documented status " + label(code) + " is absent from snapshot.")
                for code in sorted(responses):
                    if code.startswith("2") and code not in doc["statuses"]:
                        add("FAIL", "MEDIUM", "UNDOCUMENTED_SUCCESS_STATUS", owner, file, line,
                            "Exported success status " + label(code) + " is absent from endpoint table.")
            elif doc and not ancillary:
                add("PENDING", "MEDIUM", "DOCUMENTED_STATUS_UNRESOLVED", owner,
                    "docs/api-contract.md", doc["line"], "Endpoint table has no numeric success status.")
            error_responses = [response for code, response in responses.items()
                               if re.fullmatch(r"[45][0-9]{2}", code)]
            if not error_responses:
                add("FAIL", "HIGH", "MISSING_ERROR_ENVELOPE", owner, file, line,
                    "Exported operation has no error envelope declarations.")
            for response in error_responses:
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                resolved = dereference(schema, components)
                error = resolved.get("properties", {}).get("error", {})
                inner = dereference(error, components)
                if "error" not in resolved.get("required", []) or not {
                    "code", "message", "requestId"}.issubset(inner.get("required", [])):
                    add("FAIL", "HIGH", "INVALID_ERROR_ENVELOPE", owner, file, line,
                        "Error envelope must require error.code, error.message and error.requestId.")
            for section in (operation.get("requestBody", {}), *responses.values()):
                for content in section.get("content", {}).values():
                    self.check_refs(content.get("schema", {}), components, owner, file, line)
            if source and source["model"]:
                expected = "Operation" if source["model"] == "OperationView" else source["model"]
                response = responses.get(source["status"], {})
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                refs = {node["$ref"].rsplit("/", 1)[-1] for node in self.walk(schema)
                        if "$ref" in node}
                if expected not in refs:
                    add("FAIL", "HIGH", "STALE_RESPONSE_SCHEMA", "T017", file, line,
                        "Response model " + label(expected) + " does not match snapshot reference.")
            if source:
                if source["responses"] is None:
                    add("PENDING", "HIGH", "RAW_ERROR_DECLARATIONS", "T017", file, line,
                        "Route has no explicit responses mapping. Exporter-injected envelopes do not "
                        "prove production /openapi.json declares the documented errors.")
                self.compare_models(source, components, owner)
        for name, schema in sorted(components.items()):
            self.check_refs(schema, components, "T017", "contracts/openapi.json", 0)
        self.check_error_codes(api, implemented)
        self.compare_documented_schemas(declarations, examples, components, api, adr_text)
        limits_ready = self.check_caps(examples, constraints, api)
        if limits_ready:
            self.check_examples(examples, exported, components)
        else:
            add("PENDING", "HIGH", "LIMIT_CHECK_STOPPED", "T013", "docs/api-contract.md", 0,
                "Approved limit authority is missing/conflicting; affected example/bounds checks stopped.")
        self.check_snapshot_privacy(components)
        self.check_typescript(exported, components)
        self.index_coverage(spec)
        add("PENDING", "HIGH", "FULL_GENERATOR_REPRODUCIBILITY", "T017",
            "scripts/export_contract.py", 0,
            "Static route/model comparison does not prove full export or pinned TypeScript equality; "
            "test_full_schema_matches_checked_in and test_openapi_generation_is_deterministic remain owners.")
        add("PENDING", "HIGH", "RUNTIME_RELEASE_EVIDENCE", "T057", "docs/task-plan.md", 0,
            "Windows, browser, provider, performance, failure-injection and CP22 release evidence "
            "are not executed or certified by this static tool.")
        add("PENDING", "MEDIUM", "SCHEMA_VALIDATION_COVERAGE", "T044",
            "scripts/tests/test_audit_contract.py", 0,
            "Focused audit tests and full JSON Schema dialect/format validation remain unverified; "
            "static validation handles represented types, required fields, unions, bounds and patterns.")
        findings = sorted(set(self.findings), key=lambda item: (
            SEVERITIES[item.severity], item.status, item.check, item.owner, item.location, item.detail))
        violations = any(item.status in {"FAIL", "OWNER_DECISION_REQUIRED", "BLOCKED_SCOPE"}
                         for item in findings)
        pending = any(item.status == "PENDING" for item in findings)
        digest = hashlib.sha256()
        for path, text in sorted(sources.texts.items()):
            digest.update(path.encode("utf-8") + b"\0" + text.encode("utf-8") + b"\0")
        return {"tool": VERSION, "status": "FAIL" if violations else "PENDING" if pending else "PASS",
                "scope_digest": digest.hexdigest(), "inputs": sorted(sources.texts),
                "routes": self.route_index, "dependencies": self.dependencies,
                "coverage": self.coverage, "findings": [asdict(item) for item in findings],
                "runtime_evidence": "PENDING; source and test presence never imply execution"}

    @staticmethod
    def safe_path(path):
        return path if len(path) <= 200 and re.fullmatch(r"/[A-Za-z0-9_/{}/.-]*", path) else (
            "[redacted-route]")

    @staticmethod
    def walk(value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from Audit.walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from Audit.walk(item)

    def check_refs(self, schema, components, owner, file, line):
        for node in self.walk(schema):
            reference = node.get("$ref")
            if reference and (not reference.startswith("#/components/schemas/") or
                              reference.rsplit("/", 1)[-1] not in components):
                self.add("FAIL", "HIGH", "MISSING_SCHEMA_REFERENCE", owner, file, line,
                         "Missing or external schema reference; reference value withheld.")

    def check_error_codes(self, api, routes):
        """Compare literal public code declarations; dynamic error paths stay pending."""
        paths = sorted({route["source"] for route in routes.values()} |
                       {"backend/app/http/errors.py", "backend/app/main.py"})
        documented = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", api))
        for path in paths:
            catalogs = {id(node.value) for node in ast.walk(self.sources.tree(path))
                        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                            and target.id.endswith("MESSAGES") for target in node.targets)}
            for node in ast.walk(self.sources.tree(path)):
                codes = []
                if isinstance(node, ast.Dict) and id(node) in catalogs:
                    # The shared/local message catalogs are transport code declarations.
                    pairs = [(self.sources.literal(path, key), self.sources.literal(path, value))
                             for key, value in zip(node.keys, node.values, strict=True)]
                    codes = [key for key, value in pairs if isinstance(key, str) and
                             re.fullmatch(r"[A-Z][A-Z_]{2,}", key) and isinstance(value, str)]
                elif isinstance(node, ast.Call) and node_name(node.func) in {"error_response", "_error"}:
                    code = self.sources.literal(path, node.args[1]) if len(node.args) > 1 else None
                    if isinstance(code, str):
                        codes = [code]
                for code in sorted(set(codes)):
                    if code not in documented:
                        self.add("FAIL", "HIGH", "UNDOCUMENTED_ERROR_CODE", "T013", path, node.lineno,
                                 "Public error code " + label(code) + " is absent from the API contract.")
        self.add("PENDING", "MEDIUM", "DYNAMIC_ERROR_MAPPING", "T017",
                 "backend/app/http/errors.py", 0,
                 "Literal error catalogs are compared. Service-computed codes/statuses and response "
                 "branches require focused runtime envelope tests; exporter injections are insufficient.")

    def compare_models(self, route, components, owner):
        source = route["source"]
        names = {route["model"]} if route["model"] else set()
        for arg in route["function"].args.args + route["function"].args.kwonlyargs:
            for node in ast.walk(arg.annotation) if arg.annotation is not None else []:
                if isinstance(node, ast.Name):
                    found = self.sources.symbol(source, node.id)
                    if found and isinstance(found[1], ast.ClassDef):
                        if any(node_name(base) in {"BaseModel", "StrictModel"}
                               for base in found[1].bases):
                            names.add(node.id)
        queue = [(source, name) for name in sorted(names)]
        seen = set()
        while queue:
            module, name = queue.pop(0)
            found = self.sources.symbol(module, name)
            if not found or not isinstance(found[1], ast.ClassDef):
                self.add("PENDING", "MEDIUM", "MODEL_EXTRACTION", owner, source, route["line"],
                         "Model " + label(name) + " cannot be resolved statically.")
                continue
            path, definition = found
            if (path, definition.name) in seen:
                continue
            seen.add((path, definition.name))
            # Follow nested public model annotations without importing their modules.
            for field in definition.body:
                if not isinstance(field, ast.AnnAssign):
                    continue
                for node in ast.walk(field.annotation):
                    if isinstance(node, ast.Name):
                        child = self.sources.symbol(path, node.id)
                        if child and isinstance(child[1], ast.ClassDef):
                            if any(node_name(base) in {"BaseModel", "StrictModel", "Question"}
                                   for base in child[1].bases):
                                queue.append((path, node.id))
            exported_name = "Operation" if name == "OperationView" else name
            schema = components.get(exported_name)
            if not schema:
                self.add("FAIL", "HIGH", "MISSING_MODEL_SCHEMA", "T017", path, definition.lineno,
                         "Boundary model " + label(exported_name) + " is absent from snapshot.")
                continue
            fields = schema_fields(self.sources, path, definition)
            properties = schema.get("properties", {})
            transformed = any(isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                              and keyword(item.value, "json_schema_extra") is not None
                              for item in definition.body)
            drift_status = "PENDING" if transformed else "FAIL"
            if transformed:
                self.add("PENDING", "MEDIUM", "CUSTOM_SCHEMA_PROJECTION", "T017",
                         path, definition.lineno,
                         label(exported_name) + " uses json_schema_extra; annotation/schema differences "
                         "require the existing export/contract checks, not an assumed raw projection.")
            for field in sorted(set(fields) ^ set(properties)):
                self.add("FAIL", "HIGH", "STALE_SCHEMA_FIELD", "T017", path, definition.lineno,
                         label(exported_name) + "." + label(field) + " differs between model and snapshot.")
            for field in sorted(set(fields) & set(properties)):
                facts = fields[field]
                current = properties[field]
                prefix = label(exported_name) + "." + label(field)
                if "default" in current and ("default" not in facts or current["default"] != facts["default"]):
                    default_status = drift_status if "default" in facts else "PENDING"
                    self.add(default_status, "HIGH", "UNPROVEN_SCHEMA_DEFAULT", "T017", path, facts["line"],
                             prefix + " default has no matching literal source declaration; value withheld.")
                if facts["nullable"] != nullable(current, components):
                    self.add(drift_status, "HIGH", "STALE_SCHEMA_NULLABILITY", "T017", path, facts["line"],
                             prefix + " nullability differs between annotation and snapshot.")
                if facts["required"] != (field in schema.get("required", [])):
                    self.add(drift_status, "HIGH", "STALE_SCHEMA_REQUIRED", "T017", path, facts["line"],
                             prefix + " requiredness differs between declaration and snapshot.")
                if facts["enum"] and set(facts["enum"]) != set(schema_enum(current, components)):
                    self.add("FAIL", "HIGH", "STALE_SCHEMA_ENUM", "T017", path, facts["line"],
                             prefix + " enum members differ; values withheld.")
                for bound, value in sorted(facts["bounds"].items()):
                    target = {"ge": "minimum", "le": "maximum", "gt": "exclusiveMinimum",
                              "lt": "exclusiveMaximum", "min_length": "minItems" if
                              facts.get("type") == "array" else "minLength", "max_length":
                              "maxItems" if facts.get("type") == "array" else "maxLength"}.get(bound)
                    candidates = [current] + current.get("anyOf", [])
                    if target and not any(item.get(target) == value for item in candidates):
                        self.add("FAIL", "HIGH", "STALE_SCHEMA_BOUND", "T017", path, facts["line"],
                                 prefix + " " + target + " differs from source Field constraint.")

    def compare_documented_schemas(self, declarations, examples, components, api, adrs):
        named_examples = {example.get("name", "") for example in examples}
        aliases_reverse = {target: alias for alias, target in ALIASES.items()}
        for name, schema in sorted(components.items()):
            alias = aliases_reverse.get(name, name)
            doc = declarations.get(name) or declarations.get(alias)
            mentioned = re.search(r"\b" + re.escape(name) + r"\b", api)
            if not doc and alias not in named_examples and not mentioned:
                self.add("FAIL", "MEDIUM", "UNDOCUMENTED_SCHEMA", "T013",
                         "contracts/openapi.json", 0,
                         "Schema " + label(name) + " has no named contract declaration or example.")
            if not doc:
                if schema.get("properties"):
                    self.add("PENDING", "MEDIUM", "SCHEMA_FIELD_DOCUMENTATION", "T013",
                             "contracts/openapi.json", 0,
                             "Schema " + label(name) + " lacks an exhaustive field declaration; "
                             "examples alone cannot document all optional/nullable/enum semantics.")
                continue
            properties = schema.get("properties", {})
            declared = doc["fields"]
            for field in sorted(set(properties) - set(declared)):
                self.add("FAIL", "MEDIUM", "UNDOCUMENTED_FIELD", "T013",
                         "docs/api-contract.md", doc["line"],
                         label(alias) + "." + label(field) + " exists in snapshot but not declaration.")
            for field in sorted(set(declared) - set(properties)):
                self.add("FAIL", "HIGH", "MISSING_DOCUMENTED_FIELD", "T013",
                         "docs/api-contract.md", doc["line"],
                         label(alias) + "." + label(field) + " is declared but absent from schema.")
            for field in sorted(set(declared) & set(properties)):
                current = properties[field]
                text = declared[field]["type"]
                prefix = label(alias) + "." + label(field)
                if nullable(current, components) and "null" not in text:
                    # Prose may clarify a compact declaration; lack of a local nullable marker
                    # cannot establish a contradiction with a later ADR.
                    self.add("PENDING", "MEDIUM", "UNDOCUMENTED_NULLABILITY", "T013",
                             "docs/api-contract.md", doc["line"],
                             prefix + " accepts null; compact declaration lacks explicit null semantics. "
                             "Resolve against field-specific prose/ADR before changing the contract.")
                if "null" in text and not nullable(current, components):
                    self.add("FAIL", "HIGH", "MISSING_DOCUMENTED_NULLABILITY", "T013",
                             "docs/api-contract.md", doc["line"],
                             prefix + " declares null but snapshot rejects it.")
                values = schema_enum(current, components)
                explicit = re.findall(r"\b[A-Z][A-Z_]+\b", text)
                if values and explicit:
                    missing = [v for v in values if isinstance(v, str) and v not in explicit]
                    extra = [v for v in explicit if v not in values]
                    if missing or extra:
                        self.add("FAIL", "HIGH", "DOCUMENTED_ENUM_DRIFT", "T013",
                                 "docs/api-contract.md", doc["line"],
                                 prefix + " enum differs from explicit field declaration; values withheld.")
                elif values and any(isinstance(v, str) and v not in api + adrs for v in values):
                    self.add("FAIL", "MEDIUM", "UNDOCUMENTED_ENUM", "T013",
                             "docs/api-contract.md", doc["line"],
                             prefix + " has enum members absent from contract and applicable ADRs.")
                elif values:
                    self.add("PENDING", "MEDIUM", "ENUM_FIELD_BINDING", "T013",
                             "docs/api-contract.md", doc["line"],
                             prefix + " enum tokens occur in documentation but need a field-specific binding.")
        for name, doc in sorted(declarations.items()):
            if name not in components and ALIASES.get(name) not in components:
                self.add("FAIL", "HIGH", "DOCUMENTED_SCHEMA_MISSING", "T013",
                         "docs/api-contract.md", doc["line"],
                         "Declared schema/alias " + label(name) + " has no generated component.")
        # ErrorDetails' compact union is not a named object declaration.
        details = components.get("ErrorDetails", {})
        kinds = {v for node in self.walk(details) for v in schema_enum(
            node.get("properties", {}).get("kind", {}), components) if isinstance(v, str)}
        for branch in details.get("anyOf", []):
            kinds.update(schema_enum(dereference(branch, components).get("properties", {}).get(
                "kind", {}), components))
        documented_kinds = set(re.findall(r"kind:\s*([A-Z_]+)", api))
        if kinds != documented_kinds:
            self.add("FAIL", "HIGH", "ERROR_DETAILS_UNION_DRIFT", "T013",
                     "docs/api-contract.md", 0,
                     "ErrorDetails.kind variants differ between documented union and generated envelope.")

    def check_examples(self, examples, routes, components):
        for example in examples:
            line = example["line"]
            if "sensitive_header" in example:
                self.add("FAIL", "CRITICAL", "EXAMPLE_CREDENTIAL_HEADER", "T006",
                         "docs/api-contract.md", line,
                         "Credential header " + label(example["sensitive_header"]) +
                         " is not an explicit redacted placeholder; value withheld.")
                continue
            if "query" in example:
                operation = routes.get(example["route"], {})
                parameters = {item.get("name"): item.get("schema", {})
                              for item in operation.get("parameters", []) if item.get("in") == "query"}
                for field, raw in example["query"]:
                    if field not in parameters:
                        self.add("FAIL", "HIGH", "EXAMPLE_QUERY_FIELD", "T013",
                                 "docs/api-contract.md", line,
                                 "Query parameter " + label(field) + " is absent from operation schema.")
                        continue
                    schema = parameters[field]
                    types = [schema.get("type")] + [item.get("type") for item in schema.get("anyOf", [])]
                    value = raw
                    if "integer" in types and re.fullmatch(r"-?[0-9]+", raw):
                        value = int(raw)
                    elif "boolean" in types and raw in {"true", "false"}:
                        value = raw == "true"
                    for pointer, category in example_errors(value, schema, components, "$query." + label(field)):
                        self.add("FAIL", "HIGH", "EXAMPLE_QUERY_BOUND", "T013",
                                 "docs/api-contract.md", line, pointer + ": " + category + ".")
                continue
            if example.get("invalid"):
                self.add("FAIL", "HIGH", "INVALID_JSON_EXAMPLE", "T013",
                         "docs/api-contract.md", line, "Fenced example is not valid JSON.")
                continue
            name = example.get("name", "")
            schema_name = ALIASES.get(name, name)
            schema = components.get(schema_name)
            key = example.get("route")
            operation = routes.get(key, {})
            if schema is None and operation:
                part = operation.get("responses", {}).get(example.get("status"), {}) if (
                    example.get("status")) else operation.get("requestBody", {})
                schema = part.get("content", {}).get("application/json", {}).get("schema")
            if schema is None and name == "Page<T>":
                schema = components.get("SearchPage")
            value = example["value"]
            owner = route_owner(key[1], key[0]) if key else "T013"
            if schema is None and isinstance(value, dict) and "readiness" in value and "localMetrics" in value:
                schema = components.get("StatusSummary")
                name = "StatusSummary"
                owner = "T046"
            if schema is None and isinstance(value, dict) and "feedbackId" in value:
                schema = components.get("Feedback")
                name = "Feedback"
                owner = "T049"
            if schema is None and isinstance(value, dict) and "data" in value and "pagination" in value:
                schema = components.get("WordFormCollection")
                owner = "T027"
            if schema is None:
                self.add("PENDING", "MEDIUM", "EXAMPLE_SCHEMA_BINDING", owner,
                         "docs/api-contract.md", line,
                         "Example " + label(name or "unnamed") + " has no proven schema binding.")
            else:
                errors = example_errors(value, schema, components)
                if isinstance(value, dict) and "counts" in value:
                    counts = value["counts"]
                    valid = isinstance(counts, dict) and set(counts) == {"mcq", "cloze", "writing"}
                    valid = valid and all(type(n) is int and 0 <= n <= 20 for n in counts.values())
                    valid = valid and 5 <= sum(counts.values()) <= 30
                    if not valid:
                        errors.append(("$.counts", "approved-quiz-count-violation"))
                if example.get("negative"):
                    status = "PASS" if errors else "FAIL"
                    self.add(status, "INFO" if errors else "HIGH", "NEGATIVE_EXAMPLE", owner,
                             "docs/api-contract.md", line,
                             "Explicit negative fixture is rejected." if errors else
                             "Explicit negative fixture unexpectedly conforms to represented schema.")
                elif errors:
                    for pointer, category in sorted(set(errors)):
                        status = "PENDING" if category.endswith("unresolved") else "FAIL"
                        self.add(status, "HIGH", "EXAMPLE_SCHEMA", owner,
                                 "docs/api-contract.md", line, pointer + ": " + category + ".")
                else:
                    self.add("PASS", "INFO", "EXAMPLE_REPRESENTED_SCHEMA", owner,
                             "docs/api-contract.md", line,
                             "Example conforms to the represented static schema subset only.")
            diagnostic = name in {"StatusSummary", "Operation", "HealthSummary"} or bool(
                key and any(part in key[1].split("/") for part in {"status", "operations", "health"}))
            for pointer, category in sorted(set(privacy_errors(value, diagnostic))):
                self.add("FAIL", "CRITICAL", "EXAMPLE_PRIVACY", owner,
                         "docs/api-contract.md", line, pointer + ": " + category + "; values withheld.")
            if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 1048576:
                self.add("FAIL", "HIGH", "EXAMPLE_BODY_LIMIT", "T006",
                         "docs/api-contract.md", line, "Example body exceeds the 1 MiB JSON cap.")

    def check_snapshot_privacy(self, components):
        queue = [(name, schema, name in {"StatusSummary", "Operation", "HealthSummary", "LocalAlert",
                                        "LocalMetricsSummary"},
                  name in {"MCQQuestion", "ClozeQuestion", "WritingQuestion"})
                 for name, schema in sorted(components.items())]
        seen = set()
        while queue:
            name, schema, diagnostic, public = queue.pop(0)
            marker = (name, diagnostic, public)
            if marker in seen:
                continue
            seen.add(marker)
            schema = dereference(schema, components)
            for field, child in sorted(schema.get("properties", {}).items()):
                normalized = re.sub(r"[^a-z]", "", field.lower())
                forbidden = normalized in FORBIDDEN_FIELDS and not (
                    name == "BootstrapExchange" and normalized == "token")
                if forbidden or (diagnostic and normalized in DIAGNOSTIC_FIELDS) or (
                    public and normalized in {"correctoptionid", "acceptedanswers", "explanationvi"}):
                    self.add("FAIL", "CRITICAL", "RESPONSE_SCHEMA_PRIVACY", "T013",
                             "contracts/openapi.json", 0,
                             label(name) + "." + label(field) + " exposes sensitive boundary content.")
                for node in self.walk(child):
                    if "$ref" in node:
                        target = node["$ref"].rsplit("/", 1)[-1]
                        if target in components:
                            queue.append((target, components[target], diagnostic, public))
        for name, schema in sorted(components.items()):
            for node in self.walk(schema):
                if "default" in node:
                    self.add("PENDING", "MEDIUM", "DEFAULT_PROVENANCE", "T017",
                             "contracts/openapi.json", 0,
                             "Schema " + label(name) + " contains a default requiring source/contract provenance; "
                             "the checker never inserts defaults into examples.")
                for key in ("example", "examples"):
                    if key in node:
                        for pointer, category in privacy_errors(node[key]):
                            self.add("FAIL", "CRITICAL", "SCHEMA_EXAMPLE_PRIVACY", "T013",
                                     "contracts/openapi.json", 0,
                                     label(name) + pointer + ": " + category + "; values withheld.")

    def check_caps(self, examples, constraints, api):
        capabilities = next((item for item in examples if item.get("name") == "Capabilities"), None)
        if not capabilities:
            self.add("FAIL", "HIGH", "CAPABILITIES_FIXTURE", "T013",
                     "docs/api-contract.md", 0, "Approved limit fixture is missing.")
            return False
        value = capabilities["value"]
        ready = True
        for field, expected in sorted(CAPS.items()):
            if value.get("limits", {}).get(field) != expected:
                ready = False
                self.add("OWNER_DECISION_REQUIRED", "HIGH", "APPROVED_LIMIT_CONFLICT", "T013",
                         "docs/api-contract.md", capabilities["line"],
                         "Capabilities.limits." + field + " conflicts with C013-08/CONSTRAINTS defaults.")
        if value.get("operationDeadlinesSeconds") != {"lookup": 120, "quizGeneration": 60,
                                                     "writingFeedback": 30}:
            ready = False
            self.add("OWNER_DECISION_REQUIRED", "HIGH", "DEADLINE_CONFLICT", "T013",
                     "docs/api-contract.md", capabilities["line"],
                     "Operation deadline fixture conflicts with approved 120/60/30-second policy.")
        for fragment in ("4,096", "1 MiB", "8 MiB", "4 MiB"):
            if fragment not in constraints:
                ready = False
                self.add("PENDING", "HIGH", "LIMIT_AUTHORITY_CHANGED", "T013",
                         "CONSTRAINTS.md", 0,
                         "Limit authority wording changed; reconcile C013-08 before evaluating fixed defaults.")
        if "pageSize=50" not in api:
            self.add("PENDING", "MEDIUM", "PAGINATION_DEFAULT", "T013", "docs/api-contract.md", 0,
                     "Default page size authority requires clarification; no default fabricated.")
        self.add("PENDING", "HIGH", "RUNTIME_BOUNDS", "T006", "CONSTRAINTS.md", 0,
                 "Streamed UTF-8 bytes, normalized strings, validator-only limits, collection limits "
                 "and exact deadline admission require boundary/max+1 tests; source metadata is insufficient.")
        return ready

    def check_typescript(self, routes, components):
        path = "frontend/src/shared/api/generated.ts"
        text = self.sources.read(path)
        ts_paths = {normalized_path(value) for value in re.findall(r'^    "(/[^\"]+)":', text,
                                                                  re.MULTILINE)}
        expected = {key[1] for key in routes}
        if ts_paths != expected:
            self.add("FAIL", "HIGH", "STALE_TYPESCRIPT_PATHS", "T017", path, 0,
                     "Generated TypeScript path inventory differs from checked OpenAPI.")
        schemas = text.split("    schemas: {", 1)
        if len(schemas) != 2:
            self.add("FAIL", "HIGH", "TYPESCRIPT_SCHEMA_INDEX", "T017", path, 0,
                     "Generated TypeScript schema section is missing or unsupported.")
            return
        section = schemas[1].split("\n    };", 1)[0]
        names = set(re.findall(r"^        ([A-Za-z_][A-Za-z0-9_]*):", section, re.MULTILINE))
        if names != set(components):
            self.add("FAIL", "HIGH", "STALE_TYPESCRIPT_SCHEMAS", "T017", path, 0,
                     "Generated TypeScript schema names differ from checked OpenAPI.")
        declarations = list(re.finditer(r"^        ([A-Za-z_][A-Za-z0-9_]*):", section, re.MULTILINE))
        for index, declaration in enumerate(declarations):
            name = declaration[1]
            schema = components.get(name, {})
            if schema.get("type") != "object" or any(key in schema for key in ("anyOf", "oneOf", "allOf")):
                continue
            end = declarations[index + 1].start() if index + 1 < len(declarations) else len(section)
            body = section[declaration.end():end]
            fields = {match[1]: (bool(match[2]), match[3]) for match in re.finditer(
                r"^            ([A-Za-z_][A-Za-z0-9_]*)(\?)?: ([^\n]+)", body, re.MULTILINE)}
            if set(fields) != set(schema.get("properties", {})):
                self.add("FAIL", "HIGH", "STALE_TYPESCRIPT_FIELDS", "T017", path, 0,
                         "Generated TypeScript fields for " + label(name) + " differ from OpenAPI.")
            for field in sorted(set(fields) & set(schema.get("properties", {}))):
                optional, field_type = fields[field]
                if optional == (field in schema.get("required", [])):
                    self.add("FAIL", "HIGH", "STALE_TYPESCRIPT_REQUIRED", "T017", path, 0,
                             label(name) + "." + label(field) + " optionality differs from OpenAPI.")
                current = schema["properties"][field]
                if current.get("type") == "object":
                    continue
                if ("null" in re.findall(r"\bnull\b", field_type)) != nullable(current, components):
                    self.add("FAIL", "HIGH", "STALE_TYPESCRIPT_NULLABILITY", "T017", path, 0,
                             label(name) + "." + label(field) + " nullability differs from OpenAPI.")

    def index_coverage(self, spec):
        sources = self.sources
        requirements = requirement_ids(spec)
        cards = {}
        for path in sources.glob("tasks/t[0-9][0-9][0-9]-*.md"):
            text = sources.read(path)
            task = "T" + Path(path).name[1:4]
            if task in cards:
                self.add("PENDING", "MEDIUM", "TASK_CARD_ALIAS", task, path, 0,
                         "Multiple cards share a task ID; canonical ownership needs confirmation.")
                continue
            paths = sorted({p.rstrip(".") for p in re.findall(
                r"(?:backend|frontend|scripts|docs)/[A-Za-z0-9_./*-]+", text)
                if ".." not in p.split("/")})
            implementation = [p for p in paths if p.startswith(("backend/app/", "frontend/src/"))
                              and "*" not in p and (sources.root / p).is_file()]
            tests = [p for p in paths if "/tests/" in p and "*" not in p]
            test_index = []
            for test in tests:
                if not (sources.root / test).is_file():
                    self.add("PENDING", "HIGH", "MISSING_FOCUSED_TEST", task, path, 0,
                             "Referenced focused test " + test + " is absent; no execution evidence.")
                    continue
                names = []
                if test.endswith(".py"):
                    names = sorted({node.name for node in ast.walk(sources.tree(test)) if
                                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                    and node.name.startswith("test_")})
                    names = [label(name) for name in names]
                test_index.append({"path": test, "tests": names, "execution": "PENDING"})
            evidence = [p for p in paths if p.startswith("docs/reviews/") and
                        (sources.root / p).is_file() and p != REPORT]
            cards[task] = {"card": path, "requirements": requirement_ids(text),
                           "implementation": implementation, "tests": test_index,
                           "evidence_references": evidence}
            if task in DEPENDENCIES:
                status = re.search(r"^\*\*Status:\*\*\s*`([^`]+)`", text, re.MULTILINE)
                declared = status[1] if status and re.fullmatch(r"[A-Z_ ()]+", status[1]) else "UNRESOLVED"
                self.dependencies.append({"task": task, "declared_status": declared,
                    "implementation": implementation, "tests": test_index,
                    "evidence_references": evidence, "runtime": "PENDING"})
                if task != "T013" and not implementation:
                    self.add("PENDING", "HIGH", "DEPENDENCY_IMPLEMENTATION", task, path, 0,
                             "No existing implementation path can be confirmed from the task card.")
                self.add("PENDING", "HIGH", "DEPENDENCY_ACCEPTANCE", task, path, 0,
                         "Card/source/test references are indexed, not current-head runtime acceptance. "
                         "Historical results and coding-only closure do not certify this audit input state.")
                for ref in evidence:
                    sources.read(ref)
        for dependency in DEPENDENCIES:
            if dependency not in cards:
                self.add("PENDING", "HIGH", "DEPENDENCY_CARD_MISSING", dependency, "tasks", 0,
                         "Required dependency card is absent; ownership evidence unavailable.")
        for requirement in sorted(requirements):
            owners = [task for task, card in sorted(cards.items())
                      if requirement in card["requirements"]]
            mappings = []
            for task in owners:
                card = cards[task]
                mappings.append({"task": task, "card": card["card"],
                    "implementation": card["implementation"], "tests": card["tests"],
                    "contract": self.contracts_by_task.get(task, []),
                    "verification_owner": task,
                    "contract_binding": "STATIC_TASK_ROUTE_ASSOCIATION; per-FR/AC oracle PENDING",
                    "evidence_references": card["evidence_references"], "runtime": "PENDING"})
            if not owners:
                self.add("FAIL", "HIGH", "REQUIREMENT_TASK_GAP", "T013", "docs/spec.md", 0,
                         requirement + " has no explicit task-card reference; assign an owner.")
            elif not any(mapping["tests"] for mapping in mappings):
                self.add("PENDING", "HIGH", "REQUIREMENT_TEST_GAP", ",".join(owners),
                         "docs/spec.md", 0,
                         requirement + " has owners but no existing focused test reference; "
                         "UI/manual/platform verification owner must provide evidence.")
            self.coverage.append({"requirement": requirement, "mappings": mappings})
        for task, card in sorted(cards.items()):
            for reference in sorted(set(re.findall(r"\bT\d{3}\b", sources.read(card["card"])))):
                if reference not in cards:
                    self.add("FAIL", "MEDIUM", "STALE_TASK_REFERENCE", task, card["card"], 0,
                             "Referenced task " + reference + " has no canonical task card.")
        self.dependencies.sort(key=lambda item: item["task"])
        self.add("PENDING", "HIGH", "OBSERVABILITY_EVIDENCE", "T061",
                 "docs/reviews/observability-evidence-001.md", 0,
                 "Qualified search-latency producer, launcher health probes (T039), consumer semantic "
                 "validation and pinned DTO generator reproducibility remain explicit verification owners.")


def render_report(result):
    lines = ["# Contract conformance 003 — T044", "", "Tool: `" + VERSION + "`", "",
             "Status: `" + result["status"] + "` (static findings only; release acceptance PENDING)",
             "", "Input scope fingerprint: `" + result.get("scope_digest", "UNAVAILABLE") + "`", "",
             "No application imports, provider calls, user data, tests, generators or runtime probes. "
             "PASS applies only to its named static check; it never implies test or release acceptance.",
             "", "## Deterministic input scope", ""]
    lines.extend("- `" + path + "`" for path in result.get("inputs", []))
    lines += ["", "## Result meanings", "",
              "PASS: available evidence for the named static check only. FAIL: deterministic violation. "
              "PENDING: missing extraction/runtime/tool/platform evidence. OWNER_DECISION_REQUIRED: "
              "conflicting product authorities; affected checks stop. BLOCKED_SCOPE: required write "
              "outside the allowlist or unsafe report destination; no workaround or contract edit.",
              "", "## Findings by severity", ""]
    for severity in SEVERITIES:
        lines += ["### " + severity, "", "| Status | Check | Owner | Location | Discrepancy / action |",
                  "|---|---|---|---|---|"]
        items = [item for item in result["findings"] if item["severity"] == severity]
        for item in items:
            cells = [item[field] for field in ("status", "check", "owner", "location", "detail")]
            lines.append("| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ")
                                           for cell in cells) + " |")
        if not items:
            lines.append("| — | — | — | — | No findings in this severity; no runtime assertion. |")
        lines.append("")
    lines += ["## Implemented and documented surfaces", "",
              "| Method | Normalized path | Classification | Owner | Implementation | Documentation |",
              "|---|---|---|---|---|---|"]
    for route in result.get("routes", []):
        lines.append("| " + " | ".join(route[key] for key in ("method", "path", "classification",
            "owner", "implementation", "documentation")) + " |")
    lines += ["", "## Dependency and runtime evidence", ""]
    for dependency in result.get("dependencies", []):
        lines.append("- `" + dependency["task"] + "`: declared `" + dependency["declared_status"] +
                     "`; runtime `PENDING`. Source/test/evidence paths are references, not passing results.")
    lines += ["", "## FR/AC coverage index", "",
              "Full source, schema-binding and focused-test references are in `--json` output. "
              "All per-requirement runtime evidence remains PENDING.", "",
              "| Requirement | Responsible tasks | Implementation references | Focused test references | Runtime |",
              "|---|---|---|---|---|"]
    for item in result.get("coverage", []):
        owners = sorted({mapping["task"] for mapping in item["mappings"]})
        paths = sorted({path for mapping in item["mappings"] for path in mapping["implementation"]})
        tests = sorted({test["path"] for mapping in item["mappings"] for test in mapping["tests"]})
        lines.append("| " + " | ".join((item["requirement"], ", ".join(owners) or "MISSING",
            ", ".join(paths) or "MISSING", ", ".join(tests) or "PENDING", "PENDING")) + " |")
    lines += ["", "## Files intentionally untouched", "",
              "Application/backend/frontend source, tests, snapshots, DTOs, API/spec documents, ADRs, "
              "constraints, CI, dependencies, other review status, credentials and vocabulary data.", "",
              "## Required follow-up", "",
              "T044: focused positive/negative audit tests; T017: fresh OpenAPI and pinned TypeScript "
              "equality; T013 and named feature owners: resolve documented drift without automatic edits; "
              "T057: Windows/browser/provider/performance acceptance and CP22. "
              "OWNER_DECISION_REQUIRED stops the affected semantic check. Fixes outside the T044 "
              "allowlist require a separate owner task; this tool never applies them.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit deterministic structured evidence")
    mode.add_argument("--write-report", action="store_true", help="Write only the T044 report")
    args = parser.parse_args()
    audit = Audit(args.root)
    try:
        result = audit.run()
    except (OSError, ValueError, SyntaxError, TypeError, KeyError, AttributeError, RecursionError):
        # Do not print exception messages: they can contain input values or host paths.
        prior = [asdict(item) for item in sorted(set(audit.findings), key=lambda item: (
            SEVERITIES[item.severity], item.status, item.check, item.owner, item.location, item.detail))]
        result = {"tool": VERSION, "status": "FAIL" if any(item["status"] in {
            "FAIL", "OWNER_DECISION_REQUIRED", "BLOCKED_SCOPE"} for item in prior) else "PENDING",
                  "inputs": sorted(audit.sources.texts),
                  "findings": prior + [asdict(Finding("PENDING", "HIGH", "INPUT_EXTRACTION", "T044",
                     "repository inputs", "Required source could not be read/parsed; no clean result. "
                     "Check source availability/encoding/shape with the responsible owner."))]}
    output = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n" if args.json else (
        render_report(result))
    if args.write_report:
        target = audit.sources.root / REPORT
        try:
            unsafe_parent = any(parent.is_symlink() for parent in target.parents
                                if parent != audit.sources.root
                                and parent.is_relative_to(audit.sources.root))
            if (target.is_symlink() or unsafe_parent
                    or not target.parent.resolve().is_relative_to(audit.sources.root)
                    or (target.exists() and target.stat().st_nlink != 1)):
                print("BLOCKED_SCOPE: unsafe report destination; no report written.", file=sys.stderr)
                return 1
            target.write_text(output, encoding="utf-8")
        except OSError:
            print("BLOCKED_SCOPE: report destination unavailable; no report certified.", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(output)
    if result["status"] == "PASS":
        return 0
    return 1 if result["status"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
