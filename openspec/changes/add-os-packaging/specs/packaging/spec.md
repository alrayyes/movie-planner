## Purpose

Lets someone install `movie-planner` through their own package manager
instead of a manual checkout — an AUR package for Arch, and `.deb`/
`.rpm` files attached directly to each GitHub Release for everything
else.

## ADDED Requirements

### Requirement: GitHub Release carries installable Linux packages
Every GitHub Release the project publishes SHALL include a `.deb` and
an `.rpm` file as release assets, each matching the release's version.

#### Scenario: New release is published
- **WHEN** a new version of `movie-planner` is released on GitHub
- **THEN** the release's assets include a `.deb` file and an `.rpm`
  file, both reporting that release's version

### Requirement: Installing the .deb or .rpm needs no separate Python setup
The system SHALL make `movie-planner` runnable immediately after
`dpkg -i` (or the `.deb`) or `rpm -i` (the `.rpm`) completes, without
the user separately installing Python or any of the project's Python
dependencies.

#### Scenario: Fresh machine, no Python installed
- **WHEN** a user with no Python interpreter installed runs
  `dpkg -i movie-planner_*.deb` (or the equivalent `rpm -i`)
- **THEN** the `movie-planner` command runs successfully afterward
  with no additional installation step

### Requirement: Package resolvable from the AUR
The project SHALL be installable from the Arch User Repository under
the name `movie-planner`, resolving a real, working install of the
released version through the distro's own Python packages.

#### Scenario: Install via an AUR helper
- **WHEN** a user runs an AUR helper (or `git clone` +
  `makepkg -si`) against the `movie-planner` AUR package
- **THEN** the package builds and installs successfully, and the
  resulting `movie-planner` command matches the version the PKGBUILD
  declares

### Requirement: A man page ships with every install method
Every install method (`.deb`, `.rpm`, AUR) SHALL install a man page for
`movie-planner`, generated from the CLI's own help output rather than
maintained separately, so it can't drift out of sync with the tool it
documents.

#### Scenario: Man page available after install
- **WHEN** a user installs `movie-planner` through any of the three
  supported methods
- **THEN** `man movie-planner` shows a page describing the CLI's
  commands and options

### Requirement: A built package is verified before it's published
The release process SHALL install each built package (`.deb` on a
Debian-family system, `.rpm` on an RPM-family system) and confirm
`movie-planner` runs successfully afterward, and SHALL build the AUR
`PKGBUILD` and confirm it installs successfully, before that release's
packages are published or pushed to the AUR.

#### Scenario: A package that builds but fails to install
- **WHEN** an `nfpm`-built `.deb` or `.rpm` fails to install, or an
  installed package's `movie-planner` command fails to run, on a given
  release
- **THEN** that release's packaging step fails and neither the GitHub
  Release assets nor the AUR push for that release are published

### Requirement: Released packages are provenance-attested
Every `.deb` and `.rpm` release asset SHALL carry a build provenance
attestation that verifiably ties it to the GitHub Actions run that
produced it.

#### Scenario: Verifying a downloaded package
- **WHEN** a user runs `gh attestation verify` against a downloaded
  `.deb` or `.rpm` release asset
- **THEN** verification succeeds and confirms the artifact was built
  by this project's release workflow
