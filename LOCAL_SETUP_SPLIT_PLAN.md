# local_setup.sh Refactor Plan

## Goal
Break `scripts/local_setup.sh` into smaller units with clear ownership so local bootstrap, deployment bootstrap, and assessment runtime provisioning can evolve independently.

## Target Layout
- `scripts/lib/common.sh`
  Shared logging, root escalation, env helpers, templating helpers, checksum helpers.
- `scripts/lib/platform.sh`
  Ubuntu detection, package-manager guards, apt install wrappers.
- `scripts/lib/python_env.sh`
  Python runtime checks, venv creation, dependency install, Django manage.py helpers.
- `scripts/lib/postgres.sh`
  PostgreSQL install, readiness checks, database/user provisioning.
- `scripts/lib/nginx.sh`
  NGINX install, config rendering, site symlink management, reload/validate flow.
- `scripts/lib/systemd.sh`
  Unit rendering, credential wiring, enable/start/restart helpers.
- `scripts/lib/assessment.sh`
  PowerShell install, module download/verification, PFX password management, assessment filesystem layout.
- `scripts/local_setup.sh`
  Thin orchestration entrypoint for the supported Ubuntu bootstrap path.
- `scripts/local_dev.sh`
  Optional dev-focused entrypoint that stops before root-owned deployment steps.
- `scripts/render_config.sh`
  Optional idempotent helper for rendering env, nginx, and systemd artifacts without executing installs.

## Extraction Order
1. Extract pure helper functions first.
   Start with logging, truthy parsing, random secret generation, checksum helpers, and prompt-free utility functions.
2. Extract platform and package-install logic.
   Move Ubuntu detection and package installation wrappers into `platform.sh` so higher-level scripts stop knowing apt details.
3. Extract assessment-specific provisioning.
   Move PowerShell, PowerShell Gallery module verification, credential-file creation, and assessment directory setup into `assessment.sh`.
4. Extract deployment integration layers.
   Move nginx rendering and systemd unit rendering/enabling into dedicated libraries.
5. Reduce `local_setup.sh` to orchestration only.
   Keep argument parsing, ordered phase execution, and top-level success/failure messaging in the entrypoint.

## Contract Changes
- Each library should expose a small set of public functions prefixed by domain, for example `platform::ensure_python`, `nginx::install`, `assessment::install_modules`.
- Shared mutable globals should be replaced with explicit function inputs where practical. When globals remain necessary, define them once in `local_setup.sh` and treat library functions as read-only consumers.
- Rendering functions should write to a caller-provided target path and avoid hidden side effects outside that path.

## Verification
- Add `shellcheck` coverage for every new script.
- Add a lightweight smoke test script that sources the libraries and validates function loading.
- Validate the split with two execution paths:
  - non-root dry run for helper/render functions
  - root-backed Ubuntu bootstrap run in a disposable VM
