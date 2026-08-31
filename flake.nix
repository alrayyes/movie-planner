{
  description = "CLI that logs watched movies and syncs them to a CalDAV calendar";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        # nixos-unstable's python3 is already 3.14, but its uv-build
        # (0.11.28 as of writing) is older than this project's own
        # `[build-system] requires = ["uv-build>=0.12.5,<0.13"]` —
        # confirmed live: `buildPythonApplication`'s pypa build hook
        # enforces that range and refuses the older one outright
        # ("Unmet dependencies ... found: 0.11.28"). Overridden here
        # to the exact version this repo already pins uv itself to
        # elsewhere, built the same way nixpkgs' own uv-build
        # derivation is (rustPlatform + maturin), just at a newer tag.
        python3 = pkgs.python3.override {
          packageOverrides = _self: super: {
            uv-build = super.uv-build.overrideAttrs (old: rec {
              version = "0.12.7";
              src = pkgs.fetchFromGitHub {
                owner = "astral-sh";
                repo = "uv";
                tag = version;
                hash = "sha256-RprHadjzR5LsiYYhryIGOiIQkRKVWJwyE63UXrzN62g=";
              };
              cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
                inherit (old) pname;
                inherit version src;
                hash = pkgs.lib.fakeHash;
              };
            });
          };
        };
        # Kept in sync with pyproject.toml's [project].version by hand —
        # release-please owns that file, not this one.
        version = "0.7.0";

        # Not in nixpkgs at all (confirmed: no click-man attribute in
        # python3Packages) — a small enough package (its only
        # dependency is click, already in nixpkgs) to vendor directly
        # rather than drop the man-page generation it enables.
        clickMan = python3.pkgs.buildPythonPackage {
          pname = "click-man";
          version = "0.5.1";
          format = "wheel";
          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/e1/37/34e03579eb583a587edba458599af6d82715a617e685dbe2ff30e4238930/click_man-0.5.1-py3-none-any.whl";
            sha256 = "ed63caf6d6bf04f2b1fb198a1a764daea9785ad29f303b2962418a417541a6ce";
          };
          propagatedBuildInputs = [ python3.pkgs.click ];
          doCheck = false;
        };
      in
      {
        packages.default = python3.pkgs.buildPythonApplication {
          pname = "movie-planner";
          inherit version;
          pyproject = true;

          src = ./.;

          # This project's own build backend (astral-sh/uv's uv_build),
          # same as every other packaging path in this repo.
          build-system = [ python3.pkgs.uv-build ];

          # Depends on nixpkgs' own versions of these rather than
          # vendoring pyproject.toml's exact pins — nixpkgs versions its
          # Python packages itself, the same tradeoff the AUR PKGBUILD's
          # depends=() already makes for the same reason (see
          # openspec/changes/add-os-packaging/design.md).
          dependencies = with python3.pkgs; [
            caldav
            httpx
            icalendar
            questionary
            rapidfuzz
            typer
          ];

          nativeBuildInputs = [
            clickMan
            pkgs.installShellFiles
          ];

          # One man page per command and subcommand, generated straight
          # from the just-installed package — the same click-man
          # approach scripts/generate-man.sh uses for the .deb/.rpm/AUR
          # paths, just invoked directly since scripts/generate-man.sh
          # itself is uv-specific and needs network access Nix's
          # sandboxed build doesn't have.
          postInstall = ''
            PYTHONPATH="$out/${python3.sitePackages}:$PYTHONPATH" ${python3.interpreter} -c "
            import datetime
            import typer.main
            from click_man.core import write_man_pages
            from movie_planner.cli import app
            write_man_pages('movie-planner', typer.main.get_command(app), version='${version}', target_dir='.', date=datetime.date.today())
            "
            for page in ./*.1; do
              installManPage "$page"
            done
          '';

          # The test suite spins up a real Baikal container via
          # testcontainers, which needs a Docker daemon Nix's sandboxed
          # build doesn't have. CI already runs the full suite outside
          # Nix; this build only proves the package itself is correct.
          doCheck = false;

          meta = {
            description = "CLI that logs watched movies and syncs them to a CalDAV calendar";
            homepage = "https://github.com/alrayyes/movie-planner";
            license = pkgs.lib.licenses.gpl3Only;
            mainProgram = "movie-planner";
          };
        };

        apps.default = flake-utils.lib.mkApp { drv = self.packages.${system}.default; };
      }
    );
}
