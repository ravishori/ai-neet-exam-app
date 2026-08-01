# Trinetra web

Next.js 15 (App Router) + TypeScript + Tailwind CSS 4 + shadcn/ui. Single
app, route-grouped — see ADR-0008 for why there's no separate admin app.

## Routes

- `(public)/` → `/` — landing shell
- `(auth)/login` → `/login` — placeholder, wired in Sprint 1
- `student/dashboard` → `/student/dashboard` — placeholder
- `admin` → `/admin` — placeholder, gains the ECAEP editorial UI in Sprint 3

## Local setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

## Adding shadcn/ui components

```bash
npx shadcn@latest add <component>
```
