import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StudentFriendlyError } from "@/components/student-friendly-error";

describe("StudentFriendlyError", () => {
  it("renders safe copy without stack traces", () => {
    render(
      <StudentFriendlyError
        reference="REQ-ABC123"
        description="We couldn't load this page right now. Your progress is safe."
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/REQ-ABC123/)).toBeInTheDocument();
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/webpack/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sqlalchemy/i)).not.toBeInTheDocument();
  });

  it("invokes retry and links to dashboard", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<StudentFriendlyError onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: /Try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: /Go to Dashboard/i })).toHaveAttribute("href", "/student/dashboard");
  });
});
