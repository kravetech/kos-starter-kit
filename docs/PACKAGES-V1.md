# Local package format and lifecycle

Skills and Power-Ups can run on KOS Community without KOS Pro. The common engine also stores
adapter, integration and bundle packages. A bundle is a package of static assets;
it does not recursively download or execute installers.

Use `install.ps1 -Target <vault> -PackageCommand <command>` or
`./install.sh --target <vault> --package-command <command>`. Commands: `validate`,
`install`, `list`, `enable`, `disable`, `update`, `rollback`, `uninstall`.
Supply `-Package <directory-or-kospkg>` / `--package` for validate/install/update,
and `-Id <id>` / `--id` for other lifecycle commands. Package rollback selects the
previous version or explicit `-Version` / `--version`. Use dry-run, inspect the
plan, then approve. Nonempty permission requests additionally need
`-ApprovePermissions` / `--approve-permissions`, including changed permissions.

## Layout and authoring

Packages are a directory or ZIP-backed `.kospkg` containing `manifest.json` and
`payload/<declared files>`. No extraction occurs until validation. The archive
must have unique slash-separated safe names and no links; backslash ZIP names
(including those emitted by older .NET directory ZIP helpers) are rejected.
Limits are 4,096 entries, 16 MiB per
file, 64 MiB total uncompressed content. Every payload file must be listed under
manifest `integrity` with its lowercase SHA-256 hash. Undeclared files fail.

See `installer/schemas/package.schema.json` and the synthetic package factories
in `tests/test_safety.py`. Required fields include schemaVersion, schema, type,
id, name, version, creator, license, compatibility, supportedEditions, scope,
permissions, dependencies, entrypoints, enabledByDefault, configurationSchema,
defaults and integrity. Skills use `kos-skill/v1`, require `entrypoint: SKILL.md`,
and include `SKILL.md`; Power-Ups use `kos-powerup/v1`; other types use
`kos-package/v1`. Compatibility is `{min, maxExclusive}` against the KOS contract;
dependencies map stable IDs to exact installed, enabled versions. Cycles fail.

Configuration validation implements an explicit JSON Schema subset: object,
array, string, boolean, integer, number and null types; properties, required,
additionalProperties, enum, const, items, uniqueItems, length/count/numeric
bounds, pattern, and date format. Descriptive annotations are accepted.
Unsupported validation keywords and formats fail closed when evaluated; remote
references and schema composition are unavailable. Unknown user configuration
keys remain valid unless the package explicitly disallows additional properties.

Canonical immutable locations:

- Skills: `.agents/skills/<id>/<version>`; registry `.agents/registry/skills.json`.
- Power-Ups: `00 - System/Power-Ups/Installed/<id>/<version>`; registry
  `00 - System/Power-Ups/Registry/power-ups.json`.
- Other package types: System Adapters, Integrations or Bundles `Installed` trees;
  shared registry `00 - System/Config/packages.json`.

Manifests are retained beside entrypoints as `manifest.json`; Skills also receive `skill.json`. Configuration,
state and reports belong in `00 - System/{Config,State,Reports}/{Skills,Power-Ups}`,
never immutable code. Package defaults < global user configuration < project
configuration. Object keys merge; arrays are replaced at the higher priority.
Project activation uses `02 - Projects/Active/<Project>/power-ups.json`; provider
consumers must enforce global enabled status and exact installed identity.

Same ID/version with different manifest or content is blocked. Updates preserve
previous versions and enabled state. Reinstalling an identical package is a no-op.
Enable verifies integrity; disabling/uninstalling a dependency used by an enabled
package is blocked. Uninstall removes only manifest-declared, unchanged code.
Modified package files stop removal. User data and configuration remain.

## Trust and commercial boundaries

Unsigned local packages require normal explicit plan approval. Signatures, when
present or required, must verify against an explicitly supplied external trust
file (`-Trust` / `--trust`). No embedded key is automatically trusted. Supported
signature: RSA PKCS#1 v1.5 with SHA-256 and a public modulus of at least 2048 bits.
The signed bytes are canonical sorted-key, two-space-indent UTF-8 JSON plus LF,
with the top-level `signature` field omitted. `signature` contains `keyId`,
`algorithm: rsa-sha256`, and base64 `value`. Trust JSON uses
`keys.<keyId>.modulus` and `.exponent` as base64 unsigned big-endian public values.

Permission declarations are review inputs, not an OS sandbox. No downloaded code,
hooks or entrypoints execute automatically. There is no marketplace, download
service, secret storage, production entitlement verifier or license server.
Commercial packages retain their own licenses. `supportedEditions` uses
`community`, `pro`, or `enterprise`. The legacy values `starter` and `core` remain
readable for compatibility and map to `community` and `pro`. Pro-only and
Enterprise-only packages require corresponding declared capabilities.
There is no expiry check that disables an acquired installed version.

KOS Pro conversion is an intentionally blocked boundary. The public Starter Kit
cannot activate Pro, validate a commercial entitlement, or exercise Pro activation
rollback without a separately supplied commercial implementation. Standalone
packages remain untouched by Pro dry-runs. Installing a commercial edition must
never relicense the user's vault or the open-source Starter Kit.

The pre-existing YAML Power-Up templates and discovery modules remain source
history for compatibility review. They are not an immutable package installer.
Use this engine for all v1.2 lifecycle mutations; manually review/import older
registries rather than silently creating another registry.

The read-only runtime interfaces are Python `resolve_powerup` and PowerShell `Resolve-KosPowerUp`. They verify immutable files and project activation, combine defaults/global/project configuration, preserve unknown keys, and honor global disabled state. They return data and never run package entrypoints. Project activation uses the shipped `project-activation` schema.
