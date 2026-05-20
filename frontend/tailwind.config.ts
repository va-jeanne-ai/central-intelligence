import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",

        // Brand accent — Central Intelligence indigo
        brand: {
          DEFAULT: "#6366F1",
          light: "#A5B4FC",
          dark: "#4F46E5",
        },

        // Department palette
        marketing: {
          DEFAULT: "#10B981",
          50: "#ECFDF5",
          100: "#D1FAE5",
          500: "#10B981",
          600: "#059669",
        },
        sales: {
          DEFAULT: "#3B82F6",
          50: "#EFF6FF",
          100: "#DBEAFE",
          500: "#3B82F6",
          600: "#2563EB",
        },
        fulfillment: {
          DEFAULT: "#F97316",
          50: "#FFF7ED",
          100: "#FFEDD5",
          500: "#F97316",
          600: "#EA580C",
        },
      },

      width: {
        sidebar: "228px",
      },

      height: {
        header: "60px",
      },

      borderWidth: {
        "3": "3px",
      },
    },
  },
  plugins: [],
};

export default config;
