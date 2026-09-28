"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

function getStored(): "light" | "dark" | null {
  try {
    const value = localStorage.getItem("talent-theme");
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    // Reads localStorage only after mount, on purpose — this "use client" component is still
    // server-rendered for the first paint (where localStorage doesn't exist), so bridging it in
    // via useState's initializer would produce a server/client hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(getStored());
  }, []);

  function toggle() {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = theme ?? (prefersDark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("talent-theme", next);
    } catch {
      // Private window / blocked storage — the toggle still works for this page view.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="تبديل الوضع الليلي"
      className="flex size-10 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
    >
      {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
    </button>
  );
}
