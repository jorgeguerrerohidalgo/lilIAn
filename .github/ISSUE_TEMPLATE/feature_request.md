---
name: Feature Request
about: Suggest a new feature or improvement
title: "[Feature]: "
labels: enhancement, needs-triage
assignees: ""
---

## Problem Statement

A clear and concise description of the problem this feature would solve.
What user need or business outcome are we addressing? Quote any user
feedback or metrics that motivate the request.

> Example: "Legal analysts need to compare two case files side-by-side
> without losing their scroll position on either document."

## Proposed Solution

A clear and concise description of what you want to happen. Describe the
user-facing behavior, not the implementation details. Include the affected
modules / routes / components if known.

## Alternatives Considered

What other approaches did you consider, and why is the proposed solution
better?

## Mockups / Wireframes

If the change is user-facing, add mockups, wireframes, or annotated
screenshots. Drag-and-drop images directly into the editor, or paste a
Figma / Excalidraw link.

## Acceptance Criteria

A bullet list of testable conditions that define "done". Use the
Given / When / Then format where it helps.

- [ ] Given `<precondition>`, when `<action>`, then `<expected outcome>`.
- [ ] ...
- [ ] Documentation under `docs/` is updated.
- [ ] Test coverage meets the 80% project floor.
- [ ] Accessibility considerations addressed (keyboard, screen reader,
  color contrast).

## Out of Scope

What is explicitly NOT included in this request? Listing these now
prevents scope creep later.

## Dependencies / Risks

- Affected modules: [e.g. `apps/backend/app/api/v1/cases.py`]
- Database / migration impact: [yes / no — describe]
- External integrations: [e.g. S3, OpenAI, Postgres]
- Known risks: [e.g. breaking change for `v2` API consumers]

## Priority

- [ ] Critical (blocks a release)
- [ ] High (next sprint)
- [ ] Medium (backlog)
- [ ] Low (nice to have)

## Additional Context

Add any other context, links to related issues, RFCs, or customer
feedback here.

## Checklist

- [ ] I have searched the existing issues and confirmed this is not a
  duplicate.
- [ ] I have discussed the approach with the maintainers (or linked a
  prior conversation).
