# Public Release Procedure

## Release Gate

Do not push until every required item passes.

### 1. Owner and License

- [ ] Confirm `Kraven` is the intended public author and copyright-holder name.
- [ ] Confirm Apache-2.0 is the intended license for code, templates, and documentation.
- [ ] Confirm the Knowledge OS and KOS names are approved for public use.

### 2. Privacy Review

- [ ] Copy `installer/private-terms.example.txt` to ignored `installer/private-terms.txt`.
- [ ] Replace the examples with private people, organizations, usernames, hostnames, projects, and machine identifiers.
- [ ] Run `.\scripts\privacy-scan.ps1`.
- [ ] Review `ARCHITECTURE.md`, `reports/`, examples, and templates for private provenance or unwanted public identity.
- [ ] Never publish a manually created archive of the working folder; publish only Git-tracked content.

### 3. Validation

- [ ] Run `.\scripts\validate-starter-kit.ps1`.
- [ ] Run a clean PowerShell installation into a temporary directory.
- [ ] Run the Bash/Python installation on Linux or in CI.
- [ ] Confirm CI passes on Windows and Ubuntu.

### 4. Git Staging

```powershell
git init -b main
git add --all
git update-index --chmod=+x install.sh initialize.sh scripts/generate-manifest.sh scripts/privacy-scan.sh scripts/validate-installation.sh scripts/validate-starter-kit.sh
git status --short --ignored
git diff --cached --check
git diff --cached
.\scripts\public-release-audit.ps1
```

The release audit must report `PASS`. Its local denylist warning is acceptable only after the owner confirms that no project-specific private terms are needed.

If Gitleaks is installed, also run:

```powershell
gitleaks dir .
git commit -m "Initial public release"
gitleaks git .
```

### 5. GitHub Configuration

- [ ] Enable secret scanning and push protection.
- [ ] Enable Dependabot alerts and code scanning.
- [ ] Protect `main` against force pushes and deletion.
- [ ] Require CI status checks and conversation resolution.
- [ ] Set GitHub Actions workflow permissions to read-only unless a workflow explicitly needs more.
- [ ] Enable private vulnerability reporting.

### 6. Publication

- [ ] Create a fresh empty public repository from the audited local history.
- [ ] Push `main`.
- [ ] Confirm ignored runtime files are absent on GitHub.
- [ ] Confirm the detected license is Apache-2.0.
- [ ] Create an annotated `v1.1.0` tag only after the public tree and CI are verified.

## Incident Response

If sensitive data is pushed, revoke or rotate credentials first. Removing a file in a later commit does not remove it from Git history, forks, caches, or existing clones. Stop publication work, rewrite affected history, re-scan it, and coordinate GitHub cleanup before resuming.
