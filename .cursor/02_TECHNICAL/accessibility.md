# Accessibility Standards
## AI NEET Exam App
### Enterprise Accessibility Engineering Guide

Version: 1.0

---

# Purpose

This document defines the accessibility standards for the AI NEET Exam App.

Accessibility is a mandatory quality requirement.

The objective is to ensure that every student can effectively use the platform regardless of physical, visual, auditory, cognitive, or motor abilities.

Accessibility should be considered from the beginning of design and implementation.

---

# Accessibility Philosophy

The platform should be

Inclusive

Accessible

Understandable

Operable

Robust

Accessibility benefits every user, not only users with disabilities.

---

# Compliance Goal

Target

WCAG 2.2 Level AA

Accessibility improvements beyond WCAG are encouraged when they improve usability.

---

# Repository First

Before creating UI

Inspect

Existing Components

Theme

Forms

Dialogs

Navigation

Layouts

Reuse accessible components whenever possible.

Never replace accessible components with inaccessible alternatives.

---

# Core Accessibility Principles

Follow the POUR principles

Perceivable

Operable

Understandable

Robust

Every screen should satisfy all four.

---

# Semantic HTML

Prefer semantic HTML.

Examples

<header>

<nav>

<main>

<section>

<article>

<footer>

<button>

<label>

Avoid replacing semantic elements with generic <div> containers.

---

# Keyboard Navigation

Every interactive element must support keyboard navigation.

Verify

Tab

Shift + Tab

Enter

Space

Escape

Arrow Keys (where applicable)

Users should never become trapped.

---

# Focus Management

Focus should always be visible.

Maintain logical focus order.

Move focus appropriately after

Dialogs

Navigation

Dynamic updates

Validation errors

Never remove visible focus indicators.

---

# Screen Readers

Support

NVDA

JAWS

VoiceOver

Narrator

Provide meaningful labels for all interactive elements.

---

# ARIA

Use ARIA only when native HTML cannot provide equivalent semantics.

Examples

aria-label

aria-labelledby

aria-describedby

aria-expanded

aria-controls

Avoid unnecessary ARIA.

Native HTML is preferred.

---

# Forms

Every form control should include

Visible label

Associated label element

Validation feedback

Required field indicators

Helpful instructions

Never rely solely on placeholder text.

---

# Validation Messages

Error messages should

Be specific

Be understandable

Identify the affected field

Be announced to assistive technologies

Avoid technical language.

---

# Buttons

Buttons should

Have descriptive text

Have accessible names

Support keyboard activation

Show focus indicators

Avoid unlabeled icon-only buttons unless an accessible label is provided.

---

# Links

Links should describe their destination.

Good

View Question Details

Download Biology Notes

Bad

Click Here

Read More

---

# Images

Every meaningful image should include

Descriptive alt text

Decorative images should use

alt=""

Never place important information inside images without text alternatives.

---

# Icons

Icons should support accessible labels when used for actions.

Do not rely solely on icons to communicate meaning.

---

# Tables

Tables should include

Headers

Caption where appropriate

Logical reading order

Responsive behaviour

Avoid using tables for layout.

---

# Dialogs

Dialogs should

Trap focus

Return focus when closed

Support Escape key

Include accessible title

Announce opening to assistive technologies

---

# Navigation

Navigation should

Remain consistent

Support keyboard users

Provide landmarks

Avoid unexpected behaviour

Breadcrumbs should be accessible.

---

# Colour

Do not rely solely on colour.

Use

Icons

Labels

Patterns

Text

Maintain sufficient contrast.

---

# Contrast

Meet or exceed WCAG AA contrast requirements.

Verify

Text

Buttons

Links

Borders

Focus indicators

Charts

Graphs

---

# Typography

Use readable fonts.

Support browser zoom up to 200%.

Avoid fixed font sizes that prevent scaling.

Maintain adequate line spacing.

---

# Motion

Respect user preferences.

Reduce unnecessary animations.

Support

prefers-reduced-motion

Avoid flashing content.

---

# Audio & Video

Provide

Captions

Transcripts

Controls

Pause functionality

Avoid autoplay where possible.

---

# Responsive Accessibility

Accessibility should remain intact across

Desktop

Tablet

Mobile

Landscape

Portrait

---

# Notifications

Announcements should be accessible.

Critical updates should be communicated through appropriate ARIA live regions where necessary.

---

# Loading States

Loading indicators should be understandable.

Avoid infinite spinners without status information.

---

# Empty States

Explain

Why nothing is displayed

What the user can do next

Use clear language.

---

# Error States

Errors should

Explain the problem

Suggest corrective action

Remain accessible to screen readers

Avoid generic messages.

---

# Educational Content

Questions

Explanations

Tables

Mathematical content

Scientific notation

Diagrams

Should remain accessible whenever practical.

Provide text alternatives for diagrams when possible.

---

# Accessibility Testing

Verify

Keyboard navigation

Screen reader compatibility

Focus management

Colour contrast

ARIA validation

Semantic HTML

Zoom behaviour

Responsive layouts

Use automated tools and manual testing.

---

# Browser Support

Accessibility should be validated on supported browsers.

Avoid browser-specific accessibility issues.

---

# Documentation

Whenever accessibility changes

Review

UI documentation

Component documentation

Testing documentation

Accessibility notes

Keep documentation synchronized.

---

# Cursor Instructions

Before implementing UI

1. Use semantic HTML.

2. Ensure keyboard accessibility.

3. Verify focus management.

4. Add accessible labels.

5. Check colour contrast.

6. Support screen readers.

7. Test responsive layouts.

8. Avoid accessibility regressions.

Accessibility is mandatory.

---

# Accessibility Checklist

Before merging verify

✓ Keyboard navigation

✓ Visible focus

✓ Semantic HTML

✓ Accessible labels

✓ Colour contrast

✓ Screen reader compatibility

✓ Responsive accessibility

✓ Accessible forms

✓ Accessible dialogs

✓ Documentation updated

---

# Definition of Done

Accessibility work is complete only when

✓ WCAG principles followed

✓ Keyboard users supported

✓ Screen readers supported

✓ Accessible forms

✓ Accessible navigation

✓ Tests completed

✓ Documentation updated

---

# Final Principle

Education should be accessible to everyone.

Every interface should be usable regardless of ability, device, or assistive technology.

Accessibility is a core engineering responsibility, not an optional enhancement.