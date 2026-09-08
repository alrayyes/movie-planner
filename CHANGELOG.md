# Changelog

## [1.25.4](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.25.3...movie-planner-v1.25.4) (2026-09-08)


### Bug Fixes

* **mail-import:** close mail_import/cli.py mutmut gaps ([#323](https://github.com/alrayyes/movie-planner/issues/323)) ([df489c3](https://github.com/alrayyes/movie-planner/commit/df489c35072bdc6fa013d550201f4b2e959e13a6))

## [1.25.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.25.2...movie-planner-v1.25.3) (2026-09-08)


### Bug Fixes

* **mail-import:** close config.py mutmut gaps ([#322](https://github.com/alrayyes/movie-planner/issues/322)) ([425d080](https://github.com/alrayyes/movie-planner/commit/425d080ee50e91d70fd46d53410b447b327c42d7))
* **mail-import:** close maildir_client.py mutmut gaps ([#320](https://github.com/alrayyes/movie-planner/issues/320)) ([4488e29](https://github.com/alrayyes/movie-planner/commit/4488e29285a092cbd260ed38e3fa88f3cacdbb9b))

## [1.25.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.25.1...movie-planner-v1.25.2) (2026-09-08)


### Bug Fixes

* **mail-import:** close imap_client.py mutmut gaps ([#318](https://github.com/alrayyes/movie-planner/issues/318)) ([be25019](https://github.com/alrayyes/movie-planner/commit/be250199b37881706e8dddcdddc1ba495fb4d862))

## [1.25.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.25.0...movie-planner-v1.25.1) (2026-09-08)


### Bug Fixes

* **mail-import:** close mbox_client.py mutmut gaps ([#316](https://github.com/alrayyes/movie-planner/issues/316)) ([04fab14](https://github.com/alrayyes/movie-planner/commit/04fab14a83a25c27f7849222cc98d05a2c76870d))

## [1.25.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.24.3...movie-planner-v1.25.0) (2026-09-08)


### Features

* **tmdb:** enrich entries with full cast and other TMDb metadata ([#312](https://github.com/alrayyes/movie-planner/issues/312)) ([c040956](https://github.com/alrayyes/movie-planner/commit/c0409568cb9d18cc58a8782df703a6d28cf99193)), closes [#311](https://github.com/alrayyes/movie-planner/issues/311)


### Bug Fixes

* **sync-pull:** correctly parse venue name from a full-address LOCATION ([#315](https://github.com/alrayyes/movie-planner/issues/315)) ([189bb46](https://github.com/alrayyes/movie-planner/commit/189bb468867eddfa25f6492c14bef48856818030)), closes [#314](https://github.com/alrayyes/movie-planner/issues/314)

## [1.24.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.24.2...movie-planner-v1.24.3) (2026-09-08)


### Bug Fixes

* **mail-import:** close envelope.py and dispatch.py mutmut gaps ([#309](https://github.com/alrayyes/movie-planner/issues/309)) ([ddca0ef](https://github.com/alrayyes/movie-planner/commit/ddca0efdd44ef2a38998d98df242785585b19ff1))

## [1.24.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.24.1...movie-planner-v1.24.2) (2026-09-08)


### Documentation

* **testing:** correct the mutmut non-blocking rationale, track [#303](https://github.com/alrayyes/movie-planner/issues/303) ([#307](https://github.com/alrayyes/movie-planner/issues/307)) ([c06b3c9](https://github.com/alrayyes/movie-planner/commit/c06b3c900af5ee6645fd485dca051db4bdd412f6))

## [1.24.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.24.0...movie-planner-v1.24.1) (2026-09-08)


### Documentation

* **contributing:** scope real-setup verification to a small sample first ([#288](https://github.com/alrayyes/movie-planner/issues/288)) ([1b9a17b](https://github.com/alrayyes/movie-planner/commit/1b9a17b4152ff458a1d1df9a8f856e585da7bfdb))

## [1.24.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.23.1...movie-planner-v1.24.0) (2026-09-08)


### Features

* **calendar:** extend LOCATION to a full street address ([#284](https://github.com/alrayyes/movie-planner/issues/284)) ([bac1498](https://github.com/alrayyes/movie-planner/commit/bac14986909cd2dd1eabfd672ac7eec762c6ad76))

## [1.23.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.23.0...movie-planner-v1.23.1) (2026-09-07)


### Bug Fixes

* **sync:** make push_new crash-safe against calendar-create/local-save interruption ([#246](https://github.com/alrayyes/movie-planner/issues/246)) ([#280](https://github.com/alrayyes/movie-planner/issues/280)) ([1ab7fe5](https://github.com/alrayyes/movie-planner/commit/1ab7fe54995670bf8d9fbcce099de005d53a6469))

## [1.23.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.22.0...movie-planner-v1.23.0) (2026-09-07)


### Features

* **store:** add a local activity log of the CLI's own actions ([#276](https://github.com/alrayyes/movie-planner/issues/276)) ([#278](https://github.com/alrayyes/movie-planner/issues/278)) ([6137dba](https://github.com/alrayyes/movie-planner/commit/6137dba05a7f0afb32d742826ec26b1e89b2dcbe))

## [1.22.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.21.0...movie-planner-v1.22.0) (2026-09-07)


### Features

* **cli:** add a global --verbose flag for debugging ([#275](https://github.com/alrayyes/movie-planner/issues/275)) ([47231ea](https://github.com/alrayyes/movie-planner/commit/47231ea4d63f0850284d4c11a1b02b5b6a8c0904))

## [1.21.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.20.0...movie-planner-v1.21.0) (2026-09-07)


### Features

* **calendar:** stamp X-IMPORTER and X-IMPORTER-VERSION for debugging ([#257](https://github.com/alrayyes/movie-planner/issues/257)) ([#272](https://github.com/alrayyes/movie-planner/issues/272)) ([9250fab](https://github.com/alrayyes/movie-planner/commit/9250fabd3177e3c7423ef4fe82d33bff70f77fda))

## [1.20.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.19.0...movie-planner-v1.20.0) (2026-09-07)


### Features

* **omdb:** track and list entries with no OMDb match ([#255](https://github.com/alrayyes/movie-planner/issues/255)) ([#271](https://github.com/alrayyes/movie-planner/issues/271)) ([c642a61](https://github.com/alrayyes/movie-planner/commit/c642a61c23b46d89e036d7db64a8f9fe6d187ee4))

## [1.19.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.18.0...movie-planner-v1.19.0) (2026-09-07)


### Features

* **cli:** add update --refresh-metadata for one entry by ID ([#260](https://github.com/alrayyes/movie-planner/issues/260)) ([#268](https://github.com/alrayyes/movie-planner/issues/268)) ([b88d14d](https://github.com/alrayyes/movie-planner/commit/b88d14d544be290968294a2b6a8413ec92a139ca))

## [1.18.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.17.1...movie-planner-v1.18.0) (2026-09-07)


### Features

* **cli:** add list --limit for the N most recent entries ([#259](https://github.com/alrayyes/movie-planner/issues/259)) ([#267](https://github.com/alrayyes/movie-planner/issues/267)) ([4c55830](https://github.com/alrayyes/movie-planner/commit/4c558303550337b8a5d7231e861ef478fb50a2fa))

## [1.17.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.17.0...movie-planner-v1.17.1) (2026-09-07)


### Bug Fixes

* **sync:** stale-UID recovery no longer drops X-CITY/X-COUNTRY ([#262](https://github.com/alrayyes/movie-planner/issues/262)) ([#264](https://github.com/alrayyes/movie-planner/issues/264)) ([0313fc1](https://github.com/alrayyes/movie-planner/commit/0313fc1475ef10dee76d932e20f5a1071413c424))

## [1.17.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.16.0...movie-planner-v1.17.0) (2026-09-07)


### Features

* **import:** a real extension point for bulk-import formats ([#261](https://github.com/alrayyes/movie-planner/issues/261)) ([78b41ba](https://github.com/alrayyes/movie-planner/commit/78b41bae768d11340824ded8d8720ffa76948c9a))
* **import:** record and list import failures ([#254](https://github.com/alrayyes/movie-planner/issues/254)) ([#263](https://github.com/alrayyes/movie-planner/issues/263)) ([770e62a](https://github.com/alrayyes/movie-planner/commit/770e62a7ef797734f8c0e29160a65b29f525fd8b))


### Bug Fixes

* **deps:** bump the python-dependencies group with 5 updates ([#250](https://github.com/alrayyes/movie-planner/issues/250)) ([0b1e10e](https://github.com/alrayyes/movie-planner/commit/0b1e10e7551e64e2c37c0e508b80a088506c732a))

## [1.16.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.15.0...movie-planner-v1.16.0) (2026-09-06)


### Features

* **sync:** add sync pull - approval-gated calendar-to-store reconciliation ([#243](https://github.com/alrayyes/movie-planner/issues/243)) ([8bdd241](https://github.com/alrayyes/movie-planner/commit/8bdd24145ec6cfaafd9a27553371239e71e179f1))

## [1.15.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.14.0...movie-planner-v1.15.0) (2026-09-06)


### Features

* **trailer:** look up an entry's official trailer via TMDb ([#241](https://github.com/alrayyes/movie-planner/issues/241)) ([8700171](https://github.com/alrayyes/movie-planner/commit/8700171df1f857e3b48edc6296e9b5e903e7afcf))

## [1.14.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.13.3...movie-planner-v1.14.0) (2026-09-06)


### Features

* **omdb:** capture the rest of OMDb's response fields ([#237](https://github.com/alrayyes/movie-planner/issues/237)) ([#239](https://github.com/alrayyes/movie-planner/issues/239)) ([4b69ac2](https://github.com/alrayyes/movie-planner/commit/4b69ac2197fccf2a3ead0adc2f68a66d21cf9656))


### Documentation

* **openspec:** design capture for calendar sync pull ([#235](https://github.com/alrayyes/movie-planner/issues/235)) ([#238](https://github.com/alrayyes/movie-planner/issues/238)) ([ed67031](https://github.com/alrayyes/movie-planner/commit/ed67031d6677d612a675e8fe6b7efd598d047dce))

## [1.13.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.13.2...movie-planner-v1.13.3) (2026-09-06)


### Bug Fixes

* **venues:** alias the pre-[#227](https://github.com/alrayyes/movie-planner/issues/227) ", Amsterdam" cinema strings too ([#233](https://github.com/alrayyes/movie-planner/issues/233)) ([9a4cde0](https://github.com/alrayyes/movie-planner/commit/9a4cde0b54f8c9cf9b7d770b90a8360af51a7179))

## [1.13.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.13.1...movie-planner-v1.13.2) (2026-09-06)


### Bug Fixes

* **pathe,venues:** stop baking city into cinema, add 4 missing aliases ([#227](https://github.com/alrayyes/movie-planner/issues/227)) ([#231](https://github.com/alrayyes/movie-planner/issues/231)) ([4d76e72](https://github.com/alrayyes/movie-planner/commit/4d76e72f2fb49caeafbac59ed15cfdcd76575431))

## [1.13.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.13.0...movie-planner-v1.13.1) (2026-09-06)


### Bug Fixes

* **omdb:** strip the Dutch "(Originele versie)" suffix too ([#224](https://github.com/alrayyes/movie-planner/issues/224)) ([#225](https://github.com/alrayyes/movie-planner/issues/225)) ([f9f1123](https://github.com/alrayyes/movie-planner/commit/f9f1123167b9ac52786c55e8fd245ec02ee84d54))

## [1.13.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.12.0...movie-planner-v1.13.0) (2026-09-06)


### Features

* **pathe,calendar:** expose row/seat as X-ROW/X-SEAT ([#218](https://github.com/alrayyes/movie-planner/issues/218)) ([#228](https://github.com/alrayyes/movie-planner/issues/228)) ([352a79f](https://github.com/alrayyes/movie-planner/commit/352a79fe47daf342ca0aa449fa37c9e51d30f6e1))

## [1.12.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.11.1...movie-planner-v1.12.0) (2026-09-06)


### Features

* **calendar:** expose venue city/country as X-CITY/X-COUNTRY ([#217](https://github.com/alrayyes/movie-planner/issues/217)) ([#222](https://github.com/alrayyes/movie-planner/issues/222)) ([961644a](https://github.com/alrayyes/movie-planner/commit/961644aba0dbdc22588e579b58ede7fe7f582940))

## [1.11.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.11.0...movie-planner-v1.11.1) (2026-09-06)


### Bug Fixes

* **omdb:** strip Pathé format/edition suffixes before title search ([#216](https://github.com/alrayyes/movie-planner/issues/216)) ([#221](https://github.com/alrayyes/movie-planner/issues/221)) ([bc3a1e5](https://github.com/alrayyes/movie-planner/commit/bc3a1e56ea0c3d58e4589c08bd53da7582be0fc2))

## [1.11.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.10.1...movie-planner-v1.11.0) (2026-09-06)


### Features

* **venues:** collapse screen/format-suffixed venue aliases ([#196](https://github.com/alrayyes/movie-planner/issues/196)) ([#219](https://github.com/alrayyes/movie-planner/issues/219)) ([fcbf168](https://github.com/alrayyes/movie-planner/commit/fcbf168969038cf556ad29cca5622b43418acc1f))

## [1.10.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.10.0...movie-planner-v1.10.1) (2026-09-06)


### Bug Fixes

* **ci:** make the test job actually fail when pytest fails ([#212](https://github.com/alrayyes/movie-planner/issues/212)) ([#213](https://github.com/alrayyes/movie-planner/issues/213)) ([ab23a5b](https://github.com/alrayyes/movie-planner/commit/ab23a5b743d57d91900f1b1bbe190508b02ace07))

## [1.10.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.6...movie-planner-v1.10.0) (2026-09-06)


### Features

* **mail-import:** add a MaildirMailClient ([#211](https://github.com/alrayyes/movie-planner/issues/211)) ([ef8627b](https://github.com/alrayyes/movie-planner/commit/ef8627bd07e9950487a519a53b5cd502521cbe82))

## [1.9.6](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.5...movie-planner-v1.9.6) (2026-09-06)


### Bug Fixes

* **pathe:** parse the three remaining 2013-2019 Dutch templates ([#200](https://github.com/alrayyes/movie-planner/issues/200)) ([#209](https://github.com/alrayyes/movie-planner/issues/209)) ([ce6dc2e](https://github.com/alrayyes/movie-planner/commit/ce6dc2e90a8c1f58345e815f64d5279285049455))

## [1.9.5](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.4...movie-planner-v1.9.5) (2026-09-06)


### Bug Fixes

* **cli,mail-import:** richer --help text, and a man-page generation bug ([#205](https://github.com/alrayyes/movie-planner/issues/205)) ([2173fae](https://github.com/alrayyes/movie-planner/commit/2173faec152658eac44c6689125219dec31291f1))

## [1.9.4](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.3...movie-planner-v1.9.4) (2026-09-06)


### Bug Fixes

* **mail-import:** a URL's own digits no longer defeat placeholder detection ([#202](https://github.com/alrayyes/movie-planner/issues/202)) ([9ed2522](https://github.com/alrayyes/movie-planner/commit/9ed25225fd55f4276334c656519b73a5a75c4f4c))

## [1.9.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.2...movie-planner-v1.9.3) (2026-09-06)


### Documentation

* **contributing:** require OMDb-minimization as an explicit AC ([#198](https://github.com/alrayyes/movie-planner/issues/198)) ([3a674cf](https://github.com/alrayyes/movie-planner/commit/3a674cf60359b94b50a9439545d1f9e0145911c0))

## [1.9.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.1...movie-planner-v1.9.2) (2026-09-06)


### Documentation

* **architecture:** refresh diagram and note current known gaps ([#197](https://github.com/alrayyes/movie-planner/issues/197)) ([075eb66](https://github.com/alrayyes/movie-planner/commit/075eb667c707c2da41df894aace738fb7c235309))

## [1.9.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.9.0...movie-planner-v1.9.1) (2026-09-06)


### Bug Fixes

* **pathe:** never treat an attachment-disposed part as the body ([#194](https://github.com/alrayyes/movie-planner/issues/194)) ([fcb9002](https://github.com/alrayyes/movie-planner/commit/fcb9002d57506a13b9e9d779a655406a4f997c5e)), closes [#193](https://github.com/alrayyes/movie-planner/issues/193)

## [1.9.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.8.1...movie-planner-v1.9.0) (2026-09-06)


### Features

* **mail-import:** scan an additional mbox folder alongside INBOX ([#189](https://github.com/alrayyes/movie-planner/issues/189)) ([e699766](https://github.com/alrayyes/movie-planner/commit/e6997667aa783a40d92e98f02155f9e52f9cdc2e)), closes [#188](https://github.com/alrayyes/movie-planner/issues/188)


### Bug Fixes

* **mail-import:** never treat an attachment-disposed part as the body ([#192](https://github.com/alrayyes/movie-planner/issues/192)) ([5334495](https://github.com/alrayyes/movie-planner/commit/5334495d2482764971f243644b7703b0fb83bf1c)), closes [#191](https://github.com/alrayyes/movie-planner/issues/191)

## [1.8.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.8.0...movie-planner-v1.8.1) (2026-09-06)


### Bug Fixes

* **store:** backfill venue coordinates independently of chain/city/country ([#186](https://github.com/alrayyes/movie-planner/issues/186)) ([d740f98](https://github.com/alrayyes/movie-planner/commit/d740f98e1aee5239610d9790340f9529372cb8f2)), closes [#185](https://github.com/alrayyes/movie-planner/issues/185)

## [1.8.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.7.0...movie-planner-v1.8.0) (2026-09-06)


### Features

* **calendar:** surface venue GPS coordinates as VEVENT GEO ([#183](https://github.com/alrayyes/movie-planner/issues/183)) ([7c1efdc](https://github.com/alrayyes/movie-planner/commit/7c1efdcc35df21d593b260f8c8d9ccb71a3ef9e7)), closes [#170](https://github.com/alrayyes/movie-planner/issues/170)

## [1.7.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.6.0...movie-planner-v1.7.0) (2026-09-06)


### Features

* **cli:** prompt interactively for CalDAV/OMDb settings on init ([#180](https://github.com/alrayyes/movie-planner/issues/180)) ([d31553b](https://github.com/alrayyes/movie-planner/commit/d31553b28bb34467dc12ea48f1d795e50be0faa8))

## [1.6.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.5...movie-planner-v1.6.0) (2026-09-06)


### Features

* **config:** let movie-planner and pathe-mail-import share one file ([#176](https://github.com/alrayyes/movie-planner/issues/176)) ([7d1e07d](https://github.com/alrayyes/movie-planner/commit/7d1e07db6d9af9fe3367982bce4d7fb500269c23))

## [1.5.5](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.4...movie-planner-v1.5.5) (2026-09-06)


### Bug Fixes

* **pathe:** from-pathe-email handles a real HTML-only confirmation ([#178](https://github.com/alrayyes/movie-planner/issues/178)) ([b1c4803](https://github.com/alrayyes/movie-planner/commit/b1c4803845aa48be59f68df9b3e34761298ceba9)), closes [#162](https://github.com/alrayyes/movie-planner/issues/162)

## [1.5.4](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.3...movie-planner-v1.5.4) (2026-09-06)


### Bug Fixes

* **mail-import:** parse a third real Pathé template ([#174](https://github.com/alrayyes/movie-planner/issues/174)) ([7a19b22](https://github.com/alrayyes/movie-planner/commit/7a19b225b98b007b58c81051b68250e668057346)), closes [#171](https://github.com/alrayyes/movie-planner/issues/171)

## [1.5.3](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.2...movie-planner-v1.5.3) (2026-09-06)


### Bug Fixes

* **sync:** recover when an entry's caldav_uid is stale ([#172](https://github.com/alrayyes/movie-planner/issues/172)) ([3ecbe01](https://github.com/alrayyes/movie-planner/commit/3ecbe0149ca20fcfb9c7013cbcc1893bef41b23d)), closes [#166](https://github.com/alrayyes/movie-planner/issues/166)

## [1.5.2](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.1...movie-planner-v1.5.2) (2026-09-05)


### Bug Fixes

* **mail-import:** parse real, HTML-only Pathé confirmations ([#163](https://github.com/alrayyes/movie-planner/issues/163)) ([6d7b45f](https://github.com/alrayyes/movie-planner/commit/6d7b45f895e86956458a399107bd40797b57d12d))

## [1.5.1](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.5.0...movie-planner-v1.5.1) (2026-09-05)


### Bug Fixes

* **mail-import:** wire --since/--until into fetch ([#161](https://github.com/alrayyes/movie-planner/issues/161)) ([07bbd55](https://github.com/alrayyes/movie-planner/commit/07bbd551a68d9ecfe1b3fc59dfa287135b3d519c))

## [1.5.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.4.0...movie-planner-v1.5.0) (2026-09-05)


### Features

* **docker:** buildable pathe-mail-import image, usage docs, man pages ([#155](https://github.com/alrayyes/movie-planner/issues/155)) ([ba3fcdf](https://github.com/alrayyes/movie-planner/commit/ba3fcdf14ef5ec479a496ea0a16e6fd04396726f))

## [1.4.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.3.0...movie-planner-v1.4.0) (2026-09-05)


### Features

* **mail-import:** piped composition mode, import stdin support ([#153](https://github.com/alrayyes/movie-planner/issues/153)) ([d6a7390](https://github.com/alrayyes/movie-planner/commit/d6a739018239b3bef128618ec849a5975de3ffcd)), closes [#140](https://github.com/alrayyes/movie-planner/issues/140)

## [1.3.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.2.0...movie-planner-v1.3.0) (2026-09-05)


### Features

* **mail-import:** chain dispatch, Pathé translation script, fetch ([#151](https://github.com/alrayyes/movie-planner/issues/151)) ([3cb2c32](https://github.com/alrayyes/movie-planner/commit/3cb2c32672d25c42df1764eb3891a2d17c1818f1))

## [1.2.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.1.0...movie-planner-v1.2.0) (2026-09-05)


### Features

* **mail-import:** scaffold pathe-mail-import, IMAP/mbox adapters ([#149](https://github.com/alrayyes/movie-planner/issues/149)) ([b642e30](https://github.com/alrayyes/movie-planner/commit/b642e309242f5ad5c3e0ef2f91832cadb1ab7ec3))

## [1.1.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v1.0.0...movie-planner-v1.1.0) (2026-09-05)


### Features

* **duplicates:** flag overlapping screening times ([#147](https://github.com/alrayyes/movie-planner/issues/147)) ([fe14b22](https://github.com/alrayyes/movie-planner/commit/fe14b22041fb246d2257ce0b790a6baa8e38b1ea)), closes [#142](https://github.com/alrayyes/movie-planner/issues/142)

## [1.0.0](https://github.com/alrayyes/movie-planner/compare/movie-planner-v0.21.3...movie-planner-v1.0.0) (2026-09-05)


### ⚠ BREAKING CHANGES

* **import:** a CSV/JSON row supplying booking_ref no longer has it stored. from-pathe-email is unaffected - it never went through this code path.

### Features

* **import:** drop booking_ref, add an opaque source field ([#143](https://github.com/alrayyes/movie-planner/issues/143)) ([27f3cde](https://github.com/alrayyes/movie-planner/commit/27f3cdea8b4018375bae0310677fbc20475fe49c))

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
