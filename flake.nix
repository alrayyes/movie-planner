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
        python3 = pkgs.python3; # nixos-unstable's python3 is already 3.14
        # Kept in sync with pyproject.toml's [project].version by hand —
        # release-please owns that file, not this one.
        version = "0.5.1";
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
            python3.pkgs.click-man
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
