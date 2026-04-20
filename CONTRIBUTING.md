# Contributing

Thanks for contributing to `css-elasticity-aiops-agent`.

## What This Repository Accepts

This project is intended for practical improvements to Huawei Cloud CSS elasticity automation, especially in these areas:

- safer scaling policies
- better CSS or CES integrations
- clearer configuration and operational guidance
- diagnostics and verification improvements
- test coverage for decision, validation, and execution paths
- documentation improvements for operators and developers

## Before You Start

- Open an issue or draft PR if the change is large
- Keep changes focused and easy to review
- Do not include real Huawei Cloud credentials, cluster IDs, or customer data
- Do not commit `.env`, local SQLite files, or generated logs

## Development Setup

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install pytest
```

Run tests:

```bash
python -m pytest -q
```

## Pull Request Guidelines

- Use clear branch names and commit messages
- Keep PRs scoped to one logical change
- Include a short summary of what changed and why
- Mention any configuration or behavior changes explicitly
- Add or update tests when changing policy or execution logic

## Documentation Expectations

When behavior changes, update the relevant documentation:

- `README.md` for project-level usage
- `.env.example` for configuration changes
- inline comments or docstrings when behavior is not obvious

## Safety Rules

- Default to non-mutating examples unless mutation is the point of the change
- Preserve recommendation-only and approval-required workflows
- Treat production safety as more important than automation convenience

## Code Style

- Keep changes straightforward and readable
- Prefer small, composable functions over large workflows
- Follow the existing project layout and naming style

## License

By contributing to this repository, you agree that your contributions will be licensed under the MIT License in this repository.
