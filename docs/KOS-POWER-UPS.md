# KOS Power-Ups

A Power-Up adds an optional, independently versioned workflow to a Community vault. The Community installer includes the free Project Action List as two installable v1 packages. The owner chooses when to install the Power-Up and its shared Skill and which projects may use them.

## Try the bundled workflow

The input is one or more selected Markdown meeting notes from an approved project. The output is a new local JSON action list with each open task’s text, project-relative filename and line number. Gemini CLI, Claude Code and Codex CLI use the same Skill. The tutorial also provides a local account-free route. [Free Project Action List tutorial](PROJECT-ACTION-LIST.md)

1. From the extracted kit, validate, install and enable the Skill in `examples/project-action-list/skill/`.
2. Review the permissions requested by `examples/project-action-list/powerup/`. Approve the package, enable it in the vault and opt in one project.
3. Select a meeting note and run the documented preparation command for the chosen provider. Save the verified result under a new name in the project’s `Results/` folder.

Removing project opt-in blocks the workflow in that project. Globally disabling the Power-Up blocks it in every project. In either case the host withholds the Skill and selected note content. [Invocation and disable checks](PROJECT-ACTION-LIST.md#run-the-shared-skill)

## Build a v1 package

Start by copying the two package directories in `examples/project-action-list/`. Each has a `manifest.json` with a version, permissions, dependencies, entrypoints and file hashes for its `payload/`. The example Power-Up depends on one exact version of its Skill. The author walkthrough changes a default, builds an updated package, then exercises update, rollback and uninstall. [Author walkthrough](PROJECT-ACTION-LIST.md#adapt-update-and-roll-back) · [v1 package format](PACKAGES-V1.md)

The installer stores immutable Power-Up code under `00 - System/Power-Ups/Installed/<id>/<version>/` and Skills under `.agents/skills/<id>/<version>/`. Project opt-in and overrides belong in the selected project’s `power-ups.json`. Package removal preserves user notes, configuration and results. [Package installation and lifecycle](POWER-UP-INSTALLATION-GUIDE.md)

## Legacy YAML discovery

Older Power-Ups can have a `manifest.yaml`, an external runtime directory and entries in a YAML registry. The discovery and status commands inspect those records read-only. To migrate one, review its permissions and payload, create a v1 package and validate it with the local installer. The older template under `templates/power-up-template/` is a reference for this migration. [Legacy discovery commands](POWER-UP-INSTALLATION-GUIDE.md#legacy-yaml-discovery)
