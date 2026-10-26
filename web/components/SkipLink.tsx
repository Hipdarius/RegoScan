"use client";

/**
 * Skip-to-content link — keyboard-accessibility a11y baseline.
 *
 * Hidden until focused (keyboard tab from the address bar). Lets screen-
 * reader and keyboard users bypass the NavBar on every doc page rather
 * than tabbing through the four nav items every time. Pairs with the
 * `id="main"` on the route's main wrapper.
 */
export function SkipLink() {
  return (
    <a
      href="#main"
      className="
        sr-only focus:not-sr-only
        focus:fixed focus:left-4 focus:top-4 focus:z-50
        focus:rounded-none focus:border focus:border-sky-500
        focus:bg-slate-900 focus:px-3 focus:py-2
        focus:font-mono focus:text-xs focus:uppercase focus:tracking-widest focus:text-sky-300
        focus:outline-none
      "
    >
      Skip to main content
    </a>
  );
}
