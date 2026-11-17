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

## Public homepage update

The supplied MyStudyLife and Shovel screenshots were used for product-story structure, not copied branding or unsupported feature claims. The existing chosen forest/ivory theme remains the visual system.

Opened and visually reviewed the new full-page desktop (1440px) and mobile (390px) captures in `docs/design/landing-desktop.png` and `docs/design/landing-mobile.png`. Confirmed: horizontal public navigation, prominent Korean hero copy, actual product image, three core features, calendar explanation, three-step guide, static AI example, keyboard-accessible FAQ and final login CTA. Public login/catalog pages use the same header. Private pages retain their sidebar and existing working forms.

Automated verification: 36 viewport/page combinations at 1440/390/320px; no axe WCAG-rule violations, missing images, page overflow or browser errors. Functional smoke flow passed, including public section links, FAQ keyboard activation, private mobile navigation, CRUD, checklist, uploads, notes, search, missing-key handling and logout.

No outstanding P0/P1/P2 findings for this update.

## Feature tour update

Reviewed the user-provided original feature grid and fresh public captures of Shovel and MyStudyLife. Replaced the 21-card catalog with four outcome-oriented scenes, real sample-data product images, working section links and honest AI explanation. No unsupported external-service functionality is presented as implemented.

Visually reviewed the corrected desktop and mobile captures at `docs/design/features-desktop.png` and `docs/design/features-mobile.png`. Fixed the initially oversized context icon by limiting product-image styles to direct children. All four mobile chapter links are visible. Additional browser checks confirmed chapter navigation and login CTA. The existing 62 tests and 36 browser viewport/page checks passed. No remaining P0/P1/P2 issues.

Research findings and evidence limits: `docs/design/FEATURE_TOUR.md`.

## Separate overview and management update

The user's supplied existing dashboard screenshot anchored the retained visual theme. The requested information separation is implemented as a focused overview and a dedicated assignment list. Visually inspected desktop overview/management and mobile management captures; confirmed consistent headings, one primary action, aligned rows, no duplicate dashboard widgets on the list and bounded overview content. Current captures are stored in `docs/design/dashboard-*.png` and `docs/design/assignments-*.png`.

78 tests and 39 browser page/viewport checks passed; no axe violations, page overflow or browser errors. Owner isolation, legacy query redirects, selected navigation and create/delete return paths were tested. See `docs/design/WORKSPACE_SPLIT.md`. No remaining P0/P1/P2 issues.

## Six productivity features

Visually reviewed updated desktop/mobile assignment management, course overview and mobile backup captures. Retained the forest/ivory system, added archive tabs within management, kept course/backup workflows on dedicated pages and used existing checklist controls for daily focus. Row status forms have contextual accessible names. The AI result distinguishes measured pass/mismatch from manual review, and supports a real, non-generative recheck after edits.

98 Python tests passed, 48 browser page/viewport checks passed with no axe findings, overflow, missing images or browser errors. Browser flows verified daily focus, completion, quick status, archive/reopen, course filtering, ZIP download and additive restore. AI analysis was mocked for UI result testing; the recheck endpoint was exercised normally, including edited requirements. Live Gemini quality is not claimed.

`docs/design/assignments-*.png`, `courses-desktop.png`, `backup-mobile.png` and `ai-request-check-*.png` capture isolated sample data. No P0/P1/P2 issues remain.

final result: passed
