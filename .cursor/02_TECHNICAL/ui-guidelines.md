# UI Guidelines
## AI NEET Exam App
### Enterprise UI/UX Standards

Version: 1.0

---

# Purpose

This document defines the official UI/UX standards for the AI NEET Exam App.

The objective is to create a user experience that is:

- Consistent
- Accessible
- Responsive
- Fast
- Intuitive
- Maintainable
- Educationally focused

The UI should help students learn efficiently rather than distract them.

---

# Design Philosophy

Every screen should answer three questions immediately:

1. Where am I?
2. What can I do?
3. What should I do next?

Reduce cognitive load.

Prioritize clarity over visual complexity.

---

# Repository First

Before creating any UI

Inspect

Existing Pages

Existing Components

Layouts

Theme

Icons

Forms

Tables

Dialogs

Navigation

Reuse existing components whenever possible.

Never duplicate UI.

---

# UI Principles

Every screen should be

Simple

Consistent

Responsive

Accessible

Predictable

Fast

Educationally focused

Avoid decorative complexity.

---

# Design Language

Preferred design characteristics

Clean

Professional

Modern

Minimal

Readable

High contrast

Whitespace driven

Content-first

Avoid unnecessary animations.

---

# Layout Standards

Every page should follow a consistent structure.

Header

↓

Breadcrumb (where appropriate)

↓

Page Title

↓

Primary Actions

↓

Main Content

↓

Secondary Information

↓

Footer (if applicable)

Maintain consistent spacing throughout.

---

# Responsive Design

Support

Desktop

Laptop

Tablet

Mobile

Common breakpoints should follow the repository design system.

Never build desktop-only pages.

---

# Theme Support

Every page must support

Light Mode

Dark Mode

Avoid hard-coded colours.

Use theme tokens.

---

# Navigation

Navigation should be

Predictable

Consistent

Minimal

Responsive

Support

Sidebar

Top Navigation

Breadcrumbs

Contextual navigation

Users should never feel lost.

---

# Component Standards

Every component should

Have one responsibility

Be reusable

Be composable

Be testable

Be accessible

Avoid oversized components.

---

# Typography

Prioritize readability.

Hierarchy

Page Title

Section Heading

Subheading

Body Text

Caption

Avoid excessive font sizes.

Maintain consistent spacing.

---

# Colours

Use repository design tokens.

Avoid hard-coded colours.

Use colour to communicate

Success

Warning

Information

Error

Do not rely solely on colour.

Always provide text or icons.

---

# Icons

Icons should

Clarify actions

Not replace labels

Remain consistent

Avoid mixing multiple icon styles.

---

# Buttons

Button hierarchy

Primary

Secondary

Tertiary

Danger

Disabled

Loading

Avoid multiple primary actions on the same screen.

---

# Forms

Every form should include

Labels

Validation

Helpful placeholders (optional)

Inline validation

Error messages

Loading state

Success state

Keyboard accessibility

Never rely on placeholder text as labels.

---

# Input Validation

Validate

Immediately where appropriate

Server-side always

Provide clear error messages.

Avoid technical language.

---

# Tables

Tables should support

Sorting

Filtering

Pagination

Responsive behaviour

Empty state

Loading state

Avoid horizontal scrolling where practical.

---

# Cards

Cards should

Present one logical piece of information

Maintain consistent spacing

Use clear headings

Avoid overcrowding

---

# Dialogs

Use dialogs only when necessary.

Support

Keyboard navigation

Escape to close

Focus trapping

Accessible labels

Avoid stacking dialogs.

---

# Notifications

Support

Success

Warning

Information

Error

Notifications should

Be concise

Actionable

Disappear appropriately

---

# Loading States

Never leave users guessing.

Use

Skeleton loaders

Progress indicators

Loading buttons

Avoid blank pages.

---

# Empty States

Every empty state should explain

Why no data exists

What the user can do next

Avoid empty tables without guidance.

---

# Error States

Every error should provide

Simple explanation

Suggested action

Retry option where appropriate

Avoid technical stack traces.

---

# Search Experience

Search should provide

Instant feedback

Clear filters

Sorting

Pagination

Recent searches (future)

No-results guidance

---

# Educational Experience

The interface should prioritize learning.

Highlight

Question

Explanation

Concept

Progress

Weak areas

Revision

Reduce distractions.

---

# Accessibility

Support

Keyboard navigation

Screen readers

Semantic HTML

Visible focus

Colour contrast

ARIA where appropriate

Forms should be fully accessible.

Follow WCAG principles.

---

# Performance

Avoid

Large bundles

Unnecessary re-renders

Heavy animations

Blocking UI

Optimize

Lazy loading

Code splitting

Image loading

Virtualization for large lists

---

# State Management

Prefer

Local state

Context where appropriate

Existing repository state management

Avoid unnecessary global state.

---

# Images

Optimize images.

Use responsive images.

Provide meaningful alt text.

Never use images for essential text.

---

# File Uploads

Provide

Progress

Validation

Error handling

Retry

Supported file information

---

# Internationalization

Current focus

English

Hindi

Future expansion should be planned.

Avoid hard-coded user-facing strings where localization is expected.

---

# AI Features

AI-generated content should be

Clearly identified

Educationally accurate

Easy to distinguish from official content

Allow users to report incorrect AI output.

---

# Admin Screens

Admin UI should prioritize

Efficiency

Bulk operations

Filtering

Searching

Auditability

Avoid unnecessary animations.

---

# Testing

UI should be tested for

Responsive layouts

Accessibility

Component behaviour

Forms

Navigation

Dark Mode

Light Mode

Regression

---

# Documentation

Whenever UI changes

Review

Screenshots

User documentation

Developer documentation

Component documentation

Keep documentation synchronized.

---

# Cursor Instructions

Before building UI

1. Inspect existing components.

2. Reuse design patterns.

3. Follow theme.

4. Support responsiveness.

5. Support accessibility.

6. Add loading states.

7. Add empty states.

8. Add error handling.

9. Test UI behaviour.

Never redesign existing UI without a product requirement.

---

# Definition of Done

UI work is complete only when

✓ Responsive

✓ Accessible

✓ Theme compatible

✓ Loading states implemented

✓ Empty states implemented

✓ Error handling implemented

✓ Component reuse maximized

✓ Tests updated

✓ Documentation updated

---

# Final Principle

The interface exists to help students learn.

Every screen should reduce friction, improve understanding, and provide a fast, intuitive, and consistent experience.

Good UI should feel obvious, not impressive.