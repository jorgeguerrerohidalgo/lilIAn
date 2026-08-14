## Type of Change

Please check the option(s) that apply:

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing
  functionality to change)
- [ ] Documentation update (changes to docs only)
- [ ] Refactor (no functional change)
- [ ] Performance improvement
- [ ] Test addition / update
- [ ] CI / build / tooling change

## Related Issue

Link the GitHub issue this PR addresses. Use `Closes #NNN` or
`Refs #NNN` so the issue is closed automatically on merge when
appropriate.

Closes #
Refs #

If there is no tracking issue, explain why.

## Description

A concise summary of what changed and why. Reference the relevant
modules / files. Include design notes for non-trivial changes.

## How Has This Been Tested?

Describe the tests you ran to verify your change. Include command-line
invocations, fixtures used, and any edge cases covered.

- [ ] Unit tests added / updated
- [ ] Integration tests added / updated
- [ ] E2E / Playwright tests added / updated
- [ ] Manual verification (describe below)

```bash
# Example commands run locally
cd apps/backend && pytest -k <name>
cd apps/frontend && npm run lint && npm run build
```

## Screenshots / Recordings

If the change is user-facing, add before / after screenshots or a short
recording. Otherwise remove this section.

## Checklist

Confirm each item before requesting review:

- [ ] My code follows the project style guides (Python: ruff; TS:
  prettier + eslint).
- [ ] I have added tests that prove the fix / feature works.
- [ ] New and existing unit tests pass locally (`pytest`,
  `npm run lint`, `npm run build`).
- [ ] I have updated the documentation where relevant
  (`docs/`, `README.md`, `CHANGELOG.md`).
- [ ] I have added an entry to `CHANGELOG.md` under the next
  unreleased section.
- [ ] My change does not introduce new lint or type errors.
- [ ] I have considered backwards compatibility and listed any
  breaking changes in the description.
- [ ] I have removed debug statements (`console.log`, `print`,
  breakpoints, `pdb`).
- [ ] I have not committed secrets, tokens, or customer data.

## Reviewer Notes

Anything you want the reviewer to focus on, known limitations, or
follow-up work that should be tracked separately.
