# KOS Power-Ups

KOS Community 1.0.0 installs Power-Ups through the immutable local package
lifecycle in [PACKAGES-V1.md](PACKAGES-V1.md). YAML paths described below
remain for legacy review and read-only discovery.

> **KOS is the core operating system. KOS Power-Ups are independently
> installed extensions that integrate with KOS through a controlled,
> manifest-driven contract.**

## What a Power-Up Is

A Power-Up is optional, separately installable, separately versioned,
separately upgradeable, separately removable software that connects to a
Knowledge OS instance. Examples include `kos-lang-extract`, `kos-memory-handoff`,
and `kos-policy-maker` — but the architecture is generic and not hard-coded to
those names. Anyone can publish a Power-Up as its own repository or package.

Power-Ups are never required. A KOS instance with zero Power-Ups installed is
a complete, fully functional Knowledge OS.

## What the Starter Kit Provides

The KOS Starter Kit ships the **integration contract**, not any Power-Up
itself:

| Provided by the Starter Kit | Not provided by the Starter Kit |
| --- | --- |
| `00 - System/Power-Ups/` generated structure (`registry.yaml`, `settings.yaml`, `manifests/`, `README.md`) | Any Power-Up's actual runtime code |
| The manifest schema (`installer/power-up-manifest.schema.json`) | A marketplace, licensing server, or payment system |
| Installer questionnaire fields and discovery tooling (`scripts/powerups.ps1` / `scripts/powerups.sh`) | Automatic installation of any module |
| A generic developer template (`templates/power-up-template/`) | Business logic specific to any one Power-Up |

## Where Things Live

```text
<workspace-root>/
├── Obsidian/
│   └── <Your Knowledge OS>/              # the KOS vault
│       └── 00 - System/
│           └── Power-Ups/                # KOS-side metadata only
│               ├── registry.yaml
│               ├── settings.yaml
│               ├── manifests/
│               └── README.md
│
└── KOS Power-Ups/                        # actual Power-Up runtimes (external mode)
    ├── kos-lang-extract/
    ├── kos-memory-handoff/
    └── kos-policy-maker/
```

`00 - System/Power-Ups/` never contains a full copy of any Power-Up's
runtime. It stores registration data, a copy of each registered Power-Up's
manifest (for offline validation), and shared settings. See
`00 - System/Power-Ups/README.md` in a generated instance for the local
operating rules, and `templates/power-ups/README.md` in this repository for
the template that generates it.

## Installation Modes

- **External (default, recommended)** — the Power-Up lives in its own
  directory outside the vault, typically `${KOS_POWERUPS_HOME}/<power-up-id>`.
  Independent Git history, clean KOS core, no runtime bloat inside Obsidian.
- **Embedded (opt-in, off by default)** — the Power-Up's runtime lives under
  `00 - System/Power-Ups/installed/<power-up-id>/` inside the vault. Useful
  for portable, self-contained deployments; increases vault size, mixes
  runtime files with knowledge files, and complicates Git boundaries. The
  installer never creates the `installed/` folder unless a user explicitly
  enables embedded installation.

## Lifecycle

```text
Discover -> Validate -> Install -> Register -> Initialize -> Use
                                        |
                             Disable / Upgrade / Repair
                                        |
                                    Uninstall
```

See [the Power-Up installation guide](POWER-UP-INSTALLATION-GUIDE.md) for the
full command sequence. The shipped `templates/power-up-template/` provides a
starting structure for package authors.

## Folder Initialization

A Power-Up is installed once but may be **initialized** for any number of
approved KOS folders (for example, one client folder and one project). This
never duplicates the Power-Up's runtime; it creates a lightweight workspace
(by default `<Target>/.kos/power-ups/<id>/`) and records the target in that
Power-Up's registry entry under `initialized_targets`.

## Security Model

- No Power-Up may access the entire vault by default — only the folders it
  was explicitly initialized for, plus its own workspace.
- Credentials are never stored in `registry.yaml`, manifests, or any tracked
  configuration; Power-Ups read secrets from environment variables or OS
  secret storage.
- Direct edits to canonical KOS files (`memory.md`, `handoff.md`, policies,
  requirements) require the manifest to declare
  `permissions.canonical_kos_writes.allowed: true` **and** explicit user
  approval per change — the two are not substitutes for each other.
- Generated content from a Power-Up is review-first: it lands in a review
  location before anything counts as approved.
- Discovery never executes a candidate Power-Up's scripts, never
  auto-installs dependencies, and never auto-enables a discovered module.

## Context and Token Budget

AI agents must not load every installed Power-Up during routine KOS
bootstrap. Load `registry.yaml` only when Power-Up availability is relevant
to the task, and load a specific Power-Up's `SKILL.md`/manifest only when
that Power-Up is actually being invoked. See `CONTEXT-POLICY.md` and
`00 - System/Config/ai-context-manifest.yaml` in a generated instance for the
exact exclusion list (runtime, state, cache, logs, and inbox directories are
never auto-loaded).

## Versioning

Power-Ups are versioned independently of Starter Kit and KOS Community. An
existing KOS instance with no `00 - System/Power-Ups/` folder remains valid.

## Non-Negotiable Rules

- Power-Ups are never a mandatory part of KOS.
- The numbered KOS folder contract (`00` through `09`, plus `99 - Archive`)
  is never altered by Power-Up support.
- Discovered scripts are never executed automatically.
- Dependencies are never installed silently.
- One shared runtime is never duplicated per initialized folder.
- Canonical KOS knowledge is never edited without approval.
- Existing files are never overwritten during installation or migration.
- Credentials are never stored in manifests or the registry.
- Not every installed Power-Up is loaded into routine AI context.
- The architecture is not hard-coded to today's Power-Up names.
