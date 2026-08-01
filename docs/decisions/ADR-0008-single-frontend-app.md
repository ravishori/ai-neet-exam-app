# ADR-0008: One Next.js app, route-grouped — not separate web/admin apps

## Status
Accepted

## Context
TALOS.docx's repo layout lists `apps/web` and `apps/admin` as separate
applications. The CTO-frozen layout only specifies
`apps/, packages/, database/, docs/, infrastructure/` without settling the
web/admin split.

## Decision
Single Next.js app (`apps/web`) with route groups: `(public)`, `(auth)`,
`(student)`, `(admin)`. Editorial/admin screens (ECAEP author workspace,
reviewer queue, coverage map) live under `(admin)` in the same app.

## Why
Two separate frontend apps means two deployments, two auth integrations,
and duplicated shared UI — overhead with no benefit at this team size. A
route group gets the same URL/layout separation with one deployable.

## Consequences
If the admin/editorial surface grows enough to need its own release cadence
or its own team, splitting `(admin)` into `apps/admin` later is a folder
move, not a rewrite — the route group boundary is already clean.
