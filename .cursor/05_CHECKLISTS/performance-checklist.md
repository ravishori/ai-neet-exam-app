# Performance Validation Checklist
## AI NEET Exam App

---

# Purpose

This checklist ensures that every feature, API, deployment, and release meets the project's performance requirements before production.

Repository implementation is the source of truth.

---

# 1. Repository Review

☐ Existing implementation reviewed

☐ Existing performance optimizations reused

☐ Existing caching reused

☐ Existing indexes reviewed

☐ Existing benchmarks reviewed

---

# 2. Backend Performance

☐ Business logic efficient

☐ No unnecessary loops

☐ No blocking operations

☐ Async code used correctly

☐ Background jobs used appropriately

☐ No duplicated computation

---

# 3. Database Performance

☐ Indexes reviewed

☐ Queries optimized

☐ No N+1 queries

☐ Pagination implemented

☐ Sorting optimized

☐ Filtering optimized

☐ Execution plans reviewed (if applicable)

---

# 4. API Performance

☐ Response time acceptable

☐ Payload minimized

☐ Compression enabled (where applicable)

☐ Pagination implemented

☐ Search optimized

☐ Validation efficient

---

# 5. Frontend Performance

☐ Bundle size reviewed

☐ Lazy loading used

☐ Code splitting used

☐ Images optimized

☐ Rendering efficient

☐ No unnecessary re-renders

☐ Loading indicators present

---

# 6. Search Performance

☐ Full-text search optimized

☐ Indexes verified

☐ Pagination implemented

☐ Ranking efficient

☐ Search latency acceptable

---

# 7. AI Performance

☐ Prompt optimized

☐ Token usage minimized

☐ AI latency acceptable

☐ Caching reviewed

☐ Fallback behaviour efficient

If not applicable

☐ No AI impact

---

# 8. Infrastructure

☐ Docker optimized

☐ Container size acceptable

☐ Health checks efficient

☐ CI build time acceptable

☐ Deployment time acceptable

---

# 9. Resource Usage

☐ Memory acceptable

☐ CPU acceptable

☐ Storage acceptable

☐ Network usage acceptable

---

# 10. Monitoring

☐ Metrics available

☐ Slow requests monitored

☐ Performance alerts configured

☐ Logs reviewed

---

# 11. Testing

☐ Load testing completed (if required)

☐ Stress testing completed (if required)

☐ Performance regression reviewed

☐ Existing benchmarks maintained

---

# Final Validation

☐ No significant regression

☐ Performance acceptable

☐ Repository scalable

☐ Production ready

---

# Cursor Instructions

Review the repository before approving performance.

Base recommendations on evidence.

Never invent performance problems.

---

# Final Principle

Performance improvements should always be measurable, evidence-based, and preserve repository architecture.