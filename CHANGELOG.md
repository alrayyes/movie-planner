# Changelog

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
