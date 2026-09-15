"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Label } from "@/components/ui/label";
import { FieldSelect } from "@/components/ui/field-select";
import { academicApi } from "@/features/academic/api";

/** Practice/mock scope — TOPIC required for Kinematics Ch2 vs Ch3 separation (T6-C). */
export type Scope = {
  scope_type: "SUBJECT" | "CHAPTER" | "TOPIC" | "CONCEPT";
  scope_id: string;
  label: string;
};

export function ScopePicker({ onChange }: { onChange: (scope: Scope | null) => void }) {
  const [subjectId, setSubjectId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [topicId, setTopicId] = useState("");
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
    queryKey: ["academic", "concepts", topicId],
    queryFn: () => academicApi.concepts(topicId),
    enabled: !!topicId,
  });

  const emit = (subj: string, chap: string, topic: string, conc: string) => {
    if (conc) {
      const name = concepts?.find((c) => c.id === conc)?.name ?? "concept";
      onChange({ scope_type: "CONCEPT", scope_id: conc, label: name });
    } else if (topic) {
      const name = topics?.find((t) => t.id === topic)?.name ?? "topic";
      onChange({ scope_type: "TOPIC", scope_id: topic, label: name });
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
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="practice-scope-subject">Subject</Label>
        <FieldSelect
          id="practice-scope-subject"
          value={subjectId}
          onChange={(e) => {
            setSubjectId(e.target.value);
            setChapterId("");
            setTopicId("");
            setConceptId("");
            emit(e.target.value, "", "", "");
          }}
        >
          <option value="">Any subject</option>
          {subjects?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </FieldSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="practice-scope-chapter">Chapter</Label>
        <FieldSelect
          id="practice-scope-chapter"
          value={chapterId}
          disabled={!subjectId}
          onChange={(e) => {
            setChapterId(e.target.value);
            setTopicId("");
            setConceptId("");
            emit(subjectId, e.target.value, "", "");
          }}
        >
          <option value="">Any chapter</option>
          {chapters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </FieldSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="practice-scope-topic">Topic</Label>
        <FieldSelect
          id="practice-scope-topic"
          value={topicId}
          disabled={!chapterId}
          aria-describedby={!chapterId ? undefined : "practice-scope-topic-hint"}
          onChange={(e) => {
            setTopicId(e.target.value);
            setConceptId("");
            emit(subjectId, chapterId, e.target.value, "");
          }}
        >
          <option value="">Any topic in chapter</option>
          {topics?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </FieldSelect>
        {chapterId && (
          <p id="practice-scope-topic-hint" className="text-xs text-muted-foreground">
            For Kinematics, choose a topic to separate Motion in a Straight Line from Motion in a Plane.
          </p>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="practice-scope-concept">Concept</Label>
        <FieldSelect
          id="practice-scope-concept"
          value={conceptId}
          disabled={!topicId}
          onChange={(e) => {
            setConceptId(e.target.value);
            emit(subjectId, chapterId, topicId, e.target.value);
          }}
        >
          <option value="">Any concept in topic</option>
          {concepts?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </FieldSelect>
      </div>
    </div>
  );
}
