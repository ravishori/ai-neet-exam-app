"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Label } from "@/components/ui/label";
import { academicApi } from "@/features/academic/api";

export type Scope = { scope_type: "SUBJECT" | "CHAPTER" | "CONCEPT"; scope_id: string; label: string };

export function ScopePicker({ onChange }: { onChange: (scope: Scope | null) => void }) {
  const [subjectId, setSubjectId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [conceptId, setConceptId] = useState("");

  const { data: subjects } = useQuery({ queryKey: ["academic", "subjects"], queryFn: academicApi.subjects });
  const { data: chapters } = useQuery({
    queryKey: ["academic", "chapters", subjectId],
    queryFn: () => academicApi.chapters(subjectId),
    enabled: !!subjectId,
  });
  const { data: topics } = useQuery({
    queryKey: ["academic", "topics", chapterId],
    queryFn: () => academicApi.topics(chapterId),
    enabled: !!chapterId,
  });
  const { data: concepts } = useQuery({
    queryKey: ["academic", "concepts-for-topics", topics?.map((t) => t.id).join(",")],
    queryFn: async () => {
      if (!topics) return [];
      const lists = await Promise.all(topics.map((t) => academicApi.concepts(t.id)));
      return lists.flat();
    },
    enabled: !!topics?.length,
  });

  const emit = (subj: string, chap: string, conc: string) => {
    if (conc) {
      const name = concepts?.find((c) => c.id === conc)?.name ?? "concept";
      onChange({ scope_type: "CONCEPT", scope_id: conc, label: name });
    } else if (chap) {
      const name = chapters?.find((c) => c.id === chap)?.name ?? "chapter";
      onChange({ scope_type: "CHAPTER", scope_id: chap, label: name });
    } else if (subj) {
      const name = subjects?.find((s) => s.id === subj)?.name ?? "subject";
      onChange({ scope_type: "SUBJECT", scope_id: subj, label: name });
    } else {
      onChange(null);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div className="flex flex-col gap-1.5">
        <Label>Subject</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={subjectId}
          onChange={(e) => {
            setSubjectId(e.target.value);
            setChapterId("");
            setConceptId("");
            emit(e.target.value, "", "");
          }}
        >
          <option value="">Any subject</option>
          {subjects?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Chapter</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={chapterId}
          disabled={!subjectId}
          onChange={(e) => {
            setChapterId(e.target.value);
            setConceptId("");
            emit(subjectId, e.target.value, "");
          }}
        >
          <option value="">Any chapter</option>
          {chapters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Concept</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={conceptId}
          disabled={!chapterId}
          onChange={(e) => {
            setConceptId(e.target.value);
            emit(subjectId, chapterId, e.target.value);
          }}
        >
          <option value="">Any concept</option>
          {concepts?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
