# Installation

## Prerequisites

<list runtime dependencies, if any>

## Install

1. Place this Power-Up under your configured Power-Ups home (for example
   `${KOS_POWERUPS_HOME}/kos-example`, or the path recorded in the target
   KOS's `00 - System/Power-Ups/settings.yaml`).
2. From the target KOS, discover and register it:

   ```text
   ./scripts/powerups.ps1 discover -InstallationRoot <kos-path>
   ./scripts/powerups.ps1 register -InstallationRoot <kos-path> -Id kos-example
   ```

   or, on Bash with Python 3:

   ```bash
   ./scripts/powerups.sh discover <kos-path>
   ./scripts/powerups.sh register <kos-path> --id kos-example
   ```

3. Run `installer/initialize.ps1` / `installer/initialize.sh` against each KOS
   folder you want this Power-Up to operate on.

Installation never runs automatically and never touches canonical KOS files.
