#!/usr/bin/env bash
# python-questionary and python-click-man aren't in Arch's official
# repos, only the AUR — pacman can't install them directly, so this
# builds and installs both from source the same way an AUR helper
# would. Shared by the CI dry run and the release job so a real
# `makepkg` build isn't the only one exercising this PKGBUILD.
set -euo pipefail

for pkg in python-questionary python-click-man; do
  git clone --depth 1 "https://aur.archlinux.org/${pkg}.git" "/tmp/${pkg}"
  (cd "/tmp/${pkg}" && makepkg -si --noconfirm --nocheck)
done
