/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        abyss: {
          950: "#030712",
          900: "#0a1120",
          800: "#0f1b30",
          700: "#16263f",
        },
        tide: {
          500: "#2dd4bf",
          400: "#5eead4",
          300: "#99f6e4",
        },
        signal: {
          amber: "#f59e0b",
          coral: "#fb7185",
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      backgroundImage: {
        "sonar-grid":
          "radial-gradient(circle at 50% 0%, rgba(45,212,191,0.12), transparent 60%)",
      },
      keyframes: {
        "sonar-ping": {
          "0%": { transform: "scale(0.6)", opacity: "0.8" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        "waveform-pulse": {
          "0%, 100%": { transform: "scaleY(0.3)" },
          "50%": { transform: "scaleY(1)" },
        },
      },
      animation: {
        "sonar-ping": "sonar-ping 2.4s ease-out infinite",
        "waveform-pulse": "waveform-pulse 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
