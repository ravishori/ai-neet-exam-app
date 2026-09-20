import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { SkipToMain } from "@/components/ds/skip-to-main";
import { StudentPage, STUDENT_MAIN_ID } from "@/components/ds/student-page";

describe("SkipToMain", () => {
  it("renders a skip link that targets the shared main id", () => {
    render(<SkipToMain />);
    const link = screen.getByTestId("skip-to-main");
    expect(link).toHaveAttribute("href", `#${STUDENT_MAIN_ID}`);
    expect(link).toHaveTextContent(/skip to main content/i);
  });

  it("StudentPage exposes the main landmark with id and tabIndex=-1", () => {
    render(
      <StudentPage>
        <p>body</p>
      </StudentPage>,
    );
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", STUDENT_MAIN_ID);
    expect(main).toHaveAttribute("tabIndex", "-1");
  });

  it("is visually hidden by default (sr-only class present)", () => {
    render(<SkipToMain />);
    expect(screen.getByTestId("skip-to-main").className).toMatch(/sr-only/);
  });
});
