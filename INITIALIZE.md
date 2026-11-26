# Initialize KOS Community

Use the [installation guide](INSTALL.md) for a new vault or a supported update. The steps below launch an installed AI client for guided setup. The direct installer also works without an AI client.

1. Open a terminal in the extracted KOS Community installer folder.
2. Run `initialize.ps1` or `initialize.sh`.
3. Use the default `auto` setting or select an installed client with `-Agent` (PowerShell) or `--agent` (Bash). The choices are `gemini`, `claude` and `codex`. The launcher checks the agent name before starting setup.
4. Answer the questionnaire or supply an existing JSON answers file.
5. Review the dry-run plan and approve the target and files before applying it.
6. After setup, review the installer’s `report.md` under `00 - System/Installation/Runs/<run-id>/`.
7. Run validation and review its findings. Use the [privacy scanner](PRIVACY.md) if you also need a privacy report.

For deterministic automation, copy `installer/answers.example.json`, replace synthetic values, and pass it with `-Answers` or `--answers`.

If an operation was interrupted, inspect its journal and preview recovery before continuing. Guided setup blocks automatic resume. [Recovery procedure](docs/INSTALLER-V1.2.md)
