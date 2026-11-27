# Release process

The public repository is promoted from a reviewed, allowlisted staging snapshot.
A version is published only after the public PR, required CI, release review, tag,
and GitHub Release are complete.

1. Finish and review all source changes, including pre-existing uncommitted work.
   While the candidate is local, keep the `(unreleased)` suffix in the top
   changelog heading. Before freezing the bytes intended for publication,
   remove the suffix and check that download links and version labels match
   the intended release. Re-freeze and requalify that exact revision. The
   packaged changelog ships inside the customer ZIP.
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
5. Obtain owner review of the exact artifact. For an approved publication,
   create or fetch the annotated Community release tag on the finalized commit.
   Run `python scripts/release.py --check-tag` on that commit. The check verifies
   the tag against the release version and HEAD and requires the finalized changelog.
   Create the release draft against the verified tag, attach the tested customer ZIP
   and verify its name and SHA-256. Publish only after the release review.
   Preserve earlier tags and named assets.

## GitHub release draft

The current copyable text lives in [the Community setup prompt](docs/prompts/setup.md).
Point new install and update copy buttons to that one text block. Keep the
historical versioned prompts available for older links. After publication, test
the prompt with the official repository URL and confirm that the named asset and
published SHA-256 match the tagged kit. Check all three supported agent clients.

Check the repository’s **About** description before publication. Use this
version-independent wording for the repository:

> KOS Community is a free, open-source Markdown workspace for notes, projects and AI-assisted workflows. Includes cross-platform installers and optional Obsidian support.

For this candidate, use the title **KOS Community 1.4.0**
and distribution tag `v1.4.0`. The customer asset is
`kos-community-v1.4.0.zip`. The tag and filename use the Community release number
in `installer/release.json`. Every release, including an installer-only fix,
gets a new Community release number. For direct downloads, use the tagged
release’s exact asset name. Earlier releases retain their original filenames and URLs.
To print the expected asset name, run `python scripts/release.py --archive-name`.

Open the release body with “KOS Community 1.4.0 uses KOS Core contract 1.0.0.”
Use the customer-facing bullets in the top
section of [CHANGELOG.md](CHANGELOG.md) for the changes. Under **Download**,
name the exact asset, include the verified ZIP’s SHA-256 and direct readers
to the bundled `INSTALL.md` for new installations and upgrades. Under GitHub
**Assets**, the named ZIP is the installer and the source archives contain
the repository. Check the title, body and attached asset again before
publishing the draft.

For a checkout enrolled in an organization’s private confidentiality review,
set the checkout-local Git setting `kos.privacyReceipt` to an absolute receipt
path outside the checkout. The organization’s scanner keeps its comparison
terms private and issues a dated PASS receipt for the source fingerprint,
exact ZIP digest and output filename (`zip_name`, including the extension).
The build verifies the receipt before publishing the output file. Changes to
the source, ZIP bytes or filename require a fresh review.

`installer/release-files.json` is the frozen source/test allowlist.
`installer/archive-files.json` is the narrower client ZIP allowlist. A file must
be in both lists to ship; new source files are not implicitly published. Tests,
CI, release tooling, maintainer documentation, reports, local answers/permissions,
logs, build/test output, PDFs, HTML and private configuration are excluded from
the ZIP. Historical reports remain in source history.
`installer/release.json` records KOS Community 1.4.0,
installer 1.4.0, distribution 1.4.0, contract 1.0.0, schema/adapter 1.0.0 and independently
versioned extensions. `python scripts/release.py` rejects any version drift.

NOTICE carries existing attribution; LICENSE retains Apache terms. Commercial
packages and KOS editions do not relicense KOS Community or user knowledge. A
passing local gate does not replace cross-platform CI or certify unavailable KOS
Pro activation.
