# Caching Audit — Phase 0 (Read-Only)

**Companion JSON:** `caching_audit.json` · **Date:** 2026-09-12

## Redis today

| Use | Status | Key pattern (conceptual) |
|-----|--------|--------------------------|
| Rate limiting | **IMPLEMENTED** | `ratelimit:{prefix}:{ip\|user}` + window TTL |
| Alert dedupe | **IMPLEMENTED** | `alert:dedupe:{key}` + cooldown TTL |
| Readiness ping | **IMPLEMENTED** | Connection check |
| Application data cache | **MISSING** | — |
| Session store | **MISSING** | JWT cookies, not Redis sessions |

## Practice FULL pool

| Item | Status |
|------|--------|
| PUBLISHED-only selection | **IMPLEMENTED** (live SQL) |
| Redis/ID-set cache | **MISSING** |
| Selection indexes / avoid Seq Scan at scale | **MISSING** (documented debt in CH01 pilot performance review) |
| Stampede protection | **MISSING** (N/A until cache exists) |

At ~100–1k PUBLISHED items this may be acceptable; at scale it is a P1 scalability risk, not a correctness bug.

## AI tutor / explain cache

| Item | Status |
|------|--------|
| Response cache | **MISSING** (`TutorService` always calls gateway) |
| Offline factory caches | **PARTIAL** (content-factory file caches only) |

**Critical design constraint if added later:** cache keys must include user/tenant boundary (or be limited to non-personalized published content). Never serve Student A’s private tutor thread to Student B.

## Invalidation (when caches exist)

Today pool is live SQL filtered to PUBLISHED, so publish/unpublish/supersede is naturally reflected. Any future cache **must** invalidate on:

- status transitions (DRAFT→…→PUBLISHED / SUPERSEDED)  
- explanation/stem edits  
- taxonomy remaps affecting scoped pools  

## Mandatory stop

No Redis cache features implemented in this phase.
