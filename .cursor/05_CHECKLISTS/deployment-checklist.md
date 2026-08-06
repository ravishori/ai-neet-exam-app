# Production Deployment Checklist
## AI NEET Exam App

---

# Purpose

This checklist defines the mandatory verification steps before deploying any release to a production environment.

The objective is to ensure that deployments are safe, repeatable, observable, and recoverable.

Repository implementation is the source of truth.

No production deployment should begin until all applicable checks have been completed.

---

# 1. Repository Validation

☐ Correct branch selected

☐ Repository clean (no unintended changes)

☐ Required commits merged

☐ Pull Request approved

☐ Release tag created (if applicable)

☐ Version number updated

☐ Changelog updated

☐ Release Notes prepared

---

# 2. Build Validation

☐ Backend builds successfully

☐ Frontend builds successfully

☐ Docker images build successfully

☐ Build reproducible

☐ Version information correct

☐ Build artifacts verified

---

# 3. Code Quality

☐ Lint passes

☐ Type checking passes

☐ Static analysis completed

☐ Code review approved

☐ No unresolved TODOs blocking release

☐ No critical technical debt introduced

---

# 4. Testing Validation

☐ Unit tests pass

☐ Integration tests pass

☐ API tests pass

☐ Frontend tests pass

☐ Regression tests pass

☐ Security tests pass

☐ Performance tests reviewed

☐ Manual smoke testing completed

---

# 5. Database Readiness

☐ Migrations reviewed

☐ Migration order verified

☐ Backup completed

☐ Rollback migration documented

☐ Index creation verified

☐ Constraints verified

☐ Migration tested in staging

☐ No destructive migration without approval

---

# 6. API Readiness

☐ OpenAPI updated

☐ Authentication verified

☐ Authorization verified

☐ Validation verified

☐ Backward compatibility reviewed

☐ Deprecated endpoints documented

☐ API versioning verified

---

# 7. Frontend Readiness

☐ Production build verified

☐ Responsive layouts verified

☐ Dark Mode verified

☐ Accessibility verified

☐ Navigation verified

☐ Loading states verified

☐ Error states verified

☐ Browser compatibility reviewed

---

# 8. AI Platform Readiness

☐ AI providers configured

☐ API keys available

☐ Prompt configuration verified

☐ Knowledge Unit pipeline verified

☐ Embeddings verified

☐ Search functionality verified

☐ AI fallback behaviour verified

☐ AI monitoring configured

If not applicable

☐ No AI deployment impact

---

# 9. Security Validation

☐ Authentication verified

☐ Authorization verified

☐ Secrets configured

☐ Environment variables verified

☐ Dependency scan reviewed

☐ No Critical vulnerabilities

☐ High vulnerabilities addressed or accepted

☐ Audit logging enabled

☐ Rate limiting verified

---

# 10. Docker Validation

☐ Docker images built

☐ Images tagged correctly

☐ Images scanned

☐ Image size acceptable

☐ Health checks configured

☐ Multi-stage build verified

☐ Registry push successful

---

# 11. CI/CD Validation

☐ GitHub Actions successful

☐ Required workflows passed

☐ Artifact upload successful

☐ Container registry updated

☐ Deployment workflow verified

☐ Manual approval completed (if applicable)

---

# 12. Infrastructure Validation

☐ VPS reachable

☐ Coolify configured

☐ Environment variables configured

☐ SSL certificates valid

☐ Domain configured

☐ Reverse proxy verified

☐ Firewall rules verified

☐ Storage available

---

# 13. Monitoring & Logging

☐ Health endpoint verified

☐ Metrics available

☐ Logs available

☐ Error tracking enabled

☐ Monitoring dashboards updated

☐ Alerts configured

☐ Audit logs enabled

☐ Correlation IDs verified

---

# 14. Deployment Execution

☐ Deployment started

☐ Deployment completed successfully

☐ Containers healthy

☐ Services available

☐ Database connected

☐ Cache connected (if applicable)

☐ Background jobs operational

---

# 15. Post-Deployment Validation

☐ Home page accessible

☐ Login works

☐ Student workflows verified

☐ Admin workflows verified

☐ Search verified

☐ AI features verified

☐ Document upload verified

☐ API health verified

---

# 16. Performance Validation

☐ Response times acceptable

☐ Database healthy

☐ Search latency acceptable

☐ Memory usage acceptable

☐ CPU usage acceptable

☐ No abnormal errors

☐ No performance regression detected

---

# 17. Rollback Readiness

☐ Rollback procedure documented

☐ Previous version available

☐ Database rollback available

☐ Backup verified

☐ Rollback tested (where practical)

☐ Rollback owner assigned

---

# 18. Communication

☐ Stakeholders informed

☐ Release Notes published

☐ Deployment recorded

☐ Incident contacts available

☐ Support team notified

☐ Monitoring team informed

---

# Deployment Status

Deployment Version:

Environment:

Reviewer:

Deployment Date:

Result

☐ Approved

☐ Approved with Conditions

☐ Blocked

☐ Rolled Back

Comments

____________________________________________________

____________________________________________________

____________________________________________________

---

# Cursor Instructions

Before approving deployment

1. Verify repository state.
2. Confirm all quality gates passed.
3. Validate Docker images.
4. Confirm CI/CD success.
5. Verify infrastructure readiness.
6. Execute deployment.
7. Perform smoke testing.
8. Verify monitoring.
9. Confirm rollback readiness.
10. Record deployment outcome.

Never approve deployment without evidence.

---

# Deployment Quality Checklist

✓ Repository verified

✓ Build successful

✓ Tests passed

✓ Security approved

✓ Database ready

✓ Docker validated

✓ CI/CD successful

✓ Infrastructure verified

✓ Monitoring active

✓ Rollback verified

✓ Post-deployment validation completed

---

# Final Principle

A deployment is successful only when the application is running correctly, users can access critical functionality, monitoring confirms healthy operation, and a verified rollback path exists if recovery becomes necessary.

Every deployment should be repeatable, observable, and recoverable.