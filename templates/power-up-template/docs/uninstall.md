# Uninstall

1. Disable the registry entry first (`status: disabled`); this alone stops
   adapters from invoking the Power-Up and deletes nothing.
2. Show which files and which initialized target workspaces
   (`<Target>/.kos/power-ups/kos-example/`) would be affected.
3. Remove the runtime only after explicit approval.
4. Preserve user data by default; offer cleanup of initialized target
   workspaces as a separate, opt-in step.
5. Remove the registry entry from `00 - System/Power-Ups/registry.yaml` only
   after the runtime has been removed successfully.

Never delete canonical KOS files as part of uninstall.

`installer/uninstall.ps1` / `installer/uninstall.sh` implement this sequence.
