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

# Arch's python-caldav 3.7.0 imports calendaring_config but doesn't depend
# on it, and no Arch or AUR package provides it (#491). Build a local
# package from the pinned PyPI wheel so caldav imports. Remove this once
# Arch ships the dependency or an AUR package exists.
cc_ver=0.5.0
cc_sha=c5e1f6ffaf428a59b0e1373d951eb8e7fd9f49924912e65548cc2803e73a8646
cc_dir=/tmp/python-calendaring-config
mkdir -p "$cc_dir"
cat > "$cc_dir/PKGBUILD" <<PKGBUILD
pkgname=python-calendaring-config
pkgver=${cc_ver}
pkgrel=1
pkgdesc="Shared calendar config loader (stand-in for caldav's missing dependency)"
arch=('any')
url="https://pypi.org/project/calendaring-config/"
license=('GPL-3.0-or-later')
depends=('python' 'python-yaml')
makedepends=('python-installer')
source=("https://files.pythonhosted.org/packages/5f/17/3e4e04e3a344b2260139e64f53d34e95163e02b128b6066753540d5df524/calendaring_config-${cc_ver}-py3-none-any.whl")
sha256sums=('${cc_sha}')
noextract=("calendaring_config-${cc_ver}-py3-none-any.whl")
package() {
  python -m installer --destdir="\$pkgdir" "\$srcdir/calendaring_config-${cc_ver}-py3-none-any.whl"
}
PKGBUILD
(cd "$cc_dir" && makepkg -si --noconfirm --nocheck)
