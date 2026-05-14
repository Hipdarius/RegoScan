"use client";

import { motion, useReducedMotion, useScroll, useSpring } from "framer-motion";

/* =============================================================
   ScrollProgress — 1px cyan beam pinned to the top of the
   viewport, tracking document scroll progress. Reads as an
   oscilloscope sweep: the further you scroll, the further the
   beam has traveled. Spring-smoothed so the line doesn't twitch
   on small scrolls.
   ============================================================= */
export function ScrollProgress() {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 220,
    damping: 30,
    mass: 0.4,
    restDelta: 0.001,
  });

  if (reduce) return null;

  return (
    <motion.div
      aria-hidden="true"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 1,
        transformOrigin: "0% 50%",
        scaleX,
        background: "#38bdf8",
        zIndex: 100,
        pointerEvents: "none",
      }}
    />
  );
}
