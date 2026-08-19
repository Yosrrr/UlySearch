// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Palette "flotte industrielle" — navy + ambre, pas l'indigo générique
        ink: {
          950: "#0F1A2B",
          900: "#16243A",
          800: "#1E2F49", // navy principal (sidebar, boutons)
          700: "#2A3F5F",
          600: "#3C567B",
        },
        slate: {
          50: "#F6F7F9",
          100: "#EEF1F4",
          200: "#DDE2E8",
          400: "#8993A3",
          600: "#5B6472",
        },
        amber: {
          500: "#E8873A", // accent alerte instantanée (score > 70%)
          600: "#C96F27",
        },
        teal: {
          500: "#2F8F7C", // acheteur connu / positif
          600: "#22705F",
        },
        rose: {
          500: "#C74B4B", // erreurs, urgence, hors-secteur
        },
      },
      fontFamily: {
        display: ["\"Space Grotesk\"", "sans-serif"],
        sans: ["\"IBM Plex Sans\"", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "monospace"],
      },
    },
  },
  plugins: [],
};