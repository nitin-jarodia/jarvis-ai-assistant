/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: "#070a12",
          surface: "#0c1222",
          elevated: "#111a2e",
          border: "rgba(148, 163, 184, 0.12)",
          "border-strong": "rgba(148, 163, 184, 0.18)",
          muted: "#94a3b8",
          fg: "#f1f5f9",
          accent: "#38bdf8",
          violet: "#a78bfa",
          amber: "#fbbf24",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Inter", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(148, 163, 184, 0.08), 0 24px 80px rgba(0, 0, 0, 0.45)",
        "glow-sm": "0 0 0 1px rgba(56, 189, 248, 0.15), 0 12px 40px rgba(0, 0, 0, 0.35)",
      },
      backgroundImage: {
        "mesh-gradient":
          "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(56, 189, 248, 0.18), transparent 50%), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(167, 139, 250, 0.14), transparent 45%), radial-gradient(ellipse 50% 30% at 50% 100%, rgba(251, 191, 36, 0.08), transparent 50%)",
        "card-shine":
          "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 45%, transparent 100%)",
      },
      animation: {
        "fade-in": "fadeIn 0.35s ease-out forwards",
        shimmer: "shimmer 1.2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%, 100%": { opacity: "0.45" },
          "50%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
