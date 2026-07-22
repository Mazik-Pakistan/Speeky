"use client";

import * as React from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = React.createContext<ThemeContextType | undefined>(
  undefined,
);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = React.useState<Theme>("light");

  // The blocking <script> in app/layout.tsx already set the `dark` class
  // before first paint (no flash). This just syncs React state to match —
  // useLayoutEffect (not useEffect) so it runs before the browser paints,
  // and starting both server/client renders at "light" avoids a hydration
  // mismatch on anything (e.g. ThemeToggle's icon) that reads `theme`.
  React.useLayoutEffect(() => {
    if (document.documentElement.classList.contains("dark")) setTheme("dark");
  }, []);

  const toggleTheme = React.useCallback(() => {
    setTheme((prev) => {
      const nextTheme = prev === "light" ? "dark" : "light";
      window.localStorage.setItem("speeky-theme", nextTheme);
      document.documentElement.classList.toggle("dark", nextTheme === "dark");
      return nextTheme;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = React.useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
