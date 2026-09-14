import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/features/academic/api", () => ({
  academicApi: {
    subjects: () => Promise.resolve([]),
    chapters: () => Promise.resolve([]),
    topics: () => Promise.resolve([]),
    concepts: () => Promise.resolve([]),
  },
}));

vi.mock("@/features/flashcards/api", () => ({
  flashcardsApi: {
    list: () => Promise.reject(new Error("flashcards down")),
  },
}));

import FlashcardsPage from "@/app/student/flashcards/page";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <FlashcardsPage />
    </QueryClientProvider>,
  );
}

describe("Flashcards shell", () => {
  it("renders the four filter comboboxes as native FieldSelect controls", async () => {
    renderPage();
    // FieldSelect renders a native <select>; the accessibility role for
    // single-select natives is combobox.
    await waitFor(() => {
      const combos = screen.getAllByRole("combobox");
      expect(combos.length).toBe(4);
    });
    // Every FieldSelect carries the canonical data-slot handle.
    const slots = document.querySelectorAll('[data-slot="field-select"]');
    expect(slots.length).toBe(4);
  });

  it("surfaces a role=alert Alert when the list query rejects", async () => {
    renderPage();
    const alert = await screen.findByTestId("flashcards-error");
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveTextContent(/Could not load flashcards/i);
  });
});
