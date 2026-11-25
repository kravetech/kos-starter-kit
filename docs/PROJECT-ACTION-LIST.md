# Project Action List

Project Action List is a free Community Power-Up. Select a project and one or more Markdown notes. It produces a JSON list of open tasks with their source filenames and line numbers. Gemini CLI, Claude Code and Codex CLI all use the same versioned Skill. You can also generate the result locally with Python.

Write a task as `- [ ] Short action` on its own line. The extractor accepts `-`, `*` or `+` bullets with up to three leading spaces. It skips completed tasks, code blocks and more deeply indented lines. Obsidian comments delimited by `%%` and HTML comments are omitted from the text supplied to a provider. Citations use line numbers in the original note.

## Try it in a disposable vault

Run the commands from the folder containing the extracted Starter Kit's `installer`, `scripts` and `examples` directories. Use Python 3.10 or newer. On systems with a `python3` command, substitute it for `python`. Keep the extracted kit available when working with an installed vault.

```text
python installer/install.py --target ../DemoVault --operation new --answers installer/answers.example.json --approve
python "../DemoVault/00 - System/Tools/ProjectContext/project_context.py" --vault ../DemoVault --project Workshop init
python "../DemoVault/00 - System/Tools/ProjectContext/project_context.py" --vault ../DemoVault --project Workshop review
```

Inspect the project's `memory.md` and `handoff.md` and the review result. If you accept the pair, replace `TOKEN_FROM_REVIEW` with the displayed token.

```text
python "../DemoVault/00 - System/Tools/ProjectContext/project_context.py" --vault ../DemoVault --project Workshop approve --review-token TOKEN_FROM_REVIEW
```

For the expected result below, copy the worked example to `../DemoVault/02 - Projects/Active/Workshop/Meeting.md`. For your own meeting, copy `08 - Templates/Meetings/Meeting-Note.md` from the installed vault into the selected project. Fill in decisions, owners, dates and unknowns, and record open tasks as checkboxes. Use a new note when trying this in a customized vault. A newly edited handoff requires a fresh review before retrieval. [Worked meeting example](../examples/project-action-list/meeting.md) · [Project context guide](PROJECT-CONTEXT.md)

## Install and opt in

The example contains two local v1 packages. The Power-Up pins the Skill's ID, version, entrypoint and SHA-256. Inspect `examples/project-action-list/skill/payload/SKILL.md` and both package manifests. Install and enable the Skill first so the Power-Up's dependency can be verified.

```text
python installer/install.py --target ../DemoVault --package-command validate --package examples/project-action-list/skill
python installer/install.py --target ../DemoVault --package-command install --package examples/project-action-list/skill --approve
python installer/install.py --target ../DemoVault --package-command enable --id project-action-list-skill --approve
python installer/install.py --target ../DemoVault --package-command validate --package examples/project-action-list/powerup
python installer/install.py --target ../DemoVault --package-command install --package examples/project-action-list/powerup --dry-run
```

The preview lists two permissions, `read:selected-project-sources` and `write:project-result`. It reports blocked until permissions are approved. Grant them if you accept reading the selected notes and creating a new project result.

```text
python installer/install.py --target ../DemoVault --package-command install --package examples/project-action-list/powerup --approve-permissions --approve
python installer/install.py --target ../DemoVault --package-command enable --id project-action-list --approve
```

Open `../DemoVault/02 - Projects/Active/Workshop/power-ups.json`. Create it with the contents below if it is missing. If it already exists, add the single `project-action-list` entry to its existing `packages` object and preserve the other entries. Omitting `version` follows the enabled installed version.

```json
{
  "schemaVersion": "1.0.0",
  "packages": {
    "project-action-list": {"enabled": true}
  }
}
```

## Run the shared Skill

Choose a client and prepare the request in the kit folder. Replace `codex` with the provider value in the table as needed.

```text
python scripts/community_skill.py --vault ../DemoVault --project Workshop --power-up project-action-list --provider codex prepare --source Meeting.md
```

The host verifies the active Power-Up and the shared Skill, checks the project approval and returns the exact `skill.instructions`, selected task candidates and a `preparationSha256`. Inspect the selection and `truncated` indicator. Repeat `--source` for each authorized note, up to 32 files. Supply just the verified instructions and candidates to the chosen client when you approve sharing those task lines. Keep the preparation digest for saving.

| Client | Provider value | Request in that client |
|---|---|---|
| Gemini CLI | `gemini` | Apply the supplied shared Skill to these candidates and return its JSON result. |
| Claude Code | `claude` | Apply the supplied shared Skill to these candidates and return its JSON result. |
| Codex CLI | `codex` | Apply the supplied shared Skill to these candidates and return its JSON result. |

The preparation command runs locally. To have a signed-in client run it directly, open the client in the kit folder. Replace `{prepare_command}` in the prompt below with the full preparation command for your chosen provider and selected notes. Use the same prompt for Gemini CLI, Claude Code or Codex CLI.

