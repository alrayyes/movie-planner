## Context

`movie-planner` builds with `uv`/`pyproject.toml`, targets Python
>=3.13, and has no `goreleaser` (see proposal.md - Why). The existing
`release` workflow (`.github/workflows/release.yml`) runs
`release-please` on every push to `main`, then, only when a release was
actually cut, builds and pushes a Docker image to GHCR. Everything new
here hangs off that same `release_created`/`tag_name` output.

`nfpm` (https://nfpm.goreleaser.com) builds `.deb`/`.rpm` from a config
plus a set of files — it doesn't build Python itself, so the packaging
step needs something else to turn the CLI into files nfpm can wrap.

## Goals / Non-Goals

**Goals:**
- `.deb` and `.rpm` attached to every GitHub Release, installable with
  a bare `dpkg -i`/`rpm -i`.
- A `PKGBUILD` on the AUR that resolves a real, working install.
- Both paths need nothing beyond GitHub itself and the AUR — no new
  repo/registry to run.

**Non-Goals:**
- No apt/dnf repository (no `Release`/`Packages` index, no signing
  key for a repo) - explicitly ruled out by the proposal.
- No Homebrew, Snap, Flatpak, or other formats - not requested.
- No `-git` rolling AUR variant for now - one PKGBUILD, tracking
  tagged releases.

## Decisions

### Freeze to a single binary for .deb/.rpm; keep a "real" Python build for AUR

Two different install stories, deliberately:

- **`.deb`/`.rpm` via `nfpm`**: freeze the CLI with `PyInstaller` into
  one self-contained executable first, then have `nfpm` package just
  that binary (plus `LICENSE`/`README.md` as doc files). `nfpm` has no
  opinion on how the files it packages get built, and Debian/Fedora
  disagree on Python package naming and available versions for this
  project's dependencies (`caldav`, `icalendar`, `httpx`) - depending
  on distro `python3-*` packages would mean chasing two different
  naming schemes and version skews. A frozen binary sidesteps all of
  that: the `.deb`/`.rpm` declares no Python dependency at all.
- **AUR `PKGBUILD`**: build for real - `python -m build` a wheel, then
  `python -m installer` it, with `depends=(python python-caldav
  python-httpx python-icalendar ...)` on real Arch packages. Arch
  users and AUR convention expect this; a frozen binary in a PKGBUILD
  is against AUR norms and would likely draw a comment/flag on the
  package page. Arch's `python-*` packages track upstream closely
  enough that this isn't the naming/version problem the `.deb`/`.rpm`
  path has.

Alternative considered: use `PyInstaller` (or `shiv`/`pex`) uniformly,
including for the AUR package. Rejected - it works, but ships against
AUR packaging norms for no real benefit, since Arch's dependency story
is already clean.

### Version comes from the release tag, not hand-maintained

`release-please` already owns versioning
(`release-please-config.json`, `include-v-in-tag: true`). The packaging
step reads `needs.release-please.outputs.tag_name`, strips the leading
`v` for `nfpm`'s `version:` field, and the same value drives the
`PKGBUILD`'s `pkgver` and the release-tarball URL. Nothing about the
version is decided in this change's own files.

### AUR push happens from the same release job, not by hand

Mirrors what `goreleaser`'s own `aurs:` publisher would do if this repo
had `goreleaser` (the proposal's instruction to use `nfpms:` there
implies this is the equivalent end state to aim for). A step in the
same `release_created`-gated job: bump `pkgver`/`pkgrel` and the
tarball checksum in `PKGBUILD`, regenerate `.SRCINFO`
(`makepkg --printsrcinfo`), commit, and push over SSH to
`ssh://aur@aur.archlinux.org/movie-planner.git`. This is "the release
job" in the sense the global convention already carves out an
exception for (unattended commits are otherwise off-limits) - it's
scoped to the one file this step owns, same as the `CHANGELOG.md`/
version-bump commit release-please already makes.

AUR has no per-package deploy keys - all AUR git access goes through
the single `aur@aur.archlinux.org` system user, and push authorization
to a given `pkgbase` is governed by that account's maintainer list on
the AUR web app, not by which key was used. So this doesn't need a new
keypair at all: a shared `aur-ci` key already exists, is already
registered on Ryan's AUR account, and already backs the same push
pattern for other repos (hush-hush, washy-washy-cli,
linkwarden-obsidian-sync). This change only needs that key made
available as the `AUR_SSH_KEY` secret on `alrayyes/movie-planner`
specifically - a repo-secret grant only Ryan can make, not a new
credential to provision; see tasks.md.

### Provenance on the new artifacts, no cosign

Add `actions/attest-build-provenance` to the packaging step, attesting
the `.deb`/`.rpm` (and the frozen binary, if built as a separate
build/attest step) - the existing unconditional-provenance rule for
every GitHub repo. No `cosign`: that convention is tied to
`goreleaser`, which this repo doesn't use, and standalone `cosign` is
explicitly "decline until a real consumer verifies" per the same rule
set. The AUR side needs nothing extra - `makepkg` verifies the
tarball against the checksum already committed to `PKGBUILD`, and
that checksum is computed straight from the GitHub release asset
`actions/attest-build-provenance` already covers.

### Man page generated from the CLI, not hand-written

`movie-planner` is a `Typer` app, which is built on `Click`. `click-man`
reads a `Click` command/group straight from the running code
(`typer.main.get_command(app)` gives it something to point at) and
writes a roff man page, so the page can't drift out of sync with the
actual `--help` output the way a hand-maintained one would. A single
checked-in `scripts/generate-man.sh` (mirroring how `scripts/lint-*.sh`
already work in this repo) runs `click-man` and writes
`man/movie-planner.1` - both the `nfpm` build step and the AUR
`PKGBUILD`'s `package()` function call the same script, so the two
packages can't end up with different man pages. `nfpm.yaml` and the
`PKGBUILD` each place the (gzip-compressed, standard for both Debian
and Arch) result at `usr/share/man/man1/movie-planner.1.gz`.

Alternative considered: hand-write a man page in `scdoc` or raw roff.
Rejected - it's one more place `--help` text has to be kept in sync by
hand, for no benefit over generating it from the source of truth.

### CI installs and runs what it builds, on every package format

`nfpm package` succeeding only proves a `.deb`/`.rpm` file got written,
not that installing it leaves a working `movie-planner` behind - a bad
`contents:` path or a missing man-page file would still "succeed" at
the packaging step. The release job's packaging step therefore also,
in ephemeral containers:

- `dpkg -i` the `.deb` in a `debian`/`ubuntu` container, `rpm -i` the
  `.rpm` in a `fedora`/`rockylinux` one, and run `movie-planner --help`
  and `man -w movie-planner` in each afterward.
- Run `makepkg` against the `PKGBUILD` inside an `archlinux` container
  *before* pushing anything to AUR, so a real Python-dependency or
  build-step regression is caught here rather than reported by an AUR
  user days later.

This runs as part of the same `release_created`-gated job, right after
the packages are built and before either the GitHub Release upload or
the AUR push - a broken package now blocks its own release rather than
shipping and getting caught after the fact.

### Installation instructions move to their own doc

README's Installation section already covers a checkout, `pipx`/`pip`,
and Docker; adding AUR, `.deb`, and `.rpm` on top of that would leave
the README mostly about how to install the thing rather than what it
is. Per this repo's own documentation conventions, something that
outgrows the README moves into `docs/` rather than being pasted into
it - so this change adds `docs/INSTALL.md` covering every install
method (checkout, `pipx`/`pip`, Docker, AUR, `.deb`, `.rpm`) in one
place, and trims the README's Installation section to a couple of
lines plus a link, the same shape `CONTRIBUTING.md` already gets from
the README.

### Pinning

- `PyInstaller`: exact version in whatever step installs it (e.g. a
  pinned `uv add --dev pyinstaller==X.Y.Z` or an equivalent pinned
  pip install in the workflow step - decide the exact mechanism at
  implementation time against this repo's existing dependency-pinning
  pattern).
- `click-man`: exact version, added as a pinned dev dependency
  (`uv add --dev click-man==X.Y.Z`) the same way as any other Python
  dev tool this repo already has.
- The `debian`/`ubuntu`, `fedora`/`rockylinux`, and `archlinux`
  container images the new install-test step runs in: digest-pinned,
  same as the Dockerfile's own base images.
- `nfpm`: exact version, installed via a checksum- or digest-verified
  download rather than a floating `latest` tag or an unpinned
  third-party Action.
- Runner: `ubuntu-24.04`, matching every other job in this workflow
  already - no new base image.

## Risks / Trade-offs

- **[Frozen-binary glibc skew]** A `PyInstaller` build on
  `ubuntu-24.04` links against a newer glibc than some longer-lived
  distro releases ship. → Document the practical floor (oldest distro
  release verified to run the binary) in the README once tested;
  revisit a musl/older-base build only if a real report comes in.
- **[Two build paths to keep in sync]** The AUR package and the
  `.deb`/`.rpm` are built by genuinely different mechanisms (real
  Python build vs. frozen binary), so a dependency bump could pass one
  and silently break the other. → Both are exercised by the same
  release; the "verify against one real tagged release before closing
  the ticket" step in the proposal is exactly this check, and it's
  worth re-running whenever `caldav`/`httpx`/`icalendar` are bumped.
- **[New unattended-push surface]** Automating the AUR push from CI
  means a compromised or buggy workflow could push bad content to the
  AUR under Ryan's account - and unlike a repo-scoped deploy key, the
  shared `aur-ci` key is account-wide by AUR's own design, so this
  isn't limited to `movie-planner`'s `pkgbase` the way a GitHub deploy
  key would be. → Keep the step doing only the minimal
  bump/regenerate/commit/push sequence, same mitigation already in use
  for the other repos sharing this key.

## Open Questions

- `pyproject.toml` currently lists `maintainer@example.invalid` as the
  author email. Both `nfpm`'s maintainer field and a PKGBUILD's
  `# Maintainer:` comment expect a real, reachable address. Doesn't
  change the approach or task breakdown - just needs a real address
  supplied before either package metadata is finalized.
- Exact `nfpm` install/pin mechanism (direct binary download with
  checksum vs. some other verified source) - resolve during
  implementation against what's actually available, not decided here.
- None outstanding - the AUR credential question above resolved to
  "reuse the existing shared `aur-ci` key," confirmed via the dotfiles
  session that manages it.
