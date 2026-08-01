"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { usersApi } from "@/features/users/api";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी (Hindi)" },
];

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({ queryKey: ["users", "me"], queryFn: usersApi.me });

  const updateLanguage = useMutation({
    mutationFn: (preferred_language: string) => usersApi.updateMe({ preferred_language }),
    onSuccess: (updated) => queryClient.setQueryData(["users", "me"], updated),
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Settings</CardTitle>
          <CardDescription>Content language and study preferences.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {updateLanguage.isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {updateLanguage.error instanceof ApiError ? updateLanguage.error.message : "Something went wrong"}
              </AlertDescription>
            </Alert>
          )}
          <div className="flex flex-col gap-1.5">
            <Label>Content language</Label>
            <select
              className="h-9 w-56 rounded-md border bg-background px-2 text-sm"
              value={profile?.preferred_language ?? "en"}
              disabled={updateLanguage.isPending}
              onChange={(e) => updateLanguage.mutate(e.target.value)}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Concept notes and questions show in this language where translated, with English as a fallback.
            </p>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
