"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Label } from "@/components/ui/label";
import { academicApi } from "@/features/academic/api";

export function ConceptPicker({ value, onChange }: { value: string | null; onChange: (conceptId: string | null) => void }) {
  const [subjectId, setSubjectId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [topicId, setTopicId] = useState("");

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
    queryKey: ["academic", "concepts", topicId],
    queryFn: () => academicApi.concepts(topicId),
    enabled: !!topicId,
  });

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div className="flex flex-col gap-1.5">
        <Label>Subject</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={subjectId}
          onChange={(e) => {
            setSubjectId(e.target.value);
            setChapterId("");
            setTopicId("");
            onChange(null);
          }}
        >
          <option value="">Select…</option>
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
            setTopicId("");
            onChange(null);
          }}
        >
          <option value="">Select…</option>
          {chapters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Topic</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={topicId}
          disabled={!chapterId}
          onChange={(e) => {
            setTopicId(e.target.value);
            onChange(null);
          }}
        >
          <option value="">Select…</option>
          {topics?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Concept</Label>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={value ?? ""}
          disabled={!topicId}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">Select…</option>
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
