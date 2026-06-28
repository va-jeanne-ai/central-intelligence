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

        // Accent — the app's themeable accent. Resolves through CSS vars in
        // globals.css (currently the mockup's gold/amber). A former indigo-N
        // utility migrates to accent-N at the same weight. Re-theme = edit the
        // --accent-* vars only.
        accent: {
          50: "var(--accent-50)",
          100: "var(--accent-100)",
          200: "var(--accent-200)",
          300: "var(--accent-300)",
          400: "var(--accent-400)",
          500: "var(--accent-500)",
          600: "var(--accent-600)",
          700: "var(--accent-700)",
          800: "var(--accent-800)",
          900: "var(--accent-900)",
          DEFAULT: "var(--accent-500)",
        },

        // Brand — back-compat alias of the accent scale.
        brand: {
          DEFAULT: "var(--brand)",
          light: "var(--brand-light)",
          dark: "var(--brand-dark)",
        },

        // Sidebar — dark themeable palette (mockup .sidebar). Resolves through
        // the --sidebar-* CSS vars so the whole sidebar re-themes from one place.
        sidebar: {
          bg: "var(--sidebar-bg)",
          hover: "var(--sidebar-hover)",
          border: "var(--sidebar-border)",
          text: "var(--sidebar-text)",
          "text-hover": "var(--sidebar-text-hover)",
          heading: "var(--sidebar-heading)",
          "active-bg": "var(--sidebar-active-bg)",
          "active-text": "var(--sidebar-active-text)",
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
