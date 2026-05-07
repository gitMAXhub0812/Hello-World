import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#1a1a2e", light: "#16213e" },
      },
    },
  },
  plugins: [],
} satisfies Config;
