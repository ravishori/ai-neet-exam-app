"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConceptPicker } from "@/components/concept-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { cmsApi, type ContentType } from "@/features/cms/api";

const CONTENT_TYPES: ContentType[] = ["CONCEPT_NOTE", "QUESTION", "FLASHCARD", "DIAGRAM", "VIDEO_REF", "FORMULA_SHEET"];

export default function NewContentPage() {
  const router = useRouter();
  const [contentType, setContentType] = useState<ContentType>("CONCEPT_NOTE");
  const [conceptId, setConceptId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");

  // Concept note fields
  const [summary, setSummary] = useState("");
  const [ncertRef, setNcertRef] = useState("");

  // Question fields
  const [stem, setStem] = useState("");
  const [optionA, setOptionA] = useState("");
  const [optionB, setOptionB] = useState("");
  const [optionC, setOptionC] = useState("");
  const [optionD, setOptionD] = useState("");
  const [correctOption, setCorrectOption] = useState("A");
  const [explanation, setExplanation] = useState("");

  const mutation = useMutation({
    mutationFn: cmsApi.create,
    onSuccess: (item) => router.push(`/admin/content/${item.id}`),
  });

  const buildBody = (): Record<string, unknown> => {
    if (contentType === "CONCEPT_NOTE") {
      return { summary, ncert_ref: ncertRef || undefined, sections: [] };
    }
    if (contentType === "QUESTION") {
      return {
        stem,
        options: [
          { label: "A", text: optionA },
          { label: "B", text: optionB },
          { label: "C", text: optionC },
          { label: "D", text: optionD },
        ],
        correct_option: correctOption,
        explanation,
        difficulty: "medium",
      };
    }
    return {};
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      content_type: contentType,
      concept_id: conceptId ?? undefined,
      title,
      slug,
      body: buildBody(),
    });
  };

  return (
    <main className="flex flex-1 justify-center px-6 py-10">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>New content</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            {mutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {mutation.error instanceof ApiError ? mutation.error.message : "Something went wrong"}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-1.5">
              <Label>Content type</Label>
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={contentType}
                onChange={(e) => setContentType(e.target.value as ContentType)}
              >
                {CONTENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              {!["CONCEPT_NOTE", "QUESTION"].includes(contentType) && (
                <p className="text-xs text-muted-foreground">
                  This content type doesn&apos;t have a dedicated form yet — it will be created with an empty
                  body you can fill in via the API directly.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Concept</Label>
              <ConceptPicker value={conceptId} onChange={setConceptId} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="title">Title</Label>
                <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="slug">Slug</Label>
                <Input id="slug" value={slug} onChange={(e) => setSlug(e.target.value)} required />
              </div>
            </div>

            {contentType === "CONCEPT_NOTE" && (
              <>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="ncert_ref">NCERT reference</Label>
                  <Input id="ncert_ref" value={ncertRef} onChange={(e) => setNcertRef(e.target.value)} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="summary">Summary</Label>
                  <textarea
                    id="summary"
                    className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm"
                    value={summary}
                    onChange={(e) => setSummary(e.target.value)}
                    required
                  />
                </div>
              </>
            )}

            {contentType === "QUESTION" && (
              <>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="stem">Question</Label>
                  <textarea
                    id="stem"
                    className="min-h-16 rounded-md border bg-background px-3 py-2 text-sm"
                    value={stem}
                    onChange={(e) => setStem(e.target.value)}
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Input placeholder="Option A" value={optionA} onChange={(e) => setOptionA(e.target.value)} required />
                  <Input placeholder="Option B" value={optionB} onChange={(e) => setOptionB(e.target.value)} required />
                  <Input placeholder="Option C" value={optionC} onChange={(e) => setOptionC(e.target.value)} required />
                  <Input placeholder="Option D" value={optionD} onChange={(e) => setOptionD(e.target.value)} required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Correct option</Label>
                  <select
                    className="h-9 w-24 rounded-md border bg-background px-2 text-sm"
                    value={correctOption}
                    onChange={(e) => setCorrectOption(e.target.value)}
                  >
                    {["A", "B", "C", "D"].map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="explanation">Explanation</Label>
                  <textarea
                    id="explanation"
                    className="min-h-16 rounded-md border bg-background px-3 py-2 text-sm"
                    value={explanation}
                    onChange={(e) => setExplanation(e.target.value)}
                    required
                  />
                </div>
              </>
            )}

            <Button type="submit" disabled={mutation.isPending} className="mt-2 w-fit">
              {mutation.isPending ? "Creating…" : "Create draft"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
