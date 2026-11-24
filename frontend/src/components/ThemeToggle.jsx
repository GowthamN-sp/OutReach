import { useState } from "react";
import { Sun, Moon } from "lucide-react";
export default function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "dark",
  );
  const dark = theme === "dark";
  function toggle() {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]').content = dark
      ? "#f5f6fb"
      : "#10121a";
    try {
      localStorage.setItem("outreachdesk.theme", next);
    } catch {
      /* Private browsing can disable storage. */
    }
    setTheme(next);
  }
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label="Dark mode"
      aria-pressed={dark}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
    >
      {dark ? <Sun size={17} /> : <Moon size={17} />}
      <span>{dark ? "Light mode" : "Dark mode"}</span>
    </button>
  );
}
