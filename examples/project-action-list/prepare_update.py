"""Build the example's next patch release with a different action limit."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new .kospkg file to create")
    parser.add_argument("--max-actions", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.max_actions <= 100:
        parser.error("--max-actions must be between 1 and 100")
    if args.output.suffix.lower() != ".kospkg":
        parser.error("choose a new file with the .kospkg extension")

    package = Path(__file__).resolve().parent / "powerup"
    manifest = json.loads((package / "manifest.json").read_bytes())
    pointer = (package / "payload/shared-skill.json").read_bytes()
    if hashlib.sha256(pointer).hexdigest() != manifest["integrity"]["shared-skill.json"]:
        parser.error("the shared Skill descriptor differs from the starting manifest")

    major, minor, patch = map(int, manifest["version"].split("."))
    manifest["version"] = f"{major}.{minor}.{patch + 1}"
    manifest["defaults"]["maxActions"] = args.max_actions
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("manifest.json"), json.dumps(manifest, indent=2) + "\n")
        archive.writestr(zipfile.ZipInfo("payload/shared-skill.json"), pointer)
    try:
        with args.output.open("xb") as stream:
            stream.write(buffer.getvalue())
    except FileExistsError:
        parser.error("the destination exists; choose another .kospkg filename")
    print(f"Created {args.output.name} for {manifest['id']} {manifest['version']}")


if __name__ == "__main__":
    main()
