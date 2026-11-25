# Initialize KOS Community

Use the [installation guide](INSTALL.md) for a new vault or a supported update. The steps below launch an installed AI client for guided setup. The direct installer also works without an AI client.

1. Open a terminal in the starter-kit folder.
2. Run `initialize.ps1` or `initialize.sh`.
3. Use the default `auto` setting or select an installed client with `-Agent` (PowerShell) or `--agent` (Bash). The choices are `gemini`, `claude` and `codex`.
4. Answer the questionnaire or provide JSON answers.
5. Review the dry-run manifest.
6. Generate the Knowledge OS.
7. Review the validation and privacy reports.

For deterministic automation, copy `installer/answers.example.json`, replace synthetic values, and pass it with `-Answers` or `--answers`.
