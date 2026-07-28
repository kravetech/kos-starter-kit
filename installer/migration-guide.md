# Migration Guide

1. Back up the exact existing target.
2. Use migration mode with overwrite disabled.
3. Review the dry-run manifest.
4. Run installation.
5. Review every `.new.md` and `.new` proposal.
6. Merge deliberately; do not bulk replace existing notes.
7. Run installation validation and privacy scanning.
8. Keep the installer state and report until acceptance.

Migration is additive. The installer does not delete, rename, or relocate existing content.
