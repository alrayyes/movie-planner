# Changelog

## [0.21.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.21.2...movie-planner-v0.21.3) (2026-09-05)


### Documentation

* **import:** add a JSON Schema for the import row shape ([#136](https://github.com/alrayyes/movie-planner/issues/136)) ([8cff65d](https://github.com/alrayyes/movie-planner/commit/8cff65d3ce62bf72767b629828025c4a2285b598))

## [0.21.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.21.1...movie-planner-v0.21.2) (2026-09-05)


### Documentation

* link movie-planner-web and add a --help screenshot ([#135](https://github.com/alrayyes/movie-planner/issues/135)) ([99000dd](https://github.com/alrayyes/movie-planner/commit/99000dd3735513d17caa542089e2d3e6c2b2843f))

## [0.21.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.21.0...movie-planner-v0.21.1) (2026-09-05)


### Bug Fixes

* **omdb:** restrict title lookups to movies ([#133](https://github.com/alrayyes/movie-planner/issues/133)) ([e360197](https://github.com/alrayyes/movie-planner/commit/e3601973601ca553088e762019a808fee5ba4c07)), closes [#132](https://github.com/alrayyes/movie-planner/issues/132)

## [0.21.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.20.0...movie-planner-v0.21.0) (2026-09-05)


### Features

* **import:** accept OMDb-derived fields directly on a row ([#130](https://github.com/alrayyes/movie-planner/issues/130)) ([06b865f](https://github.com/alrayyes/movie-planner/commit/06b865f88cc2675ed268af9a535ffe6434f92196))

## [0.20.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.19.1...movie-planner-v0.20.0) (2026-09-05)


### Features

* fetch director, actors, genre, and release year from OMDb ([#127](https://github.com/alrayyes/movie-planner/issues/127)) ([47240fa](https://github.com/alrayyes/movie-planner/commit/47240fac6a614f2f0de67dbab335808e6dd51b74))

## [0.19.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.19.0...movie-planner-v0.19.1) (2026-09-05)


### Bug Fixes

* sync refresh checks every OMDb field, not just imdb_rating ([#125](https://github.com/alrayyes/movie-planner/issues/125)) ([589374e](https://github.com/alrayyes/movie-planner/commit/589374e02343eb458e647dc19dcbbfe45e317809)), closes [#124](https://github.com/alrayyes/movie-planner/issues/124)

## [0.19.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.18.0...movie-planner-v0.19.0) (2026-09-05)


### Features

* **omdb:** try a year-scoped title search before falling back ([#122](https://github.com/alrayyes/movie-planner/issues/122)) ([3e281b7](https://github.com/alrayyes/movie-planner/commit/3e281b7b501bf369796e8cc44c24aa4da218faeb)), closes [#87](https://github.com/alrayyes/movie-planner/issues/87)

## [0.18.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.17.1...movie-planner-v0.18.0) (2026-09-05)


### Features

* switch CalDAV UID generation from uuid4 to uuid7 ([#120](https://github.com/alrayyes/movie-planner/issues/120)) ([02ab70a](https://github.com/alrayyes/movie-planner/commit/02ab70a830c913c85cbf8f453486e5effc514a66)), closes [#118](https://github.com/alrayyes/movie-planner/issues/118)

## [0.17.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.17.0...movie-planner-v0.17.1) (2026-09-05)


### Bug Fixes

* persist and push poster_url, detect Ghostty for inline posters ([#117](https://github.com/alrayyes/movie-planner/issues/117)) ([bf5adf3](https://github.com/alrayyes/movie-planner/commit/bf5adf3ef6d4a4146f2a00679ccfc2f075fc1392)), closes [#114](https://github.com/alrayyes/movie-planner/issues/114)

## [0.17.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.16.0...movie-planner-v0.17.0) (2026-09-05)


### Features

* add a chain/location structure for venues ([#113](https://github.com/alrayyes/movie-planner/issues/113)) ([5a941b5](https://github.com/alrayyes/movie-planner/commit/5a941b524f78bf54fd233834b1a5706b7efbdb25)), closes [#111](https://github.com/alrayyes/movie-planner/issues/111)

## [0.16.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.15.0...movie-planner-v0.16.0) (2026-09-05)


### Features

* add a free-text notes field to logged entries ([#110](https://github.com/alrayyes/movie-planner/issues/110)) ([565b214](https://github.com/alrayyes/movie-planner/commit/565b21459c4ea8387539125d94c8760a54d5d55c))

## [0.15.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.14.0...movie-planner-v0.15.0) (2026-09-05)


### Features

* **cli:** add show command with structured output and inline posters ([#107](https://github.com/alrayyes/movie-planner/issues/107)) ([fbe50f9](https://github.com/alrayyes/movie-planner/commit/fbe50f9e38432f1ba6df66e7ae6fcf9af18bfccb)), closes [#106](https://github.com/alrayyes/movie-planner/issues/106)

## [0.14.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.13.1...movie-planner-v0.14.0) (2026-09-05)


### Features

* **cli:** add --force to sync refresh to re-fetch existing ratings ([#104](https://github.com/alrayyes/movie-planner/issues/104)) ([aeadc48](https://github.com/alrayyes/movie-planner/commit/aeadc484ef9b54bc4b1a2497a16e75756215df59)), closes [#103](https://github.com/alrayyes/movie-planner/issues/103)

## [0.13.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.13.0...movie-planner-v0.13.1) (2026-09-05)


### Documentation

* publish the CalDAV data contract for movie-planner-web ([#101](https://github.com/alrayyes/movie-planner/issues/101)) ([5169c9c](https://github.com/alrayyes/movie-planner/commit/5169c9c61ee405083bf614e4c2efd3220882b817)), closes [#100](https://github.com/alrayyes/movie-planner/issues/100)

## [0.13.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.12.0...movie-planner-v0.13.0) (2026-09-05)


### Features

* **cli:** add --no-metadata to import for rate-limited bulk imports ([#96](https://github.com/alrayyes/movie-planner/issues/96)) ([0a88998](https://github.com/alrayyes/movie-planner/commit/0a889985c657ba85b78b2f1f59d687b84d73258d)), closes [#95](https://github.com/alrayyes/movie-planner/issues/95)

## [0.12.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.11.0...movie-planner-v0.12.0) (2026-09-05)


### Features

* **omdb:** auto-populate imdb_url and include it in calendar descriptions ([#93](https://github.com/alrayyes/movie-planner/issues/93)) ([59b8666](https://github.com/alrayyes/movie-planner/commit/59b8666e8a947988e4d4d7be4a69b89c13ec1aad)), closes [#92](https://github.com/alrayyes/movie-planner/issues/92)

## [0.11.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.10.2...movie-planner-v0.11.0) (2026-09-05)


### Features

* **cli:** scope sync refresh to a date range or single date ([#90](https://github.com/alrayyes/movie-planner/issues/90)) ([4284819](https://github.com/alrayyes/movie-planner/commit/4284819ec25bd173da8b58b3e6db86131850d7be)), closes [#89](https://github.com/alrayyes/movie-planner/issues/89)

## [0.10.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.10.1...movie-planner-v0.10.2) (2026-09-03)


### Documentation

* fix stale openspec change paths after archiving add-os-packaging ([#75](https://github.com/alrayyes/movie-planner/issues/75)) ([404bc6d](https://github.com/alrayyes/movie-planner/commit/404bc6dd587ced8e9a0605894c11aec02c39afc9))

## [0.10.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.10.0...movie-planner-v0.10.1) (2026-09-03)


### Documentation

* **openspec:** archive add-pathe-email-import, sync its specs ([#73](https://github.com/alrayyes/movie-planner/issues/73)) ([0fed883](https://github.com/alrayyes/movie-planner/commit/0fed883eb74073f6817150063e9befdaf674ef0b))

## [0.10.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.9.3...movie-planner-v0.10.0) (2026-09-03)


### Features

* parse Pathé booking emails, and give calendar events real content ([#70](https://github.com/alrayyes/movie-planner/issues/70)) ([4660387](https://github.com/alrayyes/movie-planner/commit/4660387b0f33486c1632f5b4d6e49b3da97589c2))

## [0.9.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.9.2...movie-planner-v0.9.3) (2026-09-01)


### Documentation

* **openspec:** archive add-os-packaging, sync the packaging spec ([#64](https://github.com/alrayyes/movie-planner/issues/64)) ([a186283](https://github.com/alrayyes/movie-planner/commit/a18628388fb31d24f135ef8acdbb274e5608aaff))

## [0.9.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.9.1...movie-planner-v0.9.2) (2026-09-01)


### Documentation

* add Nix/NixOS to docs/INSTALL.md, close out the Nix flake tasks ([#62](https://github.com/alrayyes/movie-planner/issues/62)) ([eaffb64](https://github.com/alrayyes/movie-planner/commit/eaffb6449d855158df9f7574d92a00945882a727))

## [0.9.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.9.0...movie-planner-v0.9.1) (2026-09-01)


### Bug Fixes

* **nix:** revert the broad mapAttrs doCheck override, add aiohttp ([#60](https://github.com/alrayyes/movie-planner/issues/60)) ([393991d](https://github.com/alrayyes/movie-planner/commit/393991d5272ac5473847605d393300a655487ebf))

## [0.9.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.8.3...movie-planner-v0.9.0) (2026-09-01)


### Features

* **config:** flag/env overrides, password_command, and audit follow-up ([#58](https://github.com/alrayyes/movie-planner/issues/58)) ([f58a32b](https://github.com/alrayyes/movie-planner/commit/f58a32bcbb98ef562169b280d2b3613721738eb0))

## [0.8.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.8.2...movie-planner-v0.8.3) (2026-09-01)


### Bug Fixes

* **nix:** commit flake.lock and cache the nix store between CI runs ([#56](https://github.com/alrayyes/movie-planner/issues/56)) ([aa7b411](https://github.com/alrayyes/movie-planner/commit/aa7b41184b00991ae4777e22aa97e47c11aaff0e))

## [0.8.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.8.1...movie-planner-v0.8.2) (2026-09-01)


### Bug Fixes

* **nix:** relax the exact-pin runtime deps check for icalendar/typer ([#54](https://github.com/alrayyes/movie-planner/issues/54)) ([d8968de](https://github.com/alrayyes/movie-planner/commit/d8968de7d749835ef3d556611b3c92e5663f8a67))

## [0.8.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.8.0...movie-planner-v0.8.1) (2026-09-01)


### Bug Fixes

* **nix:** disable checks on a flaky nixpkgs transitive test dependency ([#51](https://github.com/alrayyes/movie-planner/issues/51)) ([978b59f](https://github.com/alrayyes/movie-planner/commit/978b59f04119c221599d075a437fffd38f96c66c))
* **nix:** fill in the real uv-build source hash ([#49](https://github.com/alrayyes/movie-planner/issues/49)) ([fdb30c1](https://github.com/alrayyes/movie-planner/commit/fdb30c13fc5ff5128f7bceeceb6a021785eaef05))
* **release:** use a real-identity token for release-please and auto-merge ([#52](https://github.com/alrayyes/movie-planner/issues/52)) ([5e1066f](https://github.com/alrayyes/movie-planner/commit/5e1066f6cb1a164381e66e7fec0600137b50ccbf))

## [0.8.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.7.0...movie-planner-v0.8.0) (2026-08-31)


### Features

* add a Nix flake ([#44](https://github.com/alrayyes/movie-planner/issues/44)) ([6608b2b](https://github.com/alrayyes/movie-planner/commit/6608b2b3aec98151b2380db1375f3a1a07fc143d))


### Bug Fixes

* **nix:** override uv-build to the version this project needs ([#48](https://github.com/alrayyes/movie-planner/issues/48)) ([9e1b763](https://github.com/alrayyes/movie-planner/commit/9e1b76397a711776da798de08cec1d33e8621c48))


### Documentation

* add docs/INSTALL.md ([#46](https://github.com/alrayyes/movie-planner/issues/46)) ([9acf5fd](https://github.com/alrayyes/movie-planner/commit/9acf5fd542998164b907fb56224170030c37758d))

## [0.7.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.6.0...movie-planner-v0.7.0) (2026-08-31)


### Features

* add an AUR PKGBUILD ([#45](https://github.com/alrayyes/movie-planner/issues/45)) ([1a548ad](https://github.com/alrayyes/movie-planner/commit/1a548ad4a7dbf200317026f012db1abf1a90fb2d))


### Bug Fixes

* **ci:** strip release-please's real tag prefix for nfpm ([#43](https://github.com/alrayyes/movie-planner/issues/43)) ([76751a7](https://github.com/alrayyes/movie-planner/commit/76751a7370be6523b2e7f4ce1a6cd298b320d80b))
* **release:** add workflow_dispatch as a manual recovery trigger ([#41](https://github.com/alrayyes/movie-planner/issues/41)) ([363ad65](https://github.com/alrayyes/movie-planner/commit/363ad65562445e4550d079ad6008d281d927d06b))

## [0.6.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.5.1...movie-planner-v0.6.0) (2026-08-31)


### Features

* add .deb/.rpm packaging via nfpm ([#39](https://github.com/alrayyes/movie-planner/issues/39)) ([7e3b0a4](https://github.com/alrayyes/movie-planner/commit/7e3b0a498937ad6c3b2988b7d32d7f6864a04543))

## [0.5.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.5.0...movie-planner-v0.5.1) (2026-08-31)


### Bug Fixes

* bring repo in line with a few standing conventions ([#33](https://github.com/alrayyes/movie-planner/issues/33)) ([7fc5a05](https://github.com/alrayyes/movie-planner/commit/7fc5a05eb524ca388cb350c3bd63f45dd7be7039))

## [0.5.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.4.1...movie-planner-v0.5.0) (2026-08-30)


### Features

* **cli:** add an init command to write a starter config.toml ([#29](https://github.com/alrayyes/movie-planner/issues/29)) ([f6c553a](https://github.com/alrayyes/movie-planner/commit/f6c553a553b993416b84aae3b65857eea5744115)), closes [#28](https://github.com/alrayyes/movie-planner/issues/28)

## [0.4.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.4.0...movie-planner-v0.4.1) (2026-08-30)


### Documentation

* **changelog:** deduplicate entries caused by merge-commit PRs ([#26](https://github.com/alrayyes/movie-planner/issues/26)) ([6d75144](https://github.com/alrayyes/movie-planner/commit/6d75144e0ec8e9e7241f78b14beb526e4a960df1))

## [0.4.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.3.1...movie-planner-v0.4.0) (2026-08-30)


### Features

* **docker:** publish a Docker image alongside each release ([f98914c](https://github.com/alrayyes/movie-planner/commit/f98914cf3e66995bd9629d80664fdcf267762dc6))

## [0.3.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.3.0...movie-planner-v0.3.1) (2026-08-30)


### Documentation

* add pip/pipx install instructions to the README ([89b3088](https://github.com/alrayyes/movie-planner/commit/89b3088496cc3caa29346bbcd9168bf8acf3be37))

## [0.3.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.2.0...movie-planner-v0.3.0) (2026-08-30)


### Features

* **cli:** wire log, list, update, delete, locations, import, and sync retry commands ([d5f299c](https://github.com/alrayyes/movie-planner/commit/d5f299c9a5f1fb0b40a2fb05f2c53d32d9942654))

## [0.2.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.1.0...movie-planner-v0.2.0) (2026-08-30)


### Features

* **calendar-sync:** push-only sync to a Baikal calendar ([665b5b7](https://github.com/alrayyes/movie-planner/commit/665b5b7731fdfcf3f237c668715b8dcee1479fa5))
* **ci:** upload coverage to Codecov ([#13](https://github.com/alrayyes/movie-planner/issues/13)) ([7aacb61](https://github.com/alrayyes/movie-planner/commit/7aacb61ad8c42a5937065e26d1e48e4600dc59f9))
* **config:** load CalDAV, OMDb, and storage settings from TOML ([b441985](https://github.com/alrayyes/movie-planner/commit/b44198561399a9e98aa17c7949459fe09d370dc9))
* **duplicates:** fuzzy title matching gated to the same day ([963a371](https://github.com/alrayyes/movie-planner/commit/963a371e541c00480c933918f9080565749e4b6b))
* **import:** bulk import from CSV, JSON, and org-mode ([fe9c97c](https://github.com/alrayyes/movie-planner/commit/fe9c97c5c6b272588f93061192a2a25637bc57ba))
* **metadata:** add OMDb ratings and manual Letterboxd link/rating ([286caf2](https://github.com/alrayyes/movie-planner/commit/286caf2c19ac05574ae0322c26324c968151b080))
* **store:** local SQLite store for entries, media, and venues ([e95555c](https://github.com/alrayyes/movie-planner/commit/e95555ce48be3db057aacb531ae83249f16cb0f2))


### Bug Fixes

* **duplicates:** add caldav_uid to the test Entry helper ([8126873](https://github.com/alrayyes/movie-planner/commit/81268738a438958cc0bcb454cfc3779e9ecc525c))
* **import:** drop org-mode support, use fictional test/example data ([1d26643](https://github.com/alrayyes/movie-planner/commit/1d26643f4cb7fdfc2063daf699f070bf0ee7da69))
* replace real viewing history with fictional data in tests/specs ([d1f540a](https://github.com/alrayyes/movie-planner/commit/d1f540a9ac2d7a6b555ec5ec7fd39daf55c7efc4))
* **store:** close SQLite connections opened by tests ([137a864](https://github.com/alrayyes/movie-planner/commit/137a8648ef7a4dded33dd622af8cbdf1b183a67b))
* use scaffold's original bun lockfile and exclude openspec/ from prose lint ([c7cf144](https://github.com/alrayyes/movie-planner/commit/c7cf14427b7bda920dbb6bd0f6e086b364c7b111))
