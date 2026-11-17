# Campus UI validation

The selected visual is the **second displayed image**, the forest green / ivory sidebar dashboard (generated source `exec-0fd20c52-8fed-4696-baa1-44960829dcbc.png`). This is an integration into the existing Flask application, not a frontend-only replacement.

## Run

```bash
cd /workspace/3rd-
.venv/bin/python -m flask --app app run --host 0.0.0.0 --port 5000 --no-debugger --no-reload
```

Existing sessions, local-only signup, CSRF, owner-scoped access, database schema, assignment routes, Gemini calls and file storage policies remain in place. The only server-side additions are read-only checklist summaries and date/calendar presentation data. No migration is required.

## Repeat validation

Existing regression suite:

```bash
GEMINI_API_KEY='' FLASK_SECRET_KEY=ci-only-not-for-production .venv/bin/python -m unittest discover -s tests -v
```

Browser smoke suite uses a **separate temporary SQLite database** and disposable account. Never point it at the regular application or personal data. It runs on port 5001, not the normal application port 5000. Start the fixture in one terminal:

```bash
.venv/bin/python tests/ui_server.py
```

In another terminal, install browser testing tools outside the checkout and run:

```bash
npm install --prefix /tmp/campus-ui-tools --cache /tmp/campus-npm-cache --no-audit --no-fund playwright axe-core
NODE_PATH="/tmp/campus-ui-tools/node_modules:${NODE_PATH:-}" node tests/ui_smoke.cjs
```

A system Chromium is required at `/usr/bin/chromium`; set `CHROMIUM_PATH` if needed. Tools are test-only and are not application dependencies. Stop the fixture server after testing; its test records and uploads are temporary.

The browser suite checks:

- Public landing, all-feature catalog, fixed AI demo, login and registration views.
- Signed-in dashboard, calendar, AI input, assignment form/detail, empty search, and deadline conflicts.
- 1440, 390 and 320px layouts: page overflow, missing images, browser errors, axe WCAG 2 A/AA and WCAG 2.1 AA rule violations.
- Mobile menu, Escape, actual form submission, create/edit/delete, checklist completion, upload, notes, search, logout and private-page redirects.
- Real missing-key error handling for Gemini. Successful AI responses and review/save behavior remain covered by the existing mocked unit tests; no live Gemini success is claimed.

Reports and screenshots are written to `/tmp/campus-checks/`. Automated accessibility checks supplement visual and keyboard review; they do not certify full WCAG compliance.

## Product details

- Public examples stay explicitly labeled and never load private assignments.
- No LMS sync, drag-and-drop scheduling, cross-device sync, email accounts, or background push features were added or advertised.
- Date selection remains the existing monthly deadline calendar; the dashboard mini-calendar highlights today and actual pending deadlines and links to that calendar.
- Today’s checklist items link to the existing assignment checklist, where completion is persisted.
- Full search/filter controls use an accessible native disclosure; active filters keep it expanded.
- Long calendar grids scroll within their own container on narrow screens. Status text accompanies colors.
- Fonts use the local Korean sans-serif stack. Bootstrap Icons 1.13.2 are vendored with their MIT license; there are no external runtime icon/font requests. The sprout is a generated decorative raster asset.
- Shovel and MyStudyLife public UX were directly reviewed. Semestree’s live site displayed a closure notice, so past product behavior was not inferred.

## Verified outcome (2026-11-17)

- Python compilation and all 62 existing tests passed.
- All browser functional flows passed against the disposable server.
- 36 viewport/page checks completed with zero axe violations, page-overflow findings or browser errors after fixes.
- See `browser-results.json` and the repository-root `design-qa.md` for evidence and scope.
