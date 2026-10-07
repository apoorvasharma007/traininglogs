# Codebase Reorganization & Documentation Plan

## Goal
Establish a professional, well-documented codebase structure that clearly separates source code from operational artifacts, with exhaustive comments and a comprehensive code walkthrough document. This positions the app as production-ready and showcases engineering rigor.

## Blast Radius
- Directory restructuring at repo root (non-destructive moves, no code changes)
- Comments added to all source files (backend + frontend)
- New code walkthrough document created
- No changes to functionality, tests, or dependencies

---

## Phase 1: Directory Reorganization

### Current state (cluttered root)
```
Root contains: 15 plan/doc files, 4 output .txt files, scattered data, archived code
```

### Proposed structure
```
root/
├── src/                          (backend source, unchanged)
├── frontend/                     (frontend source, unchanged)
├── tests/                        (test files, unchanged)
├── docs/                         (documentation)
│   ├── architecture.md           (API + data model overview)
│   ├── design.html               (existing design doc)
│   ├── planning/                 (all plan files)
│   │   ├── phase-9-plan.md
│   │   ├── react-plan.md
│   │   ├── db-redesign-plan.md
│   │   ├── docs-overhaul-plan.md
│   │   ├── codebase-cleanup-plan.md (this file)
│   │   └── roadmap.md
│   └── extraction-design-principles.md
├── infra/                        (terraform, existing)
├── data/                         (non-source files)
│   ├── inputs/                   (test data)
│   │   ├── programs/
│   │   └── sessions/
│   └── backups/                  (database backups)
│       ├── prod-before-*.json
│       └── program_workouts-*.json
├── outputs/                      (generated artifacts)
│   ├── eval_runs/
│   ├── historical-review/
│   ├── output_training_logs_json/
│   ├── output_training_logs_json_v3.0.0/
│   ├── arms_out.txt
│   ├── eval_out.txt
│   ├── groq_out.txt
│   └── haiku_out.txt
├── archive/                      (old code/plans, already exists but clean)
│   ├── guides/
│   ├── plans/
│   ├── scripts/
│   └── src/
├── tools/                        (utility scripts)
│   └── scripts/ (from root)
├── config/                       (configuration)
│   └── key_lifts.yaml
├── .github/                      (CI/CD workflows, existing)
├── .claude/                      (Claude project notes, existing)
├── (root config files: docker-compose.yml, Dockerfile, pyproject.toml, etc.)
```

### Detailed moves

#### To docs/planning/
- phase-9-plan.md
- react-plan.md
- db-redesign-plan.md
- docs-overhaul-plan.md
- roadmap.md

#### To docs/
- extraction-design-principles.md

#### To data/inputs/
- inputs/programs/ (whole dir)
- inputs/sessions/ (whole dir)

#### To data/backups/
- backups/ (whole dir, keep as-is)

#### To outputs/
- eval_runs/ (whole dir)
- historical-review/ (whole dir)
- output_training_logs_json/ (whole dirs)
- arms_out.txt
- eval_out.txt
- groq_out.txt
- haiku_out.txt

#### To tools/
- scripts/ (from root)

#### To config/
- config/ (already organized, keep)

#### Keep at root
- src/
- frontend/
- tests/
- infra/
- docs/
- .github/
- .claude/
- CLAUDE.md (instructions)
- README.md (project overview)
- CHANGELOG.md (release notes)
- ux-audit.md (recent changes)
- pyproject.toml (Python config)
- requirements*.lock (dependencies)
- docker-compose.yml (dev setup)
- Dockerfile (build)
- .env.example (example secrets)
- All .gitignore, .python-version, etc (dotfiles)

---

## Phase 2: Backend Code Comments

### Strategy
- Every module gets a docstring explaining its purpose
- Every function gets a one-line docstring (what it does, not how)
- Complex logic gets a comment explaining the "why"
- No docstrings for trivial getters/setters
- Comments are concise and in plain language

### Backend modules to document
```
src/traininglogs/
├── api/          (FastAPI endpoints)
├── db/           (database queries)
├── models/       (Pydantic schemas)
├── ingest/       (note parsing, extraction)
├── agent/        (AI prompts and agents)
├── analytics/    (strength analysis)
├── processor/    (data processing)
├── parser/       (text parsing)
├── cli/          (command-line tools)
└── program_templates.py
```

---

## Phase 3: Frontend Code Comments

### Strategy
- Every component gets a docstring (what it renders and why)
- Hooks get docstrings (what they manage, dependencies)
- Complex state logic gets comments explaining invariants
- Event handlers get one-line comments (e.g., "// Submit set and close sheet")
- Test files get comments explaining what each test block covers

### Frontend modules to document
```
frontend/src/
├── screens/      (top-level pages)
├── components/   (reusable UI)
├── lib/          (utilities, helpers, API)
└── (tests)
```

---

## Phase 4: Code Walkthrough Document

### Output: docs/code-walkthrough.md
A comprehensive guide with:
1. **Architecture overview** — high-level flow (user → frontend → API → DB)
2. **Backend walkthrough** — each module, key functions, with GitHub links
3. **Frontend walkthrough** — each screen and component, data flow
4. **Key patterns** — how sessions are logged, how programs work, how data is validated
5. **Testing strategy** — where tests live, how to run them
6. **Deployment flow** — how changes move from dev to prod

Each section will include:
- Links to source files on GitHub (e.g., `[app.py](https://github.com/.../blob/main/src/traininglogs/api/app.py)`)
- Code snippets for key functions
- Diagrams (ASCII or Mermaid) where helpful

---

## Steps (branch-per-step)

- [ ] Step 1: Create directory structure and move files (codebase-cleanup-1-reorganize)
- [ ] Step 2: Add comments to backend modules (codebase-cleanup-2-backend-comments)
- [ ] Step 3: Add comments to frontend modules (codebase-cleanup-3-frontend-comments)
- [ ] Step 4: Write code walkthrough document (codebase-cleanup-4-walkthrough)

All steps verify with tests green and manual review before merging.

---

## ▶ Resume here

**Next step:** User approves plan above, then proceed with Step 1 (reorganize directories).

Current branch: main (ready to branch)
