# Trinetra NEET WhatsApp Bot — Product Requirements

Status: DRAFT FOR IMPLEMENTATION
Date: 2026-09-30
Owner: Trinetra NEET Prep

## 1. Objective
Provide a WhatsApp-based learning interface for Trinetra NEET Prep.

WhatsApp is a channel/interface only. Existing Trinetra learning, assessment,
content, mastery and AI services remain the source of truth.

This document deliberately makes no reference to a specific WhatsApp
messaging provider (Twilio, Meta Cloud API, or otherwise) — the product
requirement is "a WhatsApp channel," not any particular provider's
integration. Which provider carries that channel is an implementation
choice, currently Twilio, made and revisited independently in
[docs/architecture/WHATSAPP_BOT_ARCHITECTURE.md](../architecture/WHATSAPP_BOT_ARCHITECTURE.md)
and
[ADR-WHATSAPP-PROVIDER-ABSTRACTION.md](../decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md),
and must never change anything in this document.

## 2. MVP Goal
Student can:
1. Start a WhatsApp conversation.
2. Link WhatsApp identity to an existing Trinetra account.
3. Start a NEET quiz.
4. Answer MCQs using A/B/C/D.
5. Receive correctness and explanation.
6. Practice flashcards.
7. Review due/revision content.
8. View basic progress.
9. Request study recommendations.
10. Ask the AI Tutor questions.

## 3. MVP Commands
- HI / HELLO / START
- HELP
- LINK
- QUIZ
- FLASHCARDS
- REVISION
- PROGRESS
- RECOMMEND
- STUDY PLAN
- TUTOR

Prefer deterministic commands; use natural-language intent recognition only where useful.

## 4. Learning Engine
Reuse existing:
- AssessmentService
- TutorService
- KnowledgeService
- MasteryService
- RecommendationService
- Study Planner
- Flashcard/CMS services
- existing identity/user services
- existing AIGateway

Do not create a separate WhatsApp learning engine.

## 5. Quiz Behaviour
Questions must come from the existing eligible content pool.

Do not expose:
- drafts
- rejected questions
- unmapped questions
- invalid questions
- questions without valid answers
- unpublished content

Use existing assessment/scoring/attempt infrastructure.

## 6. Account Linking
Never automatically link an existing account solely because the WhatsApp
phone number matches.

Use a secure one-time linking flow with expiry, one-time use, unlinking and
blocked identity handling.

## 7. MVP Exclusions
- voice
- image-question processing
- PDF processing
- full 180-question mock tests
- payments
- parent accounts
- proactive coaching
- sophisticated spaced repetition
- WhatsApp marketing campaigns
- native mobile application
- separate vector/RAG infrastructure

## 8. Conversation Model
Student initiates the initial conversation.

Example:

Student: Hi

Bot:
Welcome to Trinetra NEET Prep.

1. Today's Quiz
2. Flashcards
3. Revision
4. Progress
5. AI Tutor
6. Study Plan

Reply with a number.

## 9. Premium/Freemium
Do not implement subscription enforcement in the first WhatsApp foundation
unless already available through existing entitlement logic.

Future:
FREE = limited daily practice.
PREMIUM = expanded practice/features subject to fair-use controls.

Entitlements should eventually be shared across Web, WhatsApp and future mobile clients.

## 10. Product Principle
WhatsApp is an interface adapter, not a second NEET platform.
Existing Trinetra services and data remain authoritative.
