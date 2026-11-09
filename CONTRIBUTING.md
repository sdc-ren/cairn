# Contributing

Thanks for helping. cairn is small on purpose; please read this before opening a pull request.

## Workflow

1. Open an issue first for anything beyond a small fix, so we can agree on the behaviour.
2. Behaviour is specified in [`docs/specs/`](docs/specs/README.md): change the requirement
   (`requirements.md`) or design decision (`design.md`) in the same pull request as the code.
3. One pull request per task, ideally under 400 changed lines excluding tests.

## Code

Follow [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md). The short version:

- Python 3.9+, standard library only at runtime.
- One place for each concern: subprocesses in `proc.py`, git commands in `gitio.py`, output in
  `out.py`, Store paths in `store.py`, agent-facing text in `src/agent_cairn/assets/`.
- Agent-facing text (skills, templates, messages) is English.

## Tests

```bash
make setup
make lint test
```

- Write the test first. Tag tests that verify a requirement with `@pytest.mark.req("Rn.m")`.
- Use real temporary git repositories (fixtures in `tests/conftest.py`), never mocked git.
- Changes to skills or hooks: also run `claude plugin validate --strict .` and try the flow in
  a real Claude Code session.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat(store): ...`,
`fix(hook): ...`, `docs: ...`, `test: ...`.
