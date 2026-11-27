#!/usr/bin/env python3
"""Start Community guided setup from a standalone installed skill."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import subprocess
import sys
import zipfile

if sys.version_info < (3, 10):
    sys.exit("Community guided setup requires Python 3.10 or newer.")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from community_asset import COMMUNITY_URL, ReleaseError, is_repository, unpack, verified_archive


def has_launcher(asset):
    with zipfile.ZipFile(asset.path) as archive:
        return "setup.py" in archive.namelist()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=COMMUNITY_URL, help="Official repository URL or a local release ZIP")
    parser.add_argument("--target", help="Vault or new folder, relative to your working directory")
    parser.add_argument("--adapter", choices=["codex", "claude", "gemini", "none"], help="Fresh-install adapter")
    parser.add_argument("--recovery-parent", help="Private parent directory for the backup and rehearsal")
    parser.add_argument("--answers", help="Existing private answers file")
    parser.add_argument("--check", action="store_true", help="Check an existing vault without applying changes")
    args = parser.parse_args(argv)
    try:
        with ExitStack() as stack:
            selected = stack.enter_context(verified_archive(args.source))
            launcher = selected
            if not has_launcher(selected):
                if is_repository(args.source):
                    raise ReleaseError(f"The latest published release {selected.version} has no guided launcher. "
                                       "Use a trusted Community kit containing setup.py when available.")
                # An older attachment selects the payload. A newer official release supplies only the driver.
                launcher = stack.enter_context(verified_archive(COMMUNITY_URL))
                if not has_launcher(launcher):
                    raise ReleaseError(f"The selected ZIP and latest published release {launcher.version} "
                                       "have no guided launcher. Use a trusted Community kit containing setup.py.")
            kit = unpack(launcher, launcher.path.parent / "launcher")
            command = [sys.executable, "-I", "-B", str(kit / "setup.py"), str(selected.path)]
            for option in ("target", "adapter", "recovery_parent", "answers"):
                value = getattr(args, option)
                if value is not None:
                    command.extend(["--" + option.replace("_", "-"), value])
            if args.check:
                command.append("--check")
            print(f"Verified Community distribution {selected.version}. Guided launcher {launcher.version}.", flush=True)
            return subprocess.run(command).returncode
    except KeyboardInterrupt:
        print("Interrupted. Inspect any reported run journal before retrying.", file=sys.stderr)
        return 130
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("Setup stopped: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
