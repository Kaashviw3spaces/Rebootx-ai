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
        background: '#09090D',
        sidebar: '#0B0B0F',
        card: '#111116',
        elevated: '#17171F',
        border: '#27272F',
        primary: {
          DEFAULT: '#8B5CF6',
          violet: '#8B5CF6',
          purple: '#A020F0',
          pink: '#E040C9',
        },
        status: {
          green: '#10B981',
          amber: '#F59E0B',
          red: '#EF4444',
        },
        text: {
          primary: '#F5F5F7',
          secondary: '#A1A1AA',
          muted: '#71717A',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'glow-purple': '0 0 25px -5px rgba(139, 92, 246, 0.15)',
        'glow-pink': '0 0 25px -5px rgba(224, 64, 201, 0.15)',
        'card': '0 4px 20px -2px rgba(0, 0, 0, 0.5)',
      }
    },
  },
  plugins: [],
}

