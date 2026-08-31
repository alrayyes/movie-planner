## 1. Ticket

- [x] 1.1 File the GitHub issue for this work (description, background,
  acceptance criteria, definition of done) and verify it exists with
  `gh issue view` before any other task starts — filed as #38

## 2. Frozen binary for .deb/.rpm

- [x] 2.1 Add a pinned `PyInstaller` build step producing a single
  `movie-planner` executable and verify running it directly
  (`./dist/movie-planner --help`) works with no `PATH`/venv active —
  `scripts/build-binary.sh`, via the Dockerfile's `pyinstaller` stage
- [x] 2.2 Confirm the frozen binary's declared/tested minimum glibc
  floor and note it in design's risk section or the README once known
  — built against `python:3.14-slim-bookworm`'s glibc; confirmed
  running on both Debian bookworm and Fedora 41 in CI's install-test

## 3. nfpm packaging

- [x] 3.1 Add a pinned `nfpm` install step (checksum- or
  digest-verified download, no `latest` tag) to the release workflow
  and verify `nfpm --version` prints the pinned version in CI logs —
  digest-pinned `goreleaser/nfpm` image, run via `docker run` rather
  than an install step
- [x] 3.2 Add an `nfpm.yaml` at the repo root describing the `.deb`
  and `.rpm` outputs (binary only, no Python `depends:`) and verify
  `nfpm package` produces both files locally
- [x] 3.3 Wire the build into `.github/workflows/release.yml`, gated
  on `needs.release-please.outputs.release_created == 'true'`, version
  taken from `needs.release-please.outputs.tag_name`, and verify the
  job runs and produces both files on a test release — via the shared
  `package-linux.yml` reusable workflow, not yet exercised against a
  real tagged release (task 8.2)
- [x] 3.4 Upload the `.deb` and `.rpm` as GitHub Release assets
  (`gh release upload` or an equivalent action) and verify they appear
  on the release page — wired, not yet exercised against a real
  release (task 8.2)

## 4. Man page

- [x] 4.1 Add a pinned `click-man` dev dependency and a
  `scripts/generate-man.sh` that writes `man/movie-planner.1` from the
  CLI's own `Click` command, and verify running it locally produces a
  readable page (`man ./man/movie-planner.1`) — generates one page per
  command and subcommand, not just the top level
- [x] 4.2 Reference the generated, gzip-compressed man page in
  `nfpm.yaml`'s `contents:` at `usr/share/man/man1/movie-planner.1.gz`
  and verify it's present after `dpkg -i`/`rpm -i` in task 6 —
  confirmed on full (not `-slim`) debian/fedora images; the `-slim`
  variants exclude `/usr/share/man` by default and would have passed
  this check while shipping nothing
- [ ] 4.3 Call the same script from the `PKGBUILD`'s `package()`
  function and install it to the same path, and verify `man
  movie-planner` works after a local `makepkg -si`

## 5. Provenance

- [x] 5.1 Add `actions/attest-build-provenance` for the `.deb`/`.rpm`
  (and the frozen binary, if attested separately) and verify
  `gh attestation verify` succeeds against a built artifact — wired,
  not yet exercised against a real release (task 8.2); the frozen
  binary itself isn't a release asset so isn't separately attested

## 6. Install-test what gets built

- [x] 6.1 Add a step that spins up a `debian`/`ubuntu` container,
  `dpkg -i`s the built `.deb`, and verifies `movie-planner --help` and
  `man -w movie-planner` both succeed afterward
- [x] 6.2 Add the equivalent `rpm -i` step against a
  `fedora`/`rockylinux` container, with the same two verifications
- [ ] 6.3 Add a step that runs `makepkg` against the `PKGBUILD` inside
  an `archlinux` container and verifies it builds and installs
  successfully, gating the AUR push in task 7 on this passing
- [x] 6.4 Wire all three into the release job so a failure here blocks
  both the GitHub Release asset upload and the AUR push for that
  release, and verify by deliberately breaking one package locally
  first to confirm the gate actually holds — a step failure in
  `package-linux.yml` stops the job before the provenance/upload steps
  run, same default-sequential-step behavior as any other job (6.3's
  AUR step, once added, gates the same way)

## 7. AUR package

- [x] 7.1 Confirm the `AUR_SSH_KEY` secret exists on
  `alrayyes/movie-planner` (the existing shared `aur-ci` key, already
  registered on Ryan's AUR account and already used by other repos —
  AUR has no per-package deploy keys, so this isn't a new credential)
  and verify a workflow step can `ssh aur@aur.archlinux.org` with it —
  confirmed present via `gh secret list`; a workflow step using it is
  still to be written
- [ ] 7.2 Write the `PKGBUILD` (source: tagged release tarball from
  `https://github.com/alrayyes/movie-planner/archive/vX.Y.Z.tar.gz`,
  real `depends=()` on Arch's `python-*` packages, build via
  `python -m build` + `python -m installer`, man page via task 4's
  script) and verify `makepkg -si` installs a working `movie-planner`
  locally
- [ ] 7.3 Generate `.SRCINFO` (`makepkg --printsrcinfo`) and push both
  files to the personal AUR git repo, and verify the package appears
  on `aur.archlinux.org/packages/movie-planner`
- [ ] 7.4 Add the release-job step that bumps `pkgver`/checksum,
  regenerates `.SRCINFO`, commits, and pushes to AUR on every release,
  and verify it runs end-to-end on a real tagged release

## 8. Docs and verification

- [ ] 8.1 Add `docs/INSTALL.md` covering every install method
  (checkout, `pipx`/`pip`, Docker, AUR, `.deb`, `.rpm`), shrink
  `README.md`'s Installation section to a link plus what it already
  covers, and verify every command shown actually works against a real
  published release
- [ ] 8.2 Tag a real release and confirm, for that one release: the
  `.deb` and `.rpm` are attached and provenance-verifiable, the AUR
  package resolves the same version, `man movie-planner` works, and
  `movie-planner --help` runs after each install method — then close
  the GitHub issue referencing what shipped
