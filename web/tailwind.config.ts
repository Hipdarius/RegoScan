import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Brand tokens — mirror :root variables from globals.css and the
        // docs/brand-guide.md palette. Use as `bg-vera-amber`, `text-vera-teal`,
        // etc. Reserved for the V mark and brand surfaces.
        vera: {
          base: "#0a0d14",
          teal: "#38b3c4",
          amber: "#f5b840",
          moon: "#c8d3da",
          light: "#f0f5f8",
          dim: "#9bb5c2",
        },
      },
      fontFamily: {
        mono: [
          "var(--font-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
        display: [
          "var(--font-display)",
          "var(--font-mono)",
          "ui-monospace",
          "monospace",
        ],
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.2" },
        },
        "scan-line": {
          "0%":   { top: "0%",   opacity: "0" },
          "10%":  { opacity: "1" },
          "90%":  { opacity: "1" },
          "100%": { top: "100%", opacity: "0" },
        },
      },
      animation: {
        blink: "blink 1.6s ease-in-out infinite",
        "scan-line": "scan-line 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
