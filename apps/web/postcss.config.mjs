// Tailwind v4 is CSS-first: a single PostCSS plugin, no tailwind.config.js.
// Theme tokens and content scanning are declared in src/app/globals.css
// (@import "tailwindcss" + @theme) — see docs/architecture.md.
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
