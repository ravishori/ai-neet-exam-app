# Good React Component Reference Implementation
## AI NEET Exam App

---

# Purpose

This document defines the canonical React component implementation for the AI NEET Exam App.

It provides the standard component architecture that Cursor should follow whenever creating or modifying React components.

Repository implementation is the source of truth.

Consistency is more important than personal coding preferences.

---

# Design Philosophy

Every component should be

✓ Simple

✓ Reusable

✓ Accessible

✓ Type-safe

✓ Responsive

✓ Testable

✓ Maintainable

✓ Performant

---

# Component Responsibilities

A React component is responsible for

✓ Rendering UI

✓ Handling user interaction

✓ Calling hooks

✓ Displaying data

✓ Managing presentation state

✓ Displaying loading states

✓ Displaying empty states

✓ Displaying error states

A component should NOT

✗ Contain business logic

✗ Execute API calls directly

✗ Perform database operations

✗ Duplicate validation logic

✗ Duplicate styling patterns

---

# Standard Architecture

Page

↓

Layout

↓

Feature Component

↓

Reusable UI Components

↓

Custom Hooks

↓

React Query

↓

API Client

↓

FastAPI

---

# Folder Structure

components/

ui/

layout/

features/

forms/

tables/

cards/

dialogs/

charts/

hooks/

pages/

Maintain clear separation between presentation and business logic.

---

# TypeScript Guidelines

Always

✓ Define Props interfaces

✓ Use explicit types

✓ Avoid "any"

✓ Prefer readonly props where appropriate

✓ Export component types if reused

Avoid

❌ Implicit any

❌ Untyped callbacks

❌ Unsafe type assertions

---

# Component Structure

Preferred order

1. Imports

2. Types / Interfaces

3. Constants

4. Component

5. Hooks

6. Event handlers

7. Derived values

8. JSX

9. Export

Maintain a consistent structure across all components.

---

# Props

Props should

Be minimal

Be descriptive

Be typed

Avoid unnecessary optional fields

Avoid passing large objects when IDs or smaller models suffice.

---

# State Management

Use

Local state for UI concerns

React Query for server state

React Hook Form for forms

Context only for shared application state

Avoid

Large global state

Prop drilling

Duplicated state

---

# Data Fetching

Use React Query.

Never fetch data directly inside JSX.

Prefer

Caching

Automatic refetch

Optimistic updates (where appropriate)

Retry policies

Background refresh

---

# Forms

Use React Hook Form.

Validation

Client validation

Server validation

Accessible error messages

Proper labels

Never duplicate validation logic.

---

# Loading States

Every async component should provide

Skeleton loaders

Loading indicators

Disabled actions during loading

Avoid blank screens.

---

# Empty States

Every collection should define

Meaningful message

Helpful guidance

Call-to-action when appropriate

Avoid empty tables or blank cards.

---

# Error States

Handle

Network errors

Validation errors

Unexpected failures

Permission errors

Display user-friendly messages.

Never expose internal stack traces.

---

# Accessibility

Every component should support

Keyboard navigation

Visible focus indicators

Semantic HTML

ARIA labels where needed

Screen readers

Logical tab order

Color contrast meeting WCAG AA

Accessibility is mandatory.

---

# Responsive Design

Support

Mobile

Tablet

Desktop

Large screens

Use responsive layouts.

Avoid fixed widths where unnecessary.

---

# Dark Mode

Support both themes.

Verify

Text contrast

Icons

Borders

Backgrounds

Hover states

Focus indicators

Never hardcode colors.

---

# Performance

Prefer

Memoization where justified

Lazy loading

Code splitting

Small components

Virtualization for large lists

Avoid

Unnecessary re-renders

Heavy computations during render

Large component trees

Premature optimization

---

# Styling

Use project styling conventions.

Prefer

Reusable UI components

Design tokens

Shared spacing

Consistent typography

Avoid

Inline styles

Duplicated utility classes

Inconsistent spacing

---

# Component Composition

Favor composition over inheritance.

Reuse

Cards

Buttons

Inputs

Dialogs

Tables

Badges

Icons

Do not duplicate UI.

---

# API Integration

Components should call hooks.

Hooks call services.

Services call APIs.

Never call FastAPI directly from presentation components.

---

# Security

Do not expose

Secrets

Tokens

Sensitive user data

Internal identifiers unnecessarily

Never trust client-side validation alone.

---

# Testing Expectations

Every important component should include

✓ Render test

✓ Interaction test

✓ Loading state test

✓ Empty state test

✓ Error state test

✓ Accessibility validation

✓ Responsive behaviour where practical

Use React Testing Library.

Avoid implementation-detail testing.

---

# Code Review Expectations

Reviewers should verify

✓ Props typed

✓ Accessibility maintained

✓ Responsive layout verified

✓ Dark Mode supported

✓ Existing components reused

✓ Hooks reused

✓ React Query used appropriately

✓ Forms validated

✓ Loading state included

✓ Error state included

✓ Empty state included

✓ Tests added

---

# Common Anti-Patterns

Never

❌ Put business logic inside components

❌ Fetch directly in JSX

❌ Duplicate UI

❌ Use "any"

❌ Ignore accessibility

❌ Ignore loading states

❌ Ignore error states

❌ Ignore empty states

❌ Hardcode colors

❌ Create oversized components

---

# Cursor Instructions

When implementing or modifying a React component

1. Inspect the repository.
2. Search for similar components.
3. Reuse existing UI.
4. Keep business logic outside the component.
5. Use TypeScript.
6. Ensure accessibility.
7. Support responsive layouts.
8. Support Dark Mode.
9. Add loading, error, and empty states.
10. Add appropriate tests.

Never redesign the UI architecture without an approved ADR.

---

# Final Principle

Every React component should be small, reusable, accessible, responsive, and consistent.

A developer reading any component in the AI NEET Exam App should immediately recognize the same architectural patterns, coding style, and quality standards.

The objective is to create a frontend that is maintainable, predictable, scalable, and easy for both engineers and AI assistants to extend.