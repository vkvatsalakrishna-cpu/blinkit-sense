import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        blinkit: {
          green: "#0c831f",
          "green-dark": "#0a6b19",
          yellow: "#f8cb46",
          cream: "#f7f4eb",
        },
      },
      fontFamily: {
        caveat: ["var(--font-caveat)", "cursive"],
      },
    },
  },
  plugins: [],
};

export default config;
