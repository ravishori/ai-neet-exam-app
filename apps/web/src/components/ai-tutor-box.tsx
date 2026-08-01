"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";

export function AiTutorBox({ conceptId }: { conceptId: string }) {
  const [question, setQuestion] = useState("");
  const ask = useMutation({ mutationFn: () => aiApi.tutorExplain({ concept_id: conceptId, question }) });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Ask the AI Tutor</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {ask.isError && (
          <Alert variant="destructive">
            <AlertDescription>{ask.error instanceof ApiError ? ask.error.message : "Something went wrong"}</AlertDescription>
          </Alert>
        )}
        <div className="flex gap-2">
          <input
            className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
            placeholder="e.g. Why is this true?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button size="sm" disabled={!question || ask.isPending} onClick={() => ask.mutate()}>
            {ask.isPending ? "Asking…" : "Ask"}
          </Button>
        </div>
        {ask.data && (
          <div className="rounded-md border border-dashed p-3 text-sm">
            {ask.data.is_fallback && (
              <Badge variant="outline" className="mb-2">
                Fallback mode — no API key configured
              </Badge>
            )}
            <p className="whitespace-pre-wrap">{ask.data.answer}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
