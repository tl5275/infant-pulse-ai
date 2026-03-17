/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./hooks/**/*.{js,jsx}",
    "./services/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#123247",
        slate: "#5B7384",
        mist: "#EAF1F4",
        surface: "#F6FAFC",
        stable: "#2E8B57",
        warning: "#D9A441",
        critical: "#C74C4C",
        accent: "#2A6F97"
      },
      boxShadow: {
        panel: "0 18px 45px rgba(15, 44, 63, 0.08)",
        glass: "0 12px 30px rgba(19, 57, 78, 0.12)"
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(18, 50, 71, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(18, 50, 71, 0.05) 1px, transparent 1px)"
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.9" },
          "50%": { transform: "scale(1.04)", opacity: "1" }
        },
        slideUp: {
          "0%": { transform: "translateY(18px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" }
        }
      },
      animation: {
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        "slide-up": "slideUp 0.45s ease-out"
      }
    }
  },
  plugins: []
};