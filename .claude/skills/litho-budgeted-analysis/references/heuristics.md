# Litho Budgeted Analysis Heuristics

## Repo classes

- `small`: <= 500 tracked source-like files and <= 50 MB source-like bytes
- `medium`: <= 2,000 tracked source-like files and <= 200 MB source-like bytes
- `large`: <= 8,000 tracked source-like files and <= 750 MB source-like bytes
- `very-large`: above either `large` threshold

Classify by the highest matching pressure, not the lowest.

## Source-like files

Treat these as source-like by default:

- code: `py`, `ts`, `tsx`, `js`, `jsx`, `rs`, `go`, `java`, `kt`, `kts`, `swift`, `c`, `cc`, `cpp`, `h`, `hpp`, `cs`, `rb`, `php`, `scala`, `sql`, `sh`
- config/spec: `json`, `yaml`, `yml`, `toml`, `ini`, `env`, `proto`, `graphql`
- docs with architectural value: `md`, `mdx`

## Cache freshness

Cache is `fresh` when:

- `.litho/cache` exists
- it contains files
- the newest cache file mtime is >= the latest git commit timestamp for the repo

If git metadata is unavailable, treat cache newer than 24 hours as `fresh-ish` and allow `--skip-preprocessing` only for `small` or `medium` repos.

## Direct-run defaults

### Small
- include tests: false
- max file size: 512 KB
- max depth: 10
- boundary insights: 15
- boundary code limit: 25
- include source code in boundary analysis: true
- max parallels: 3

### Medium
- include tests: false
- max file size: 384 KB
- max depth: 10
- boundary insights: 15
- boundary code limit: 25
- include source code in boundary analysis: false
- max parallels: 4

### Large
- include tests: false
- max file size: 256 KB
- max depth: 8
- boundary insights: 10
- boundary code limit: 20
- include source code in boundary analysis: false
- max parallels: 5

### Very-large
- direct mode only if estimate fits budget after pruning
- max file size: 128 KB
- max depth: 6
- boundary insights: 8
- boundary code limit: 15
- include source code in boundary analysis: false
- max parallels: 5

## Exclusions

Always exclude obvious heavy/generated directories:

- `.git`, `.hg`, `.svn`
- `node_modules`, `vendor/bundle`, `.venv`, `venv`, `__pycache__`
- `dist`, `build`, `target`, `.next`, `.turbo`, `.cache`, `coverage`
- `tmp`, `temp`, `.litho`, `litho.docs`

Be conservative with `vendor/` and `third_party/` in ecosystems where vendored source may matter.

## Filtered-copy mode

Enter filtered-copy mode when either is true:

- repo class is `very-large`
- estimated runtime exceeds budget by >= 25% after normal pruning

Filtered-copy keep rules:

1. Start from tracked files when git is available.
2. Keep source-like files.
3. Always keep important root files:
   - `README*`, `ARCHITECTURE*`, `UI*`, `AGENTS.md`, `CLAUDE.md`
   - `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`
   - `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`
   - `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`
   - `docker-compose*`, `Dockerfile*`, `.github/workflows/*`
4. Keep migrations, schemas, and infra/config directories.
5. Keep architecture/design/ADR docs when present.

Do not arbitrarily cap to the first N files. Filter by value, not by position.

## Cache-aware command selection

- no cache or stale cache:
  - full run
- fresh cache + medium/large repo:
  - add `--skip-preprocessing`
- fresh cache + focused rerun after docs already exist:
  - consider `--skip-preprocessing --skip-research`

Do not use `--no-cache` unless debugging cache behavior.
Do not use force regeneration unless the user asks or the run clearly failed because of stale cache.
