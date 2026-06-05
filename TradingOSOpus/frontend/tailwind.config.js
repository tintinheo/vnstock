/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: { 50:'#eef2ff',500:'#6366f1',600:'#4f46e5',700:'#4338ca',900:'#312e81' },
        surface: { 800:'#1e1e2e',900:'#11111b',700:'#2a2a3c' },
        buy: '#22c55e', sell: '#ef4444', hold: '#f59e0b',
      },
    },
  },
  plugins: [],
};