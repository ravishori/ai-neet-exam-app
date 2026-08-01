import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const modules = [
  { name: "Identity & Auth", sprint: "SP1", status: "next" },
  { name: "Academic Engine", sprint: "SP2", status: "planned" },
  { name: "Content (ECAEP) + Question Bank", sprint: "SP3", status: "planned" },
  { name: "Assessment Engine", sprint: "SP4", status: "planned" },
  { name: "AI Gateway — Tutor, Planner, Generator, Evaluator", sprint: "SP5", status: "planned" },
] as const;

export default function LandingPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-10 px-6 py-24">
      <div className="flex flex-col items-center gap-3 text-center">
        <Badge variant="secondary">Foundation — Sprint 0</Badge>
        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-balance">
          Trinetra AI Learning OS
        </h1>
        <p className="max-w-lg text-muted-foreground">
          An AI-first NEET preparation platform. This shell confirms the
          frontend foundation is wired to the backend, the design system, and
          light/dark theming — real modules land sprint by sprint from here.
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
              <Badge variant={m.status === "next" ? "default" : "outline"}>
                {m.status}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
