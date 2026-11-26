"""Update only recognized release information in an existing user's document."""
import codecs
import json
from pathlib import Path
import re


RULES = json.loads(Path(__file__).with_name("community-document-rules.json").read_bytes())


def inside_code_fence(prefix):
    opening = ""
    for fence in re.finditer(r"(?m)^ {0,3}(`{3,}|~{3,})([^\n]*)$", prefix):
        marker, tail = fence.groups()
        if opening:
            if marker.startswith(opening) and not tail.strip():
                opening = ""
        elif marker.startswith("~") or "`" not in tail:
            opening = marker
    return bool(opening)


def community_document_update(name, raw, release):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw
    newline = "\r\n" if "\r\n" in text else "\n"
    # Preserve nonstandard or mixed formats for a manual merge.
    pieces = text.split(newline)
    if any("\r" in line or "\n" in line or "\0" in line for line in pieces):
        return raw
    body = "\n".join(pieces)
    header = ""
    if name == "ARCHITECTURE.md":
        if not body.startswith("---\n") or "\n---\n" not in body[4:]:
            return raw
        header, body = body.split("\n---\n", 1)

    for rule in RULES[name]:
        metadata = rule.get("frontMatter", False)
        original = header if metadata else body
        matches = [m for m in re.finditer(rule["pattern"], original, re.MULTILINE)
                   if metadata or not inside_code_fence(original[:m.start()])]
        if not matches and rule.get("optional"):
            continue
        if len(matches) != 1:
            return raw
        match = matches[0]
        replacement = re.sub(r"{{(\w+)}}", lambda m: release[m[1]], rule["replacement"])
        updated = original[:match.start()] + replacement + original[match.end():]
        if metadata:
            header = updated
        else:
            body = updated
    result = (header + "\n---\n" if header else "") + body
    return (codecs.BOM_UTF8 if raw.startswith(codecs.BOM_UTF8) else b"") + result.replace("\n", newline).encode("utf-8")
