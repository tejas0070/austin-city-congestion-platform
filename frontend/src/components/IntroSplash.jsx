import { useEffect, useRef, useState } from 'react';
import { SpiralAnimation } from './ui/spiral-animation';

const EXIT_MS = 600;
// How long to wait before fading the Enter control in, letting the spiral form.
const REVEAL_MS = 2000;

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/**
 * Full-screen entry curtain: a GSAP spiral particle field over black, with an
 * "Enter" control that hands off to the dashboard. Reduced-motion users skip the
 * animation and get the control immediately on a still black field.
 *
 * @param {{ onEnter: () => void }} props
 */
export default function IntroSplash({ onEnter }) {
  const reduceMotion = prefersReducedMotion();
  const [leaving, setLeaving] = useState(false);
  const [revealed, setRevealed] = useState(reduceMotion);
  const timerRef = useRef(null);

  // Fade the Enter control in once the spiral has had time to form.
  useEffect(() => {
    if (reduceMotion) return undefined;
    const id = setTimeout(() => setRevealed(true), REVEAL_MS);
    return () => clearTimeout(id);
  }, [reduceMotion]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const handleEnter = () => {
    if (leaving) return;
    setLeaving(true);
    timerRef.current = setTimeout(onEnter, EXIT_MS);
  };

  return (
    <div
      className={`fixed inset-0 z-50 overflow-hidden bg-black transition-opacity duration-500 ease-out ${
        leaving ? 'opacity-0' : 'opacity-100'
      }`}
    >
      <h1 className="sr-only">Austin Traffic Intelligence</h1>

      {/* Spiral particle field. Skipped for reduced-motion users. */}
      {!reduceMotion && (
        <div className="absolute inset-0">
          <SpiralAnimation />
        </div>
      )}

      {/* Wordmark — upper third, large and lavender so it reads clearly over
          the black spiral while leaving the center vortex unobscured. */}
      <div
        className={`absolute left-1/2 top-[26%] z-10 w-[min(92vw,920px)] -translate-x-1/2 px-4 text-center transition-all duration-1000 ease-out ${
          revealed ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
        }`}
      >
        <p className="font-['Orbitron'] text-2xl font-semibold uppercase leading-tight tracking-[0.14em] text-[#b9abe6] sm:text-4xl sm:tracking-[0.22em]">
          Austin Traffic Intelligence
        </p>
      </div>

      {/* Enter control — centered. */}
      <div
        className={`absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 transition-all duration-1000 ease-out ${
          revealed ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
        }`}
      >
        <button
          type="button"
          onClick={handleEnter}
          className="font-display text-2xl font-extralight uppercase tracking-[0.2em] text-white transition-all duration-700 hover:tracking-[0.3em] focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-4 focus-visible:ring-offset-black motion-safe:animate-pulse"
        >
          Enter
        </button>
      </div>
    </div>
  );
}
