"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/* =============================================================
   SmoothScroll — momentum-based scroll engine. Replaces the
   default browser scroll with a physics-driven version that
   decelerates on a curve. Fires native scroll events so the
   MarginNav scroll-spy and IntersectionObservers still work.
   Bypassed entirely for prefers-reduced-motion users.
   ============================================================= */
export function SmoothScroll() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const lenis = new Lenis({
      duration: 1.05,
      // ease-out-expo — lands gently at zero velocity
      easing: (t: number) =>
        t === 1 ? 1 : 1 - Math.pow(2, -10 * t),
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 2,
      anchors: true,
    });

    let raf = 0;
    const frame = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, []);

  return null;
}
