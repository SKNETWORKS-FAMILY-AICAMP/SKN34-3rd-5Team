<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Frontend application authentication

- Use JWT only: send the access token as `Authorization: Bearer <token>` and keep the refresh token in the existing per-tab `sessionStorage` lifecycle.
- Do not add authentication cookies, `document.cookie`, `credentials`-based cookie fallback, or `kbo_access`/`kbo_refresh` cookies. Never record real credentials or tokens in source or documentation.
- Django's native admin session and guest course edit tokens are separate framework/resource capabilities and are outside this frontend application-auth rule.
