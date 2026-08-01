"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { cmsApi } from "@/features/cms/api";

const ALL_TYPES = ["CONCEPT_NOTE", "QUESTION", "FLASHCARD", "DIAGRAM", "VIDEO_REF", "FORMULA_SHEET"];

export default function CoveragePage() {
  const { data: rows, isLoading } = useQuery({ queryKey: ["cms", "coverage"], queryFn: cmsApi.coverage });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-2 text-xl font-semibold">Content coverage</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Every concept in the curriculum against what&apos;s been published for it — the literal UI for
        &quot;seed one chapter completely before scaling&quot;.
      </p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="p-2 text-left">Subject</th>
              <th className="p-2 text-left">Chapter</th>
              <th className="p-2 text-left">Concept</th>
              {ALL_TYPES.map((t) => (
                <th key={t} className="p-2 text-center text-xs">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows?.map((row) => (
              <tr key={row.concept_id} className="border-t">
                <td className="p-2">{row.subject_name}</td>
                <td className="p-2">{row.chapter_name}</td>
                <td className="p-2">{row.concept_name}</td>
                {ALL_TYPES.map((t) => (
                  <td key={t} className="p-2 text-center">
                    {row.published_content_types.includes(t) ? (
                      <Badge variant="default">✓</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
