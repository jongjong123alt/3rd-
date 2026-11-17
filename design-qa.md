# Design QA — 과제 노트

Visual target: second displayed generated concept, forest green / ivory campus dashboard (`/workspace/generated_images/exec-0fd20c52-8fed-4696-baa1-44960829dcbc.png`).

Reference and implementation were opened and visually compared at the same **1487 × 1058** desktop viewport. Implementation: [desktop dashboard](docs/design/dashboard-desktop.png). Responsive visual review: [390px dashboard](docs/design/dashboard-mobile.png), [390px landing](docs/design/landing-mobile.png). Screenshots use an isolated test account and sample assignments, not personal user records.

## Comparison

- Forest primary actions, ivory sidebar, soft sage selected navigation, generous white main surface, strong Korean heading, sprout illustration, lightweight assignment rows, right calendar and deadline column match the selected direction.
- Full-page application behavior is retained: summary statistics, search/filter disclosure, row checklist progress, today’s work, notification opt-in and analytics remain usable.
- Landing, catalog, static AI demo, login, assignment forms/detail, checklist, AI input/review and calendar share the same tokens, typography, controls and spacing.
- The concept’s invented name/email are replaced by an honest workspace label. Counts, deadlines and progress use owner-scoped records. The calendar uses correct full-month dates. Today’s work is empty when no items are scheduled; no example tasks are inserted into private screens.
- Checklist completion remains in assignment detail through existing POST/CSRF routes. The dashboard links to it. Existing notification behavior remains explicitly described; there is no background push claim.

## Fixes and verification

- Fixed attachment input accessible name and added names for editable study-plan inputs.
- Added visible calendar status text and ensured it retains readable contrast.
- Mobile navigation keeps text labels, moves focus into the menu and supports Escape. Skip link, focus rings, semantic form labels, selected navigation state, reduced-motion support and touch targets are included.
- 1440/390/320px browser coverage includes public and private surfaces, empty search and forms. Calendar overflow is confined to its scroll container.
- Existing 62 regression tests pass. Browser CRUD, checklist completion, upload, notes, search, missing-key error, logout and auth redirect flows pass.
- Automated axe checks cover WCAG 2 A/AA and WCAG 2.1 AA rule sets. Automated checks do not establish complete accessibility conformance.

Live Gemini response quality is not verified because an API key is absent. Existing mocked integration tests cover successful analysis/save; browser testing verifies the actual missing-key error.

No outstanding P0/P1/P2 visual or interaction findings. No deployment or environment publication performed.

final result: passed
