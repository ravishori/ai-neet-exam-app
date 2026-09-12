"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const reference = error.digest ?? "UNKNOWN";

  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          padding: "3rem 1.5rem",
          textAlign: "center",
          background: "#fafafa",
          color: "#111",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600 }}>Something went wrong</h1>
        <p style={{ color: "#555", maxWidth: 440, margin: "1rem auto", lineHeight: 1.5 }}>
          We couldn&apos;t load this page right now. Your progress is safe.
          <br />
          Our system has recorded the issue automatically.
          <br />
          Reference: <code>{reference}</code>
        </p>
        <button
          type="button"
          onClick={() => reset()}
          style={{
            padding: "0.65rem 1.25rem",
            borderRadius: 8,
            border: "none",
            background: "#111",
            color: "#fff",
            cursor: "pointer",
            minHeight: 44,
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
