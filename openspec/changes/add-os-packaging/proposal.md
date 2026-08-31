## Why

Right now the only ways to get `movie-planner` are a checkout with `uv
sync`, or `pipx install git+https://...` — nothing a package manager can
resolve or a distro's update mechanism can track. Arch and
Debian/RPM-based installs are the two most requested shapes for a CLI
like this, and both can be covered with almost no extra hosting: an AUR
`PKGBUILD` for Arch, plus `.deb`/`.rpm` files attached directly to
GitHub Releases for everything else — no apt/dnf repo to run, just
`dpkg -i`/`rpm -i` against a downloaded file.

## What Changes

- File the GitHub issue for this work first (four-part shape), per the
  personal-project convention — done as part of this change's own
  tracking, not left for later.
- Add `nfpm` as a standalone step in the existing `release` GitHub
  Actions job (this repo has no `goreleaser`, so there's no `nfpms:`
  block to hook into) that builds `.deb` and `.rpm` packages and
  uploads them as assets on the GitHub Release `release-please` already
  creates.
- Add a `PKGBUILD` (and its generated `.SRCINFO`) that builds from a
  tagged GitHub release tarball (`https://github.com/alrayyes/movie-planner/archive/movie-planner-vX.Y.Z.tar.gz`),
  pushed to this package's own AUR git repo
  (`ssh://aur@aur.archlinux.org/movie-planner.git`) — not committed to
  this project's repo.
- Add `actions/attest-build-provenance` to the new packaging step, per
  the existing unconditional-provenance rule for GitHub repos; no
  cosign, since that's a `goreleaser`-only convention this repo doesn't
  use.
- Pin `nfpm`'s version (and any base image the packaging step runs in)
  exactly, per the standing pin-every-dependency rule.
- Generate a man page from the CLI's own `--help` output and ship it
  in the `.deb`, the `.rpm`, and the AUR package alike, so `man
  movie-planner` works regardless of install method.
- Add CI coverage that actually installs the built `.deb`/`.rpm` (and
  test-builds the `PKGBUILD`) rather than only checking that `nfpm`
  produced files — a package that builds but doesn't install, or
  installs but doesn't run, is otherwise only caught by hand against a
  real release.
- Add a new `docs/INSTALL.md` with per-format install instructions
  once each path is verified against a real tagged release, and shrink
  `README.md`'s Installation section to a link plus the checkout/
  `pipx`/Docker basics it already documents.

## Capabilities

### New Capabilities

- `packaging`: observable guarantees about how `movie-planner` can be
  installed — a `PKGBUILD` resolvable from the AUR, `.deb`/`.rpm`
  files attached to every GitHub Release, a man page shipped with
  every install method, and CI that verifies a built package actually
  installs and runs before it's ever published.

### Modified Capabilities

None — no existing capability's requirements change.

## Impact

- `.github/workflows/release.yml` — new job/step: build `.deb`/`.rpm`
  with `nfpm`, attest provenance, upload as release assets.
- New `nfpm` config file (e.g. `nfpm.yaml`) at the repo root.
- New `PKGBUILD` + `.SRCINFO`, living in a separate, personally-owned
  AUR repo (not this repo).
- New `docs/INSTALL.md` covering every install method; `README.md`'s
  Installation section shrinks to a couple of lines plus a link.
- `pyproject.toml` — the placeholder maintainer email
  (`maintainer@example.invalid`) needs a real address before it can
  appear in a `PKGBUILD`'s `# Maintainer:` line or an `nfpm` package's
  maintainer field; flagged as an open question in `design.md`.
- New GitHub issue tracking this work end-to-end.
- New `openspec/changes/add-os-packaging/specs/packaging/spec.md`
  delta, becoming `openspec/specs/packaging/spec.md` on archive.
