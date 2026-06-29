/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      // "Violet Crown" — warm limestone surfaces, warm-ink text, and a single
      // dusk-violet accent (Austin's "City of the Violet Crown"). No generic
      // blue. Signal colors mirror the map's congestion ramp exactly so the
      // legend always matches what's drawn on the map.
      colors: {
        paper: '#ECE9E2', // warm limestone — app base
        surface: '#F8F6F1', // floating panel
        'surface-hi': '#FFFFFF', // raised tile inside a panel
        ink: '#211F1B', // warm near-black text
        'ink-soft': '#6A655C', // secondary text
        'ink-faint': '#9A958B', // captions / tertiary
        stone: '#D9D4C9', // hairline border
        'stone-soft': '#E7E3DA', // subtle fill / hover
        violet: '#6B5B95', // dusk accent — active / focus / primary
        'violet-deep': '#564A7A', // accent hover
        'violet-tint': '#EAE5F1', // accent wash (active bg)
        // Signal ramp = map colors (congestion + severity legends).
        'signal-green': '#00C864',
        'signal-amber': '#FFC800',
        'signal-red': '#DC3232',
        // Darker signal inks for text/labels on light surfaces (AA contrast).
        'signal-green-ink': '#0C7A45',
        'signal-amber-ink': '#946A00',
        'signal-red-ink': '#B23633',
        // Kept for the dark map cold-start overlay only.
        'gray-850': '#1a1f2e',
        'gray-950': '#0d1117',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        float: '0 12px 40px -8px rgba(33, 31, 27, 0.28)',
      },
    },
  },
  plugins: [],
};
