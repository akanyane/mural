# Changelog

## [0.5.0](https://github.com/akanyane/mural/compare/v0.4.0...v0.5.0) (2026-11-15)


### ⚠ BREAKING CHANGES

* **api:** access tokens are opaque session tokens instead of JWTs; tokens issued before this release stop working, so everyone has to log in again. Public user payloads no longer contain "email".
* **schemas:** post/comment "owner" and profile "user" no longer include "email".

### Features

* **api:** server-side sessions and a separate profiles table ([bda9405](https://github.com/akanyane/mural/commit/bda94050e2187370986ec422abfd2d06b7636195))
* **schemas:** public profiles, profile edits and session models ([e7e17bc](https://github.com/akanyane/mural/commit/e7e17bcf813775266705d486a9076b59a73eb2fd))
* server-side sessions, profiles table and profile editing ([363681b](https://github.com/akanyane/mural/commit/363681be02e515f2bc00155bb4ab1644c93a0752))
* **web:** persistent login, active sessions page and profile editing ([2db811b](https://github.com/akanyane/mural/commit/2db811bb48198ac45b220efb4ec336b79d4e4152))

## [0.4.0](https://github.com/akanyane/mural/compare/v0.3.0...v0.4.0) (2026-11-15)


### Features

* **api:** follow and unfollow users ([4fe911f](https://github.com/akanyane/mural/commit/4fe911fb0a4147b9c12577a90ca252d46c89d39a))
* follow users and a following feed ([41e49fb](https://github.com/akanyane/mural/commit/41e49fbd6e6c92e71664022f53ffb571f5498bdb))
* **schemas:** add follower counts and a public user model ([614765c](https://github.com/akanyane/mural/commit/614765c2339423fb1df373a359faa1a3f1f92f43))
* **web:** follow button, follower lists and a following feed ([ec408f3](https://github.com/akanyane/mural/commit/ec408f33b525f383740f280218bb73574ee64272))

## [0.3.0](https://github.com/akanyane/mural/releases/tag/v0.3.0) (2026-11-15)

First release of Mural as a monorepo. The whole repository (API, web app and shared schemas)
shares a single version and a single tag (`vX.Y.Z`).

### ⚠ BREAKING CHANGES

* **api:** POST /users/ now requires a "username" field.
* **api:** the database is now SQLite by default (any SQLAlchemy URL via DATABASE_URL) and the old PostgreSQL-only migrations were replaced by a new initial migration. PUT /posts/{id} returns the post instead of {"data": ...}, /posts lists newest first and tokens use the standard "sub" claim, so existing sessions must log in again.

### Features

* **api:** comments, profiles, SQLite and a full test suite ([b678f0f](https://github.com/akanyane/mural/commit/b678f0fa37d98c5a4ed60cd11cf6ccc3aecff51a))
* **api:** unique usernames, login by username and profiles by username ([466bb95](https://github.com/akanyane/mural/commit/466bb9503499f130df444a4040f11a80e0143a48))
* **web:** add Mural, a server-rendered HTMX frontend ([1aa8d74](https://github.com/akanyane/mural/commit/1aa8d74c8b3004e9641095069caf8a31504efaa7))
* **web:** show usernames, live username check and login by username ([e8faa4d](https://github.com/akanyane/mural/commit/e8faa4dc308ed1e07ac49e1054d2d1bb6ad32c2f))
* **schemas:** add shared posts-schemas package ([153afbb](https://github.com/akanyane/mural/commit/153afbb15e0d2b87a1d1ecf37338099209b6da8d))
* **schemas:** add Instagram-style username rules ([4f27a74](https://github.com/akanyane/mural/commit/4f27a74798f30785ad11de5221708ac1e16e18c7))
