# Changelog

## [0.3.0](https://github.com/akanyane/mural/compare/posts-api-v0.2.0...posts-api-v0.3.0) (2026-11-15)


### ⚠ BREAKING CHANGES

* **api:** POST /users/ now requires a "username" field.
* **api:** the database is now SQLite by default (any SQLAlchemy URL via DATABASE_URL) and the old PostgreSQL-only migrations were replaced by a new initial migration. PUT /posts/{id} returns the post instead of {"data": ...}, /posts lists newest first and tokens use the standard "sub" claim, so existing sessions must log in again.

### Features

* **api:** comments, profiles, SQLite and a full test suite ([b678f0f](https://github.com/akanyane/mural/commit/b678f0fa37d98c5a4ed60cd11cf6ccc3aecff51a))
* **api:** unique usernames, login by username and profiles by username ([466bb95](https://github.com/akanyane/mural/commit/466bb9503499f130df444a4040f11a80e0143a48))
* Mural — uv monorepo, HTMX frontend, comments, profiles and release-please ([b02b3cb](https://github.com/akanyane/mural/commit/b02b3cb7879d9827d231bc012e43b1bc250a34c0))
