import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const modules = [
  { name: "Identity & Auth", sprint: "SP1", status: "done" },
  { name: "Academic Engine", sprint: "SP2", status: "next" },
  { name: "Content (ECAEP) + Question Bank", sprint: "SP3", status: "planned" },
  { name: "Assessment Engine", sprint: "SP4", status: "planned" },
  { name: "AI Gateway — Tutor, Planner, Generator, Evaluator", sprint: "SP5", status: "planned" },
] as const;

export default function LandingPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-10 px-6 py-24">
      <nav className="absolute top-6 right-6 flex gap-2">
        <Link href="/login" className={cn(buttonVariants({ variant: "ghost" }))}>
          Sign in
        </Link>
        <Link href="/register" className={cn(buttonVariants())}>
          Create account
        </Link>
      </nav>

      <div className="flex flex-col items-center gap-3 text-center">
        <Badge variant="secondary">Sprint 1 — Identity &amp; Auth</Badge>
        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-balance">
          Trinetra AI Learning OS
        </h1>
        <p className="max-w-lg text-muted-foreground">
          An AI-first NEET preparation platform. Registration, login, sessions,
          and role-based access are wired end to end — real learning modules
          land sprint by sprint from here.
        </p>
      </div>

      <div className="grid w-full max-w-2xl gap-3 sm:grid-cols-2">
        {modules.map((m) => (
          <Card key={m.sprint}>
            <CardHeader>
              <CardTitle className="text-base">{m.name}</CardTitle>
              <CardDescription>{m.sprint}</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant={m.status === "done" ? "default" : m.status === "next" ? "secondary" : "outline"}>
                {m.status}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
