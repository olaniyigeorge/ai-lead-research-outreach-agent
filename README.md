# Koya Lead Agent

An AI-powered lead research and outreach agent. You give it a plain-language
qualification objective ("Find 10 US B2B SaaS companies with 10 to 100
employees"), it turns that into a structured, human-reviewable target
profile (ICP), and — once fully built out — researches, qualifies, and
drafts outreach for real candidate companies against it. Every step is
persisted and auditable; nothing is sent automatically.

**Live app:** https://ai-lead-research-outreach-agent.vercel.app/sign-in
**API docs (Swagger):** https://ai-lead-research-outreach-agent.onrender.com/docs

> Access is invite-only. If you don't have an account yet, ask whoever
> manages the [Access page](https://ai-lead-research-outreach-agent.vercel.app/access)
> to grant your email.

## Current status

This is built in milestones, in order:

- ✅ **Foundations** — auth (Supabase email OTP, allowlisted), Postgres schema, migrations
- ✅ **ICP vertical slice** — objective in, structured target profile out, human confirmation before anything spends money
- ✅ **Guardrails** — deterministic + cheap-model gating on submitted objectives, rate limiting, per-call cost tracking, an admin access-management page
- ✅ **Discovery** — Apify company search, capped and logged, with a speculative buffer + top-up flow for shortfalls
- ✅ **Scraping** — untrusted content isolated from any tool-calling context (zero-tools Claude call, Haiku)
- ✅ **Qualification** — real Agent SDK tool-calling (Sonnet): one session per run works through every
  pending lead via `list_pending_leads` / `save_qualification`, and can call `request_more_candidates`
  (budget/cap-enforced by the tool, never the model) if it notices a shortfall — see note below
- ✅ **Drafting** — 3-step email sequence + LinkedIn message per qualified lead (Sonnet, tool-less,
  cited to scraped evidence), gated by `outbound-copywriting` + `outreach-safety` skills

Every other stage (ICP, sanity check, scraping, drafting) uses a single tool-less, structured-output call, since each
has exactly one right thing to do with its input every time. Qualification is different: which lead to look
at, when to stop, and whether to fetch more candidates are real decisions, so it's built as genuine
tool-calling per the PRD ("the agent should have access to a defined set of tools and should decide which
tool to use") and the architecture doc's original design (`get_lead_context`/`save_qualification`). See
`apps/api/agent/tools/qualification_tools.py` for the tools and `apps/api/agent/options.py`'s
`qualification_session_options()` docstring for the fuller rationale.

Full design rationale lives in [`docs/work/koya_lead_agent_architecture.md`](docs/work/koya_lead_agent_architecture.md).
The original cohort project brief is in [`docs/provided/PRD.md`](docs/provided/PRD.md).

## How to use it

1. **Sign in** at `/sign-in` with an allowlisted email — you'll get a one-time
   code by email (no passwords).
2. **Submit an objective** on the home page — as vague or as specific as you
   like. A quick free/cheap check catches obvious junk before anything
   expensive runs.
3. **Review the target profile**: required criteria, preferred criteria,
   exclusions, plus any assumptions the model made or couldn't verify — all
   editable before you confirm.
4. **Set a lead count** (capped at 25) and confirm. This is the point past
   which nothing is spent without your say-so.
5. Check **My runs** any time for a run's status and estimated Claude spend
   so far. Stage progress (once discovery/qualification/drafting exist)
   shows as nodes at the top of a run's page.

## Architecture at a glance

- **Frontend**: Next.js (App Router) + Tailwind v4, deployed on Vercel
- **Backend**: FastAPI + SQLAlchemy + Postgres, deployed on Render (Docker)
- **Agent runtime**: Claude Agent SDK, one scoped `query()` call per pipeline
  stage rather than a single long-lived agent loop — see the architecture
  doc for why (independent budgets, retries, and tool scoping per stage)
- **Models**: pinned explicitly per stage (Sonnet 5 for ICP refinement,
  Haiku 4.5 for the cheap sanity check) — cost is a hard constraint here,
  never left to a CLI default
- **Skills**: the five guidance docs in `docs/provided/assets/` become
  `.claude/skills/` entries, one per stage that needs judgment

## Contributing / local development

**Prerequisites**: Python 3.12, Node 22, a local Postgres instance.

```bash
cp .env.example apps/api/.env   # fill in ANTHROPIC_API_KEY, SUPABASE_*, etc.
make install                     # backend venv + frontend node_modules
make migrate                     # apply supabase/migrations/ to your dev DB
make test-db                     # create + migrate a SEPARATE test database
make dev                         # backend on :8000, frontend on :3000
make test                        # backend test suite (never touches the dev DB)
```

A few things worth knowing before you touch code:

- **Tests run against their own database, always.** `apps/api/tests/conftest.py`
  refuses to start if the resolved test `DATABASE_URL` matches the dev one —
  tests truncate tables on teardown, so this is a hard guard, not a
  suggestion.
- **Every model call must set `model=` explicitly** (`apps/api/agent/options.py`).
  Cost is a hard constraint on this project; nothing should fall back to
  whatever the Claude CLI defaults to.
- **Skills are derived, not invented.** `.claude/skills/*/SKILL.md` bodies
  must come from the corresponding guide in `docs/provided/assets/` — don't
  write rubric content from scratch.
- **Migrations are numbered and tracked.** `scripts/migrate.sh` records
  applied files in a `schema_migrations` table; add a new
  `supabase/migrations/000N_description.sql` rather than editing an
  existing one.
- Run `make test` before opening a PR. New backend logic should come with
  tests that mock the Claude/Supabase calls — no live network calls in the
  test suite.

## Deployment

- **Backend**: `Dockerfile` + `render-entrypoint.sh` at the repo root (build
  context must be the repo root, not `apps/api/`, since the image also
  needs `.claude/skills/`). Deployed on Render as a Docker web service.
- **Frontend**: deployed on Vercel, root directory `apps/web`.
