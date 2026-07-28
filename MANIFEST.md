# Starter-Kit Manifest

| Component | Purpose | Requirement | Modes | User data | AI load |
| --- | --- | --- | --- | --- | --- |
| `KOS-INSTALLER.md` | Canonical agent installer | Required | All | No | Installation only |
| `QUESTIONNAIRE.md` | Human question contract | Required | All | No | Installation only |
| `installer/questionnaire.schema.json` | Answer validation | Required | All | No | Installation only |
| `installer/answers.example.json` | Synthetic example | Required | All | Synthetic | Example only |
| `installer/private-terms.example.txt` | Local denylist template | Recommended | Builder | Synthetic | Privacy review only |
| `installer/install.py` | Cross-platform engine | Required | All | Reads answers | Installation only |
| `templates/root/*` | Root contracts | Required | All | Placeholders | During generation |
| `templates/system/*` | Control-plane policies | Required | All | No | Task-specific |
| `templates/projects/*` | Project lifecycle | Recommended | Standard+ | No | Selected project only |
| `templates/business/*` | Business MOC | Optional | Business/Standard | No | Business task |
| `templates/personal/*` | Personal MOC | Optional | Standard/Custom | No | Explicit task |
| `templates/hobbies/*` | Hobby MOC | Optional | Standard/Creator | No | Hobby task |
| `templates/knowledge/*` | Knowledge MOC | Recommended | Standard+ | No | Research/knowledge task |
| `templates/inbox/*` | Capture workflow | Required | All | No | Inbox task |
| `templates/daily/*` | Review workflow | Recommended | All | No | Review task |
| `templates/automations/*` | Manual registry | Required | All | No | Automation task |
| `install.ps1`, `install.sh` | Direct installation | Required | All | Reads answers | Execution only |
| `initialize.ps1`, `initialize.sh` | Agent launcher | Required | All | Reads answer path | Execution only |
| `scripts/validate-*` | Structural validation | Required | All | No | Validation only |
| `scripts/privacy-scan.*` | Privacy checks | Required | All | No | Validation only |
| `scripts/public-release-audit.ps1` | Git-index release gate | Required | Builder | No | Publication only |
| `reports/*` | Build evidence | Generated | Builder | May name local source path | Audit only |
| `test-output/*` | Synthetic test install | Generated | Test | Synthetic | Test only |

`structure.manifest.json` is the complete machine-readable generated-file contract.
