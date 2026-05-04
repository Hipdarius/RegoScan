"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useTheme } from "./ThemeProvider";

const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Console" },
  { href: "/about", label: "About" },
  { href: "/architecture", label: "Architecture" },
  { href: "/methods", label: "Methods" },
];

/**
 * Thin top-left nav strip. Shares colors with the Hero/console aesthetic
 * so it doesn't disrupt the existing landing layout — it sits above the
 * Hero on every page and just provides routing between sections.
 */
export function NavBar() {
  const { theme } = useTheme();
  const pathname = usePathname() ?? "/";
  const isLight = theme === "light";

  const muted = isLight ? "#475569" : "#94a3b8";
  const fg = isLight ? "#0f172a" : "#e2e8f0";
  const cyan = isLight ? "#0284c7" : "#38bdf8";
  const dim = isLight ? "#94a3b8" : "#64748b";
  const borderCol = isLight ? "#e2e8f0" : "#1e293b";

  return (
    <nav
      className="border-b px-6"
      style={{ borderColor: borderCol }}
      aria-label="Primary"
    >
      <ul className="mx-auto flex max-w-6xl items-center gap-6 py-2 font-mono text-[10px] uppercase tracking-[0.25em]">
        <li className="mr-2 inline-flex items-center gap-2" style={{ color: dim }}>
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: cyan }}
            aria-hidden="true"
          />
          VERA
        </li>
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className="inline-block py-1 transition-colors hover:opacity-80"
                style={{
                  color: active ? fg : muted,
                  borderBottom: active
                    ? `1px solid ${cyan}`
                    : "1px solid transparent",
                }}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
