# Tests

At minimum, cover:

- `manifest.yaml` validates against `installer/power-up-manifest.schema.json`
  in the KOS Starter Kit (unique id, semver, declared permissions and
  lifecycle commands).
- `installer/initialize.*` does not modify files outside the target's
  `.kos/power-ups/kos-example/` workspace and is safe to run twice.
- `installer/uninstall.*` never deletes user data without explicit approval
  and never touches canonical KOS files.

Test framework choice is up to this Power-Up; the KOS Starter Kit does not
require a specific one.
