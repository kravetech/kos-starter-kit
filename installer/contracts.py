"""Small explicit schema subset; no network resolution or executable schemas."""
from __future__ import annotations

import re
import datetime
from safety import Blocked, ROOT, json_read

RELEASE = json_read(ROOT / "installer/release.json")
OWNERS = {"managed", "managed-customizable", "user-owned", "generated", "runtime", "extension-owned"}
CLASSIFICATIONS = ["MISSING", "IDENTICAL", "COMPATIBLE_EXISTING", "OLDER_MANAGED", "USER_MODIFIED", "PATH_CONFLICT", "SEMANTIC_DUPLICATE", "VERSION_CONFLICT", "CONFIG_CONFLICT", "DEPENDENCY_CONFLICT", "SECURITY_CONFLICT", "RESERVED_PATH_CONFLICT", "UNKNOWN", "BLOCKED"]
EDITION_ALIASES = {"starter": "community", "core": "pro"}


def canonical_edition(value):
    """Map pre-hierarchy edition identifiers to the finalized public names."""
    return EDITION_ALIASES.get(value, value)


def supports_edition(supported, edition):
    """Compare canonical editions while continuing to read legacy manifests."""
    wanted = canonical_edition(edition)
    return any(canonical_edition(item) == wanted for item in supported)


def validate(value, schema, location="$"):
    supported = {"$schema", "$id", "title", "description", "default", "examples", "deprecated", "type", "required", "properties", "additionalProperties", "enum", "const", "items", "uniqueItems", "minItems", "maxItems", "pattern", "minLength", "maxLength", "minimum", "maximum", "format"}
    if not isinstance(schema, dict) or set(schema) - supported:
        raise Blocked("SCHEMA_UNSUPPORTED_KEYWORD:" + location)
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float), "null": type(None)}
    kind = schema.get("type")
    if kind and (kind not in kinds or not isinstance(value, kinds[kind]) or kind in {"integer", "number"} and isinstance(value, bool)):
        raise Blocked("SCHEMA_TYPE:" + location)
    if "enum" in schema and value not in schema["enum"]:
        raise Blocked("SCHEMA_ENUM:" + location)
    if "const" in schema and value != schema["const"]:
        raise Blocked("SCHEMA_CONST:" + location)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise Blocked("SCHEMA_REQUIRED:" + location + "." + key)
        for key, item in value.items():
            child = schema.get("properties", {}).get(key)
            if child is not None:
                validate(item, child, location + "." + key)
            elif schema.get("additionalProperties") is False:
                raise Blocked("SCHEMA_UNKNOWN:" + location)
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(item, schema["additionalProperties"], location + "." + key)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise Blocked("SCHEMA_ARRAY_EMPTY:" + location)
        if len(value) > schema.get("maxItems", len(value)):
            raise Blocked("SCHEMA_ARRAY_LENGTH:" + location)
        if schema.get("uniqueItems") and len({repr(item) for item in value}) != len(value):
            raise Blocked("SCHEMA_DUPLICATE:" + location)
        for item in value:
            validate(item, schema.get("items", {}), location + "[]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)) or "pattern" in schema and not re.search(schema["pattern"], value):
            raise Blocked("SCHEMA_STRING:" + location)
        if "format" in schema:
            if schema["format"] != "date":
                raise Blocked("SCHEMA_UNSUPPORTED_FORMAT:" + location)
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError()
                datetime.date.fromisoformat(value)
            except ValueError as error:
                raise Blocked("SCHEMA_DATE:" + location) from error
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            raise Blocked("SCHEMA_NUMBER_RANGE:" + location)


def check(name, value):
    validate(value, json_read(ROOT / "installer/schemas" / (name + ".schema.json")))


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise Blocked("VERSION_INVALID")
    return tuple(map(int, value.split(".")))


def compatible(spec, current):
    check("compatibility", spec)
    return version(spec["min"]) <= version(current) < version(spec["maxExclusive"])
