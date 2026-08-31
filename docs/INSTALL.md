# Installing movie-planner

Every method below installs the `movie-planner` command. Pick whichever
matches your system; none of them need any of the others.

## Arch Linux (AUR)

```sh
paru -S movie-planner
```

An AUR helper (`paru`, `yay`, or similar) is the easiest path — two of
`movie-planner`'s dependencies (`python-questionary`, `python-click-man`)
are themselves AUR-only, and a bare `makepkg -si` can't resolve those on
its own. Without a helper, build them first:

```sh
for pkg in python-questionary python-click-man; do
  git clone "https://aur.archlinux.org/$pkg.git"
  (cd "$pkg" && makepkg -si)
done
git clone https://aur.archlinux.org/movie-planner.git
cd movie-planner
makepkg -si
```

Builds for real against Arch's own `python-*` packages — see the
[`PKGBUILD`](../PKGBUILD) in this repo for the exact dependencies (kept
here for reference and review; the actual AUR package lives in its own
git repo, updated by this project's release job).

## Debian, Ubuntu and other `.deb`-based distros

Download the `.deb` from the
[latest release](https://github.com/alrayyes/movie-planner/releases/latest)
and install it:

```sh
curl -LO https://github.com/alrayyes/movie-planner/releases/latest/download/movie-planner_VERSION_amd64.deb
sudo dpkg -i movie-planner_VERSION_amd64.deb
```

Replace `VERSION` with the version you downloaded (matching the
filename on the release page). No separate Python install needed — the
package bundles everything it depends on.

## Fedora, RHEL and other `.rpm`-based distros

Download the `.rpm` from the
[latest release](https://github.com/alrayyes/movie-planner/releases/latest)
and install it:

```sh
curl -LO https://github.com/alrayyes/movie-planner/releases/latest/download/movie-planner-VERSION-1.x86_64.rpm
sudo rpm -i movie-planner-VERSION-1.x86_64.rpm
```

Replace `VERSION` with the version you downloaded. Same as the `.deb`:
no separate Python install needed.

## Verifying a downloaded `.deb`/`.rpm`

Every release asset carries a build provenance attestation tying it to
the GitHub Actions run that produced it:

```sh
gh attestation verify movie-planner_VERSION_amd64.deb --repo alrayyes/movie-planner
```

## From a checkout, or without a package manager

```sh
git clone https://github.com/alrayyes/movie-planner.git
cd movie-planner
uv sync
uv run movie-planner --help
```

Or install the command directly without keeping the checkout around —
this project isn't published to PyPI, so install straight from the repo:

```sh
pipx install git+https://github.com/alrayyes/movie-planner.git
```

`pip install` works the same way in place of `pipx` if you'd rather
manage the virtual environment yourself.

## Docker

A [Docker image](https://github.com/alrayyes/movie-planner/pkgs/container/movie-planner)
is published on every release too — mount your config and data
directories in, and run as your own user (not the image's built-in one)
so it can write to them. The flags below drop every capability the tool
doesn't need, block privilege escalation, make the root filesystem
read-only (with a `tmpfs` for the one path that needs to write), and cap
resource usage:

```sh
docker run --rm -it --user "$(id -u):$(id -g)" -e HOME=/home/movieplanner \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only \
  --tmpfs /tmp --memory=256m --cpus=1 \
  -v ~/.config/movie-planner:/home/movieplanner/.config/movie-planner \
  -v ~/.local/share/movie-planner:/home/movieplanner/.local/share/movie-planner \
  ghcr.io/alrayyes/movie-planner:latest --help
```
