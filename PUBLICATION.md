# Release process

The public repository is promoted from a reviewed, allowlisted staging snapshot.
A version is published only after the public PR, required CI, release review, tag,
and GitHub Release are complete.

1. Finish and review all source changes, including pre-existing uncommitted work.
   Run `python scripts/release.py` for allowlist, privacy, asset and version checks.
2. Run `python scripts/release.py --freeze`. This creates a source candidate under
   `build/candidates/` containing the full source/test allowlist and a SHA-256
   manifest. Review that folder. Changes to frozen source require a new candidate.
3. Run `python scripts/release.py --stage --candidate auto`, or supply the
   frozen source folder explicitly. This reruns source tests, stages the narrower
   client files in a fingerprinted `build/payloads/` folder, and tests new
   installation, supported 1.1.0 upgrade, and additive Obsidian enhancement
   directly from that folder. It validates each result and checks preservation
   of existing content and settings. Review this exact payload folder and the
   disposable test results under `test-output/pv-*/`.
4. After owner authorization for the reviewed Git integration, require Windows,
   Ubuntu and macOS CI for the same source and staged client folder; review
   skips, especially links and long paths. Test disposable copies of
   representative real vaults from the staged payload. Only after those gates
   pass, run the manual `workflow_dispatch` archive check and then run
   `python scripts/release.py --build --payload auto` or pass the
   staged folder explicitly. The command rechecks its source, payload hashes,
   and test proof immediately before ZIP creation. It creates the ZIP from only
   the tested payload bytes and verifies every archive entry against SHA-256.
   Existing archives are never overwritten. Test installation from the staged
   folder during development; smoke test one extraction of the final archive.
   Push and pull request CI do not create a ZIP. The manual CI archive is a
   disposable verification artifact, not the production ZIP.
5. Obtain owner review of the exact artifact. Annotate the matching `vX.Y.Z`
   tag, publish and promote to production only under their respective
   authorizations.

`installer/release-files.json` is the frozen source/test allowlist.
`installer/archive-files.json` is the narrower client ZIP allowlist. A file must
be in both lists to ship; new source files are not implicitly published. Tests,
CI, release tooling, maintainer documentation, reports, local answers/permissions,
logs, build/test output, PDFs, HTML and private configuration are excluded from
the ZIP. Historical reports remain in source history.
`installer/release.json` is authoritative: Starter Kit 1.2.0,
Community 1.0.0, contract 1.0.0, schema/adapter 1.0.0 and independently
versioned extensions. `python scripts/release.py` rejects any version drift.

NOTICE carries existing attribution; LICENSE retains Apache terms. Commercial
packages and KOS editions do not relicense the Starter Kit or user knowledge. A
passing local gate does not replace cross-platform CI or certify unavailable KOS
Pro activation.
