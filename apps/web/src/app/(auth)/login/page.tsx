import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Placeholder shell — wired up in Sprint 1 (Identity &amp; Auth).
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Login form, JWT issuance, and session handling land with the
          Identity module.
        </CardContent>
      </Card>
    </main>
  );
}
