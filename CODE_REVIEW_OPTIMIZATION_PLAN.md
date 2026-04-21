This file is retained only as a historical placeholder.

The previous optimization review referenced the old `ISO27001` workspace path, a deleted `portal/services.py` layout, and findings that are no longer accurate for the current repository state.

Use these files as the current sources of truth instead:

- `SPECIFICATION.md` for the current architecture and ownership map
- `DEPLOYMENT.md` for runtime and hosting guidance
- `LOCAL_SETUP_SPLIT_PLAN.md` for the planned breakup of `scripts/local_setup.sh`

Current structural cleanup that replaced the old review assumptions:

- service code is split across `portal/services/`
- shared view decorators and page render helpers live in `portal/view_helpers.py`
- DTO serialization is centralized in `portal/contracts.py`
- upload parsing and sanitization now live in focused service modules
- Django tests live under `portal/tests/`
