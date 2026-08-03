"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { searchApi } from "@/features/search/api";
import { ApiError } from "@/lib/api-client";

export default function SearchConsolePage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const searchQuery = useQuery({
    queryKey: ["admin-search", submittedQuery],
    queryFn: () => searchApi.search({ q: submittedQuery, limit: 20 }),
    enabled: submittedQuery.length > 0,
  });

  const reindex = useMutation({ mutationFn: searchApi.reindex });

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="font-heading text-xl font-semibold">Search Console</h1>
            <p className="text-sm text-muted-foreground">Test what students see when they search, and reindex if results look stale.</p>
          </div>
          <Button type="button" variant="outline" size="sm" disabled={reindex.isPending} onClick={() => reindex.mutate()}>
            <RefreshCw className={reindex.isPending ? "size-4 animate-spin" : "size-4"} aria-hidden="true" />
            {reindex.isPending ? "Reindexing…" : "Reindex all published"}
          </Button>
        </div>

        {reindex.data && (
          <Alert>
            <AlertDescription>Reindexed {reindex.data.reindexed_count} published question(s).</AlertDescription>
          </Alert>
        )}
        {reindex.isError && (
          <Alert variant="destructive">
            <AlertDescription>{reindex.error instanceof ApiError ? reindex.error.message : "Reindex failed"}</AlertDescription>
          </Alert>
        )}

        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmittedQuery(query);
          }}
        >
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search questions…" className="flex-1" />
          <Button type="submit" disabled={!query.trim()}>
            <Search className="size-4" aria-hidden="true" /> Search
          </Button>
        </form>

        {searchQuery.isLoading && (
          <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {searchQuery.data && (
          <>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">mode: {searchQuery.data.meta.search_mode}</Badge>
              <span>{searchQuery.data.meta.total} result(s) for &quot;{searchQuery.data.meta.query}&quot;</span>
            </div>

            {searchQuery.data.data.length === 0 ? (
              <EmptyState title="No results" description="Neither full-text nor fuzzy search matched this query." />
            ) : (
              <div className="grid gap-3">
                {searchQuery.data.data.map((item) => (
                  <Card key={item.id}>
                    <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
                      <CardTitle className="text-sm leading-snug">
                        {item.snippet.map((seg, idx) =>
                          seg.highlighted ? (
                            <mark key={idx} className="rounded bg-amber-200 px-0.5 dark:bg-amber-900">
                              {seg.text}
                            </mark>
                          ) : (
                            <span key={idx}>{seg.text}</span>
                          )
                        )}
                      </CardTitle>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">rank {item.rank.toFixed(3)}</span>
                    </CardHeader>
                    <CardContent className="flex flex-wrap items-center gap-1.5 pt-0">
                      {item.subject && <Badge variant="outline">{item.subject.name}</Badge>}
                      {item.concept && <Badge variant="outline">{item.concept.name}</Badge>}
                      {item.matched_fields.map((field) => (
                        <Badge key={field} variant="secondary" className="text-xs">
                          matched: {field}
                        </Badge>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
