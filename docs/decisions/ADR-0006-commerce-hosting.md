# ADR-0006: Payment gateway and MVP hosting

## Status
Accepted

## Decision
- **Payments**: Razorpay (UPI, cards, net banking, GST invoicing,
  subscriptions). Stripe/Apple/Google Play billing considered only if/when
  international expansion is real.
- **Hosting**: Coolify on a Hetzner VPS for the MVP. Revisit AWS/Azure/GCP
  only when Coolify's single-VPS model genuinely can't scale further.

## Why
India-first product, India-first payment rails. Coolify + Hetzner is the
lowest-cost path to a production deployment with good Docker support, and
avoids committing to cloud-provider complexity before there's traffic that
needs it.

## Consequences
Commerce module (Sprint 9) integrates the Razorpay SDK directly, no
payment-gateway abstraction layer until a second gateway is actually
needed.
