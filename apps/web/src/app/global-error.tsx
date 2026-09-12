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
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "3rem 1.5rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem" }}>Something went wrong</h1>
        <p style={{ color: "#555", maxWidth: 420, margin: "1rem auto" }}>
          We couldn&apos;t complete this request right now.
          <br />
          Reference ID: <code>{reference}</code>
        </p>
        <button type="button" onClick={() => reset()} style={{ padding: "0.5rem 1rem" }}>
          Try again
        </button>
      </body>
    </html>
  );
}
