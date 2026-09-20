import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";

import { useMounted } from "@/hooks/use-mounted";

function Probe() {
  const mounted = useMounted();
  return <span data-testid="mounted">{mounted ? "yes" : "no"}</span>;
}

describe("FRONTEND-A12 useMounted", () => {
  it("SSR / first paint is unmounted (false)", () => {
    const html = renderToString(<Probe />);
    expect(html).toContain(">no<");
    expect(html).not.toContain(">yes<");
  });

  it("becomes true after client mount", async () => {
    render(<Probe />);
    await waitFor(() => {
      expect(screen.getByTestId("mounted")).toHaveTextContent("yes");
    });
  });
});
