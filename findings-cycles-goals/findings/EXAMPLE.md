---
title: "(example) login route lacks rate limiting"
created_at: 2026-05-26T09:30:00Z
resolved: false
priority: P1
related:
  - goals/_meta.md
---

# (example) login route lacks rate limiting

> **This is a template/example finding.** Copy the shape, not the content.
> Real findings are named `docs/findings/<UTC>-<slug>.md` (e.g.
> `2026-05-26T0930-login-rate-limit.md`). Delete this file in your repo.

## TL;DR

The login handler accepts unlimited attempts per IP, so credential
stuffing is trivial. Out-of-scope for the active goal (which is about the
signup flow), so queued here rather than fixed inline.

## Body

`src/http/auth-routes.ts:42` registers `POST /login` with no rate-limit
middleware, unlike `POST /signup` which wraps `rateLimit()` at
`src/http/auth-routes.ts:18`. A loop of 10k requests against `/login` in a
local run never throttled (observed 2026-05-26).

## Options / Recommendation

- (A) Reuse the existing `rateLimit()` middleware on `/login`. **Recommended** —
  smallest change, already battle-tested on `/signup`.
- (B) Add a global rate-limit plugin. Larger blast radius; defer.

## Acceptance signal

A new test `tests/e2e/login-rate-limit.test.ts` that fires N+1 requests and
asserts the (N+1)th returns `429`. Today no such test exists; it will go
from red to green.

## Migration plan

1. RED: add the e2e test asserting `429` after the threshold.
2. GREEN: wrap `/login` with the same `rateLimit()` used by `/signup`.
3. Consider promoting to a goal only if "every authenticated mutation route
   is rate-limited" becomes a universal invariant worth a gate.
