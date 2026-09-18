"""Static, provenance-bearing Swin configuration inspection, never imports the repo."""

import ast
import posixpath
import re

import yaml

from .schema import ToolInputError


def attribute_path(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = attribute_path(node.value)
        return parent + "." + node.attr if parent else None
    return None


def decoded_override(value: str):
    if not isinstance(value, str) or len(value) > 1024:
        raise ToolInputError("Override values must be bounded strings")
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def trace_config(
    corpus,
    config_path: str,
    field: str,
    opts: list[str],
    cli: dict,
    *,
    user_arguments_verified=False,
):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+", field):
        raise ToolInputError("Use an exact uppercase dotted configuration field")
    if len(opts) > 20 or len(opts) % 2 or len(cli) > 10:
        raise ToolInputError("Overrides exceed bounds or are not key/value pairs")
    candidates = sorted(
        {
            r["source_path"]
            for r in corpus.registry.values()
            if r["source_type"] == "config"
            and corpus.allowed(r)
            and (
                r["source_path"] == config_path
                or posixpath.basename(r["source_path"]) == config_path
            )
        }
    )
    if config_path and len(candidates) != 1:
        raise ToolInputError(
            "Configuration filename must resolve to exactly one eligible file"
        )
    if config_path:
        config_path = candidates[0]
        directory = config_path.split("/configs/")[0]
        default_path = directory + "/config.py"
    else:
        defaults = sorted(
            {
                r["source_path"]
                for r in corpus.registry.values()
                if r["source_type"] == "code"
                and r["source_path"].endswith("/config.py")
                and corpus.allowed(r)
            }
        )
        if len(defaults) != 1:
            raise ToolInputError(
                "Default source must resolve to exactly one eligible config.py"
            )
        default_path = defaults[0]
    chain, evidence, warnings = [], {}, []
    value, known = None, False

    def record(stage, path, line, new_value):
        nonlocal value, known
        proof = corpus.at_line(path, line)
        if not proof:
            warnings.append(f"No eligible original chunk covers {path}:{line}")
            known = False
            return
        evidence.update({e.chunk_id: e for e in proof})
        value, known = new_value, True
        chain.append(
            {
                "stage": stage,
                "value": new_value,
                "source_path": path,
                "line": line,
                "chunk_ids": [e.chunk_id for e in proof],
            }
        )

    try:
        tree = ast.parse(corpus.source_text(default_path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                attribute_path(t) == "_C." + field for t in node.targets
            ):
                try:
                    record(
                        "default",
                        default_path,
                        node.lineno,
                        ast.literal_eval(node.value),
                    )
                except (ValueError, SyntaxError):
                    warnings.append(
                        "Default value uses an unsupported dynamic expression"
                    )
    except ToolInputError:
        warnings.append("Default configuration source is unavailable in this scope")

    visiting = set()

    def apply_file(path, depth=0):
        if path in visiting or depth >= 12:
            raise ToolInputError("BASE configuration cycle or excessive depth")
        visiting.add(path)
        text = corpus.source_text(path)
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict) or not isinstance(data.get("BASE", []), list):
            raise ToolInputError("Expected a YAML mapping and BASE list")
        for base in data.get("BASE", []):
            if not isinstance(base, str):
                raise ToolInputError("BASE entries must be filenames")
            if base:
                parent = posixpath.normpath(
                    posixpath.join(posixpath.dirname(path), base)
                )
                apply_file(parent, depth + 1)
        node = yaml.compose(text)
        current = data
        for part in field.split("."):
            if not isinstance(current, dict) or part not in current:
                break
            current = current[part]
            if not isinstance(node, yaml.MappingNode):
                break
            node = next((v for k, v in node.value if k.value == part), None)
        else:
            if node is not None:
                record("yaml", path, node.start_mark.line + 1, current)
        visiting.remove(path)

    if config_path:
        apply_file(config_path)
    override_source = (
        "user_argument"
        if user_arguments_verified
        else "caller_supplied_claim_requires_review"
    )
    if (opts or cli) and not user_arguments_verified:
        warnings.append(
            "Override values are unverified caller claims, not confirmed user arguments"
        )
    for key, raw in zip(opts[::2], opts[1::2], strict=True):
        if key == field:
            candidate = decoded_override(raw)
            if known and type(candidate) != type(value):
                raise ToolInputError("Override type differs from the static field type")
            value, known = candidate, True
            chain.append(
                {
                    "stage": "opts",
                    "value": value,
                    "source": override_source,
                    "chunk_ids": [],
                }
            )
    cli_fields = {
        "batch_size": "DATA.BATCH_SIZE",
        "accumulation_steps": "TRAIN.ACCUMULATION_STEPS",
        "resume": "MODEL.RESUME",
        "pretrained": "MODEL.PRETRAINED",
    }
    for key, candidate in cli.items():
        if key not in cli_fields:
            warnings.append(f"Unsupported CLI argument: {key}")
        elif cli_fields[key] == field and candidate:
            if known and type(candidate) != type(value):
                raise ToolInputError(
                    "CLI override type differs from the static field type"
                )
            value, known = candidate, True
            chain.append(
                {
                    "stage": "specific_cli",
                    "value": value,
                    "source": override_source,
                    "chunk_ids": [],
                }
            )
    for structure in ["_update_config_from_file", "update_config"]:
        for item in corpus.read("", structure, default_path):
            evidence[item.chunk_id] = item
    return {
        "kind": "configuration_trace",
        "field": field,
        "final_value": value if known else None,
        "status": "partial" if warnings or not known else "traced",
        "chain": chain,
        "warnings": warnings,
        "execution": "static_only",
        "config_path": config_path,
    }, list(evidence.values())
