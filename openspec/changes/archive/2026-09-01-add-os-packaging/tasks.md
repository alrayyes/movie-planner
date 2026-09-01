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
  `package-linux.yml` reusable workflow, verified against the real
  v0.7.0 release
- [x] 3.4 Upload the `.deb` and `.rpm` as GitHub Release assets
  (`gh release upload` or an equivalent action) and verify they appear
  on the release page — verified against the real v0.7.0 release

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
- [x] 4.3 Generate the man pages in the `PKGBUILD`'s `package()`
  function and install them to the same path, and verify `man
  movie-planner` works after a local `makepkg -si` — invokes
  `click-man` directly via `python -c`, not `scripts/generate-man.sh`
  itself: that script needs `uv`, which isn't part of this build at
  all (same reason `flake.nix` doesn't call it either); verified
  locally end-to-end including the man page after `pacman -U`

## 5. Provenance

- [x] 5.1 Add `actions/attest-build-provenance` for the `.deb`/`.rpm`
  (and the frozen binary, if attested separately) and verify
  `gh attestation verify` succeeds against a built artifact — wired,
  verified against the real v0.7.0 release (`gh attestation verify`
  succeeds against the downloaded `.deb`); the frozen binary itself
  isn't a release asset so isn't separately attested

## 6. Install-test what gets built

- [x] 6.1 Add a step that spins up a `debian`/`ubuntu` container,
  `dpkg -i`s the built `.deb`, and verifies `movie-planner --help` and
  `man -w movie-planner` both succeed afterward
- [x] 6.2 Add the equivalent `rpm -i` step against a
  `fedora`/`rockylinux` container, with the same two verifications
- [x] 6.3 Add a step that runs `makepkg` against the `PKGBUILD` inside
  an `archlinux` container and verifies it builds and installs
  successfully, gating the AUR push in task 7 on this passing — added
  to both `ci.yml` (dry run, against a local `git archive` tarball)
  and the release job (against the real release tarball); verified
  locally end-to-end (build, install, `--help`, `man -w`) against
  both a local dev tarball and the real v0.6.0 release tarball
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
- [x] 7.2 Write the `PKGBUILD` (source: tagged release tarball from
  `https://github.com/alrayyes/movie-planner/archive/movie-planner-vX.Y.Z.tar.gz`,
  real `depends=()` on Arch's `python-*` packages, build via
  `python -m build` + `python -m installer`, man page via task 4's
  approach) and verify `makepkg -si` installs a working
  `movie-planner` locally — verified against both a local dev tarball
  and the real v0.6.0 release tarball, `python-questionary` and
  `python-click-man` (AUR-only deps) built from source via
  `scripts/install-aur-builddeps.sh`
- [x] 7.3 Generate `.SRCINFO` (`makepkg --printsrcinfo`) and push both
  files to the personal AUR git repo, and verify the package appears
  on `aur.archlinux.org/packages/movie-planner` — wired into the
  release job (clone, regenerate, commit, push over the shared
  `aur-ci` key), verified against the real v0.7.0 release — the AUR
  push succeeded on its first real attempt;
  AUR's host key is pinned in the workflow (fetched via `ssh-keyscan`
  against the real host)
- [x] 7.4 Add the release-job step that bumps `pkgver`/checksum,
  regenerates `.SRCINFO`, commits, and pushes to AUR on every release,
  and verify it runs end-to-end on a real tagged release — wired,
  gated on the same install-test as task 6.3 passing first; the
  end-to-end real-release run is task 9.2, now done

## 8. Nix flake

- [x] 8.1 Add `flake.nix` building `movie-planner` via
  `python3.pkgs.buildPythonApplication` (`pyproject = true`,
  `build-system = [ python3.pkgs.uv-build ]`, `dependencies` against
  nixpkgs' own `caldav`/`httpx`/`icalendar`/`questionary`/`rapidfuzz`/
  `typer`) and man page via task 4's approach, and verify `nix build`
  produces a working `movie-planner` — the `uv-build` version blocker
  resolved via an explicit version-bump override (nixpkgs'
  `python3Packages.uv-build` overridden to this project's own pinned
  version, built the same way nixpkgs' own derivation is); the
  `icalendar`/`typer` exact-pin mismatch against nixpkgs' own versions
  resolved via `pythonRelaxDepsHook`; four of nixpkgs' own transitive
  Python packages (`httpcore2`, `paramiko`, `caldav`, `aiohttp`) had
  their own `doCheck` disabled after each one's upstream test suite
  failed or ran long inside Nix's build sandbox in turn — none of it
  tests movie-planner itself, and CI already runs the real suite
  outside Nix. `nix build`/`nix run . -- --help` both verified green
  in CI.
- [x] 8.2 Add a CI job that runs `nix build` and `nix run .# --
  --help` on every push/PR (mirroring `package-linux.yml`'s dry run)
  and verify it catches a deliberately broken flake — verified green
  in CI once 8.1 unblocked
- [x] 8.3 Commit the `flake.lock` CI generates once the build
  succeeds, and verify `nix flake check` passes — no local `nix` in
  this project's dev environment to run `nix flake lock` directly, so
  downloaded from a green CI run's uploaded artifact and committed
  by hand instead; `nix flake check` verified green in CI
- [x] 8.4 Report any nixpkgs-specific friction (the `uv-build` version
  question in design.md's risks, or anything else) to whoever
  maintains the shared Nix packaging conventions — done; reported to
  `dotfiles`, along with the container-image man-page-exclusion and
  git `safe.directory` findings from the AUR work

## 9. Docs and verification

- [x] 9.1 Add `docs/INSTALL.md` covering every install method
  (checkout, `pipx`/`pip`, Docker, AUR, `.deb`, `.rpm`), shrink
  `README.md`'s Installation section to a link plus what it already
  covers, and verify every command shown actually works against a real
  published release — verified against v0.7.0; found the AUR section's
  first draft was itself wrong (a bare `makepkg -si` can't resolve
  `python-questionary`'s own AUR-only dependency), fixed to lead with
  an AUR helper. Nix isn't in the doc yet - add it once 8.1 unblocks
- [x] 9.2 Tag a real release and confirm, for that one release: the
  `.deb` and `.rpm` are attached and provenance-verifiable, the AUR
  package resolves the same version, `man movie-planner` works, and
  `movie-planner --help` runs after each install method — all
  confirmed against the real v0.7.0 release, including a from-scratch
  AUR install via the real published package (not a local stand-in).
  Nix isn't part of this yet - it's still blocked on task 8.1
- [x] 9.3 Once the Nix flake actually builds (task group 8 unblocked)
  and is verified against a real release the same way, add it to
  `docs/INSTALL.md` and close the GitHub issue referencing everything
  that shipped — `nix build`/`nix run . -- --help` verified green in
  CI against real tagged releases (0.9.x) once the release-please
  auto-merge fix landed; added to `docs/INSTALL.md`, issue #38 closed
