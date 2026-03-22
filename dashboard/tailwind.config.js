/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        mira: {
          50: '#f0f0ff',
          100: '#e0e0ff',
          200: '#c4c4ff',
          300: '#9e9eff',
          400: '#7c6cff',
          500: '#6B4EFF',
          600: '#5a3de6',
          700: '#4a2dc2',
          800: '#3d259e',
          900: '#342181',
        },
      },
    },
  },
  plugins: [],
}
