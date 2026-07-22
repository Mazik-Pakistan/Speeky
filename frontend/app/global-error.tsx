"use client";

import * as React from "react";

/**
 * Only fires if the root layout itself throws (Providers, fonts, etc.) —
 * a much rarer case than app/error.tsx, but without this one, a crash that
 * high up would bypass React entirely and show the browser's default error
 * page with no styling and no way back into the app.
 */
export default function GlobalRootErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          display: "flex",
          minHeight: "100vh",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          fontFamily: "system-ui, sans-serif",
          textAlign: "center",
          padding: "1.5rem",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600 }}>Something went wrong</h1>
        <p style={{ maxWidth: "24rem", color: "#64748B" }}>
          An unexpected error occurred while loading Speeky. Please try again.
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            borderRadius: "0.75rem",
            backgroundColor: "#00246E",
            color: "#fff",
            padding: "0.5rem 1.25rem",
            fontSize: "0.875rem",
            fontWeight: 500,
            border: "none",
            cursor: "pointer",
          }}
        >
          Try Again
        </button>
      </body>
    </html>
  );
}
