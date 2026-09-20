# FRONTEND-RUNTIME-003 — Production CSS delivery

**Verdict: GREEN (styles restored on clean production server)** — 2026-09-14

## Exact root cause

Not a missing `globals.css` import and not an A6–A12 regression.

`/register` HTML referenced **`/_next/static/css/app/layout.css`** (dev asset path). That request returned **404**. `main-app.js` also 404’d. The page kept Tailwind class names in HTML but no stylesheet applied → browser-default look.

Cause: **corrupted/mixed `.next`**. A successful `next build` wrote hashed CSS (`df040096…css`, etc.), then a later **`next dev`** rewrote manifests to development paths without those files existing. Port **3000** kept serving that broken process (PID **18240**, Access Denied to kill from this agent).

## Fix (ops only — no app source changes)

1. Remove corrupted `apps/web/.next`
2. `npm run build`
3. `npm run start -- -p 3001 -H 127.0.0.1` (because `:3000` is still held by PID 18240)

Verified on `:3001`: CSS links → **200**, Plus Jakarta + primary button `oklch` applied.

## User action for `:3000`

In an elevated PowerShell:

```powershell
taskkill /F /PID 18240
cd "D:\ravishori\AI Neet Exam App\apps\web"
npm run start -- -p 3000 -H 127.0.0.1
```

Use **`http://127.0.0.1:3000`** (or `:3001` until then). Do not mix `next dev` onto the same `.next` you just built for production.
