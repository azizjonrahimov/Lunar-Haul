## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. Route only to skills in the session's available-skills list; answer directly for quick questions or small scoped edits.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- QA/testing site behavior → invoke /qa
- Code review/diff check → invoke /review
- Ship/deploy/PR → invoke /ship

Do not suggest or auto-invoke other gstack skills: they run when the user types them, or when a running skill hands off to them (`gstack-config set proactive all` routes every skill).

## Testing

- Python: `.venv/Scripts/python -m pytest tests -q -p no:cacheprovider` (CI: `python -m pytest tests -q` after `pip install -e ".[full]"`).
- Site: `node --test site/tests/*.test.mjs` (after `cd site && npm run build`); page budgets: `.venv/Scripts/python tools/ci/budgets.py pages`.
- CI also runs `python -m lunarsim verify`, `python -m lunarsim validate data/scenarios/*.json data/sample_traces/*.json` and `python tools/ci/budgets.py schemas`.