```text
Invoke your shell tool exactly once in the current directory with this command:
{prepare_command}
Read the host JSON in the command output. If its status is "blocked", stop immediately, make no further tool calls, and return exactly {"status":"blocked"}. For a ready result, apply its verified shared Skill instructions to the returned candidates and return only the Skill's JSON result. Do not run other commands or inspect other data.
```

When project opt-in is missing or the Power-Up is disabled globally, the host withholds the Skill and selected note content. Save a result only after a ready preparation.

For the sample, compare the provider's response with this expected result. Both tasks come from the same explicit selection.

```json
{"actions":[{"path":"Meeting.md","line":6,"text":"Confirm the meeting time."},{"path":"Meeting.md","line":8,"text":"Share the draft agenda."}]}
```

Save the client's raw JSON reply as UTF-8 `reply.json` in a private working directory. To verify and save that reply, pass it on standard input and replace `SHA_FROM_PREPARE` with the preparation digest. This PowerShell block preserves Unicode when piping into Python, including on Windows PowerShell 5.1. Set the path to your private reply file.

```powershell
& {
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    Get-Content -Raw -Encoding utf8 reply.json | python -X utf8 scripts/community_skill.py --vault ../DemoVault --project Workshop --power-up project-action-list --provider codex save --source Meeting.md --preparation-sha256 SHA_FROM_PREPARE --output actions.json --response-stdin
}
```

From a POSIX shell:

```sh
python3 scripts/community_skill.py --vault ../DemoVault --project Workshop --power-up project-action-list --provider codex save --source Meeting.md --preparation-sha256 SHA_FROM_PREPARE --output actions.json --response-stdin < reply.json
```

Use the same provider and selections as in `prepare`. A valid result is created in `02 - Projects/Active/Workshop/Results/actions.json`. A mismatch or changed source requires review and a new preparation. An existing result is preserved.

### Run the example offline

For a local automation or an account-free trial, run these commands from the extracted kit. Substitute the first command’s `preparationSha256` in the second command and choose a fresh output name for each run. The host computes the list locally. The provider label is part of the preparation digest and both commands must use the same label.

```text
python scripts/community_skill.py --vault ../DemoVault --project Workshop --power-up project-action-list --provider codex prepare --source Meeting.md
python scripts/community_skill.py --vault ../DemoVault --project Workshop --power-up project-action-list --provider codex save --source Meeting.md --preparation-sha256 SHA_FROM_PREPARE --output offline-actions.json
```

Inspect `Results/offline-actions.json` inside the project. Stop the automation if either command exits with a nonzero status.

## Adapt, update and roll back

An author can change the Power-Up's default action limit while keeping the same Skill. The included helper reads the supplied Power-Up and creates a new `.kospkg` with the next patch version. The sample command creates Power-Up 1.0.1 with a limit of one task and the original Skill dependency. Choose an unused destination.

```text
python examples/project-action-list/prepare_update.py ../action-list-update.kospkg --max-actions 1
python installer/install.py --target ../DemoVault --package-command validate --package ../action-list-update.kospkg
python installer/install.py --target ../DemoVault --package-command update --package ../action-list-update.kospkg --approve-permissions --approve
```

Run `prepare` again. On the uncustomized example, the reported Power-Up version is 1.0.1 and the first task is returned. Global user settings override package defaults, and project settings override global settings. To try a project override, add `"configuration":{"maxActions":2}` alongside `"enabled":true` in its activation entry. The two sample actions should return. Keep a copy of the first result when saving another.

```text
python installer/install.py --target ../DemoVault --package-command rollback --id project-action-list --version 1.0.0 --approve
python installer/install.py --target ../DemoVault --package-command list
```

For a new workflow, copy both package directories outside the kit. Give them distinct stable IDs and version numbers. Author the single Skill, hash its exact bytes, and update the Skill manifest and the Power-Up descriptor. Hash the descriptor bytes in the Power-Up manifest and set its exact dependency. Validate the Skill, install and enable it, then validate the Power-Up. The supplied CLI implements the Project Action List operation. A workflow with a different input or output contract needs a matching host operation. [Package format and lifecycle](PACKAGES-V1.md)

## Disable or remove

Set the project's activation entry to `"enabled":false` to stop use in that project. To remove the packages from the vault, remove the dependent Power-Up first.

```text
python installer/install.py --target ../DemoVault --package-command disable --id project-action-list --approve
python installer/install.py --target ../DemoVault --package-command uninstall --id project-action-list --approve
python installer/install.py --target ../DemoVault --package-command uninstall --id project-action-list-skill --approve
```

The notes, results and user configuration belong to the vault owner and survive removal. For an ordinary workflow problem, provide the package versions, operation, error and a synthetic note through Community support. Report a suspected vulnerability or privacy leak through the private route. [Installation guide](../INSTALL.md) · [Community support and issue tracker](../README.md#learning-and-support) · [Security reporting instructions](../SECURITY.md)
