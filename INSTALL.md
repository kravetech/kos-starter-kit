# Installation and migration

Installing KOS Starter Kit creates **KOS Community** on the shared **KOS Core** architecture.

See [the v1.2 operation guide](docs/INSTALLER-V1.2.md).

```powershell
./install.ps1 -Answers ./installer/answers.example.json -Target ./test-output/My-KOS -Operation new -DryRun
./install.ps1 -Answers ./installer/answers.example.json -Target ./test-output/My-KOS -Operation new -Approve
./install.ps1 -Target ./test-output/My-KOS -Operation upgrade -DryRun
./install.ps1 -Target ./test-output/My-KOS -Operation validate
```

```bash
./install.sh --answers installer/answers.example.json --target test-output/My-KOS --operation new --dry-run
./install.sh --answers installer/answers.example.json --target test-output/My-KOS --operation new --approve
./install.sh --target test-output/My-KOS --operation upgrade --dry-run
./install.sh --target test-output/My-KOS --operation validate
```

PowerShell 5.1/7 is native; Bash needs Python 3.10+. Copy the example to ignored
`installer/answers.json` for personal values. New installs require an empty target.
Use upgrade for existing KOS and enhance for Obsidian. Minimal enhancement is the
default; `-Mode complete` / `--mode complete` adds missing numbered domains.
Nothing moves notes or resets .obsidian. Global overwrite is rejected.
Before changing an existing vault, make a complete backup outside the vault,
review the dry-run plan, and apply with `-Approve` / `--approve`. The installer
backs up files it changes; it does not copy the entire vault. An answer file or
legacy migration switch does not approve an existing-vault write.
The old `backup_before_migration` answer is rejected because it never made a
complete vault backup. Remove it from older answer files after taking a
separate, verified snapshot.

Select adapters with `installation.providers`: codex, claude, gemini. Provider
executables are not needed to create files. See [packages](docs/PACKAGES-V1.md).
For interrupted operations review the run journal and rollback by run ID;
automatic resume is blocked.
