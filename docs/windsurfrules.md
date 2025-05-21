# 🏄‍♂️ Windsurf Rules – KISS & YAGNI Manifesto for OpusClip Clone

## Core Principles

1. **KISS – Keep It Stupid Simple**
   - Favor clarity over cleverness.
   - If a junior can't understand the code in 5 minutes, rewrite it.
   - No over-engineering or premature optimization.

2. **YAGNI – You Aren't Gonna Need It**
   - Build only what the current tasks in task.md require.
   - No premature abstractions or speculative features.
   - If it's not in the requirements, don't build it.

3. **No Code Smell**
   - Functions ≤ 40 lines.
   - Cyclomatic complexity ≤ 10.
   - One return path unless using guard clauses.
   - Keep nesting depth ≤ 3 levels.

4. **Boy‑Scout Rule**
   - Leave code cleaner than you found it.
   - Refactor incrementally as you go.
   - Improve documentation with each commit.

## Implementation Checklist

- [ ] Does each component have a single responsibility?
- [ ] Are names chosen to express *why* not *how*?
- [ ] Is there an obvious simpler solution?
- [ ] Did we benchmark before optimizing?
- [ ] Could this be data‑driven instead of hard‑coded?
- [ ] Are we following the Go/React/Python idiomatic patterns?
- [ ] Does each service have clear boundaries and interfaces?
- [ ] Are errors handled gracefully and informatively?

## Commit Etiquette

- Prefix with semantic tag: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Limit body to **72 chars/line**.
- Reference task ID from task.md (e.g., `Relates to F-5`).
- Include progress updates (e.g., `Updates F-5 to 🟡`).

## Review Guidelines

| 🚫 Reject If | ✅ Accept When |
|--------------|--------------|
| Magic numbers | Constants/enums |
| Callback hell | `async/await` or Go channels |
| Global state mutation | Pure functions / proper state management |
| Unused imports/packages | Clean import list |
| Debug statements left in | Debug removed or behind flag |
| Hardcoded paths | Configuration-driven paths |
| No error handling | Proper error propagation and logging |
| Inefficient video processing | Optimized FFmpeg parameters |

## Frontend Specifics

- React components ≤ 200 lines.
- Use React Query for data fetching.
- Prefer Tailwind utility classes over custom CSS.
- Use TypeScript for all React components.
- Keep bundle size in check (<500KB main bundle).

## Go Specifics

- Follow standard Go project layout.
- Use modules, not GOPATH.
- Prefer composition over inheritance.
- Proper error handling with context.
- Clear interface boundaries between packages.
- Efficient concurrency with goroutines and channels.

## Python Specifics (AI Service)

- Use FastAPI for API endpoints.
- Proper type hinting throughout.
- Async where beneficial for I/O operations.
- Model loading optimized for memory usage.
- Graceful fallbacks for model failures.

## Performance Guardrails

- Video processing queue wait time < 2 minutes.
- API response time < 200ms for non-processing endpoints.
- Model inference time < 5 seconds per minute of video.
- Storage usage optimized for cost efficiency.
- Client-side memory usage < 300MB.

## Documentation Musts

- OpenAPI/Swagger for all REST endpoints.
- README for each service with setup instructions.
- Code comments explaining "why" not "what".
- Diagrams for architecture and data flow.
- Configuration options documented.

## Golden Rules

> "If in doubt, **delete** and start simpler."

> "Working software trumps perfect architecture."

> "Make it work, make it right, make it fast. In that order."

Signed — *The Video Wizards Squad* 🏄‍♂️

## Process Guidelines

- Mark off your tasks in task.md as you go.
- Update task status from 🔵 (To-Do) to 🟡 (In-Progress) to 🟢 (Done).
- Follow the architecture defined in task.md.
- Let your code be simple, necessary, and smell-free.
- Ask questions if you're not sure what to do.
- Keep the user informed of processing progress.
- Validate assumptions early with proof-of-concepts.
- Choose the right tool for the job, not the trendy one.