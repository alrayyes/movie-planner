# Changelog

## [0.4.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.3.1...movie-planner-v0.4.0) (2026-08-30)


### Features

* **docker:** publish a Docker image alongside each release ([f98914c](https://github.com/alrayyes/movie-planner/commit/f98914cf3e66995bd9629d80664fdcf267762dc6))
* **docker:** publish a Docker image alongside each release ([d1ff900](https://github.com/alrayyes/movie-planner/commit/d1ff900ddce305bd50f3215a779a0e30c2514845))

## [0.3.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.3.0...movie-planner-v0.3.1) (2026-08-30)


### Documentation

* add pip/pipx install instructions to the README ([89b3088](https://github.com/alrayyes/movie-planner/commit/89b3088496cc3caa29346bbcd9168bf8acf3be37))
* add pip/pipx install instructions to the README ([f6267e3](https://github.com/alrayyes/movie-planner/commit/f6267e3df455ff9b8c51b17a4076792f2a58beaa))

## [0.3.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.2.0...movie-planner-v0.3.0) (2026-08-30)


### Features

* **cli:** wire log, list, update, delete, locations, import, and sync retry commands ([d5f299c](https://github.com/alrayyes/movie-planner/commit/d5f299c9a5f1fb0b40a2fb05f2c53d32d9942654))
* **cli:** wire log, list, update, delete, locations, import, and sync retry commands ([6ba1160](https://github.com/alrayyes/movie-planner/commit/6ba1160b098a1b649ba4679ebd84c2d449888108)), closes [#17](https://github.com/alrayyes/movie-planner/issues/17)

## [0.2.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.1.0...movie-planner-v0.2.0) (2026-08-30)


### Features

* **calendar-sync:** push-only sync to a Baikal calendar ([665b5b7](https://github.com/alrayyes/movie-planner/commit/665b5b7731fdfcf3f237c668715b8dcee1479fa5))
* **calendar-sync:** push-only sync to a Baikal calendar ([8432c76](https://github.com/alrayyes/movie-planner/commit/8432c7652083465f25a8296167bc537ef4206ebb))
* **ci:** upload coverage to Codecov ([#13](https://github.com/alrayyes/movie-planner/issues/13)) ([7aacb61](https://github.com/alrayyes/movie-planner/commit/7aacb61ad8c42a5937065e26d1e48e4600dc59f9))
* **config:** load CalDAV, OMDb, and storage settings from TOML ([b441985](https://github.com/alrayyes/movie-planner/commit/b44198561399a9e98aa17c7949459fe09d370dc9))
* **config:** load CalDAV, OMDb, and storage settings from TOML ([120af3d](https://github.com/alrayyes/movie-planner/commit/120af3d2c7e38e61575f5bed7f6f3dbe2e851d95))
* **duplicates:** fuzzy title matching gated to the same day ([963a371](https://github.com/alrayyes/movie-planner/commit/963a371e541c00480c933918f9080565749e4b6b))
* **duplicates:** fuzzy title matching gated to the same day ([ddab323](https://github.com/alrayyes/movie-planner/commit/ddab32362cc1fb24cb1783fccf4d604d7e2207e5))
* **import:** bulk import from CSV, JSON, and org-mode ([fe9c97c](https://github.com/alrayyes/movie-planner/commit/fe9c97c5c6b272588f93061192a2a25637bc57ba))
* **import:** bulk import from CSV, JSON, and org-mode ([40fd4fc](https://github.com/alrayyes/movie-planner/commit/40fd4fce4d7e15d076ebe8e524edb21b38297e68))
* **metadata:** add OMDb ratings and manual Letterboxd link/rating ([286caf2](https://github.com/alrayyes/movie-planner/commit/286caf2c19ac05574ae0322c26324c968151b080))
* **metadata:** add OMDb ratings and manual Letterboxd link/rating ([129f1a0](https://github.com/alrayyes/movie-planner/commit/129f1a09fe0a63bb08ef2779566aace2b533c7d6))
* **store:** local SQLite store for entries, media, and venues ([e95555c](https://github.com/alrayyes/movie-planner/commit/e95555ce48be3db057aacb531ae83249f16cb0f2))
* **store:** local SQLite store for entries, media, and venues ([1e48e13](https://github.com/alrayyes/movie-planner/commit/1e48e139b07d8d0fa53f39a922f17fb674dfa74c))


### Bug Fixes

* **duplicates:** add caldav_uid to the test Entry helper ([8126873](https://github.com/alrayyes/movie-planner/commit/81268738a438958cc0bcb454cfc3779e9ecc525c))
* **import:** drop org-mode support, use fictional test/example data ([1d26643](https://github.com/alrayyes/movie-planner/commit/1d26643f4cb7fdfc2063daf699f070bf0ee7da69))
* **import:** drop org-mode support, use fictional test/example data ([f155925](https://github.com/alrayyes/movie-planner/commit/f155925710c0c8bb16b5fc6276455dba338d4b45))
* replace real viewing history with fictional data in tests/specs ([d1f540a](https://github.com/alrayyes/movie-planner/commit/d1f540a9ac2d7a6b555ec5ec7fd39daf55c7efc4))
* replace real viewing history with fictional data in tests/specs ([540125b](https://github.com/alrayyes/movie-planner/commit/540125b8cd986be95ce5dff9cfd550e7335f2043))
* **store:** close SQLite connections opened by tests ([137a864](https://github.com/alrayyes/movie-planner/commit/137a8648ef7a4dded33dd622af8cbdf1b183a67b))
* use scaffold's original bun lockfile and exclude openspec/ from prose lint ([c7cf144](https://github.com/alrayyes/movie-planner/commit/c7cf14427b7bda920dbb6bd0f6e086b364c7b111))
