# Code Review Checklist
## AI NEET Exam App

---

# Purpose

This checklist is used by reviewers before approving any Pull Request.

Its objective is to ensure that every change is technically correct, architecturally consistent, secure, maintainable, fully tested, and production-ready.

Repository implementation is the source of truth.

---

# 1. Repository Review

☐ Repository inspected

☐ Existing implementation reviewed

☐ No duplicate functionality introduced

☐ Existing modules reused

☐ Existing APIs reused where appropriate

☐ Existing UI components reused

☐ Existing services reused

☐ Existing repositories reused

☐ Existing tests reused

☐ Repository conventions followed

---

# 2. Feature Scope

☐ Feature matches approved specification

☐ Scope is appropriate

☐ No unnecessary features included

☐ No unrelated code changes

☐ Acceptance criteria satisfied

☐ Business requirements satisfied

---

# 3. Architecture Review

☐ ADRs reviewed

☐ Architecture preserved

☐ Layer boundaries respected

☐ Module responsibilities maintained

☐ No circular dependencies

☐ Dependency direction correct

☐ No architectural shortcuts

☐ No unnecessary abstractions

☐ Architecture documentation updated (if required)

---

# 4. Backend Review

☐ Business logic correct

☐ Services follow project conventions

☐ Repository pattern followed

☐ Dependency Injection used correctly

☐ Validation complete

☐ Error handling implemented

☐ Logging implemented

☐ Background jobs reviewed

☐ No dead code

☐ No duplicated logic

---

# 5. Database Review

☐ Schema reviewed

☐ Existing tables reused

☐ Relationships verified

☐ Constraints verified

☐ Indexes reviewed

☐ Alembic migration correct

☐ Rollback considered

☐ No duplicate entities

☐ No unsafe migrations

---

# 6. API Review

☐ REST conventions followed

☐ Authentication correct

☐ Authorization correct

☐ Validation complete

☐ Pagination implemented (if applicable)

☐ Filtering implemented (if applicable)

☐ Sorting implemented (if applicable)

☐ Search implemented (if applicable)

☐ OpenAPI updated

☐ Backward compatibility preserved

---

# 7. Frontend Review

☐ Existing components reused

☐ Responsive layout verified

☐ Dark Mode verified

☐ Navigation verified

☐ Loading states implemented

☐ Empty states implemented

☐ Error states implemented

☐ Forms validated

☐ State management follows project conventions

☐ UI consistency maintained

---

# 8. Accessibility Review

☐ Keyboard navigation

☐ Focus management

☐ Semantic HTML

☐ ARIA attributes

☐ Color contrast

☐ Screen reader support

☐ Responsive accessibility

☐ WCAG AA reviewed

---

# 9. AI Platform Review

☐ AI services reviewed

☐ Prompt changes reviewed

☐ Knowledge Unit impact reviewed

☐ Embedding impact reviewed

☐ Search impact reviewed

☐ Token usage appropriate

☐ Fallback behaviour verified

☐ No unnecessary AI calls

If not applicable

☐ No AI impact

---

# 10. Security Review

☐ Authentication verified

☐ Authorization verified

☐ Input validation complete

☐ Output encoding verified

☐ Sensitive data protected

☐ Secrets not exposed

☐ Rate limiting reviewed

☐ Audit logging verified

☐ OWASP considerations reviewed

☐ File upload validation (if applicable)

---

# 11. Performance Review

☐ Database queries reviewed

☐ Indexes reviewed

☐ Search performance reviewed

☐ Rendering reviewed

☐ Bundle size acceptable

☐ Memory impact acceptable

☐ CPU impact acceptable

☐ Background processing reviewed

☐ No unnecessary API calls

---

# 12. Testing Review

☐ Unit tests reviewed

☐ Integration tests reviewed

☐ API tests reviewed

☐ Frontend tests reviewed

☐ Regression tests reviewed

☐ Existing tests still pass

☐ Edge cases tested

☐ Failure scenarios tested

☐ Test quality acceptable

---

# 13. Documentation Review

☐ README updated

☐ API documentation updated

☐ Architecture documentation updated

☐ Deployment documentation updated

☐ Release Notes updated

☐ ADR updated (if required)

☐ Developer documentation updated

---

# 14. DevOps Review

☐ Docker impact reviewed

☐ GitHub Actions reviewed

☐ Environment variables documented

☐ Monitoring updated

☐ Logging reviewed

☐ Health checks reviewed

☐ Rollback documented

☐ Deployment impact understood

---

# 15. Code Quality

☐ Readable code

☐ Consistent naming

☐ Small focused methods

☐ Appropriate comments

☐ No commented-out code

☐ No magic values

☐ No unnecessary complexity

☐ Lint passes

☐ Type checking passes

☐ Build passes

---

# 16. Risk Assessment

☐ Technical risks identified

☐ Security risks reviewed

☐ Performance risks reviewed

☐ Migration risks reviewed

☐ Deployment risks reviewed

☐ Operational risks reviewed

☐ Business risks understood

---

# 17. Merge Readiness

☐ Feature complete

☐ Repository remains deployable

☐ CI/CD successful

☐ No unresolved blockers

☐ Manual verification completed

☐ Production ready

---

# Review Decision

PR Number:

Reviewer:

Review Date:

Decision

☐ Approved

☐ Approved with Minor Changes

☐ Changes Requested

☐ Blocked

Comments

____________________________________________________

____________________________________________________

____________________________________________________

---

# Cursor Instructions

Before approving a Pull Request

1. Inspect repository.
2. Review Feature Specification.
3. Review ADRs.
4. Review implementation.
5. Execute tests.
6. Review security.
7. Review accessibility.
8. Review performance.
9. Review documentation.
10. Verify deployment readiness.

Never approve a Pull Request without evidence.

---

# Final Principle

A Pull Request should only be approved when it demonstrably improves the repository without introducing regressions, architectural drift, security risks, or maintainability issues.

Approval signifies that the implementation is consistent with the AI NEET Exam App's architecture, coding standards, testing strategy, and long-term engineering vision.