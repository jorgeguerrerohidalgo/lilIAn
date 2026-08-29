/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Trust & Authority Palette - Legal */
        // `primary` is a single brand color (`#1e3a8a`). Many components
        // reach for `primary-50` / `primary-600` / `primary-700` etc. —
        // those numeric shades didn't exist in the old config, so the
        // utilities silently did nothing and the buttons looked broken
        // (transparent background, only the white text visible). The
        // defaults below mirror Tailwind's blue ramp so the existing
        // class names resolve to real colors without renaming call sites.
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          DEFAULT: '#1e3a8a',
          light: '#1e40af',
        },
        secondary: '#1E40AF',
        accent: '#B45309',
        foreground: '#0F172A',
        background: '#F8FAFC',
        surface: '#FFFFFF',
        muted: '#E9EEF5',
        border: '#CBD5E1',
        ring: '#1E3A8A',
        destructive: '#DC2626',

        /* Semantic colors */
        success: {
          DEFAULT: '#059669',
          bg: '#D1FAE5',
        },
        warning: {
          DEFAULT: '#B45309',
          bg: '#FEF3C7',
        },
        error: {
          DEFAULT: '#DC2626',
          bg: '#FEE2E2',
        },
        info: {
          DEFAULT: '#1E40AF',
          bg: '#DBEAFE',
        },

        /* Legacy support */
        coral: {
          DEFAULT: '#DC2626',
          dark: '#B91C1C',
          pale: '#FEE2E2',
        },
        cream: '#FAFAFA',
        soft: '#F1F5F9',
        soft2: '#E9EEF5',
        ink: '#0F172A',
        ink2: '#334155',
        amber: {
          DEFAULT: '#B45309',
          pale: '#FEF3C7',
        },
        green: {
          DEFAULT: '#059669',
          pale: '#D1FAE5',
        },
        blue: {
          DEFAULT: '#1E40AF',
          pale: '#DBEAFE',
        },
        purple: {
          DEFAULT: '#7C3AED',
          pale: '#EDE9FE',
        },
      },
      fontFamily: {
        heading: ['Barlow', 'system-ui', 'sans-serif'],
        body: ['Barlow', 'system-ui', 'sans-serif'],
        mono: ['Roboto Mono', 'monospace'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '18px',
        xl: '22px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(15, 23, 42, 0.05)',
        DEFAULT: '0 8px 24px rgba(15, 23, 42, 0.07)',
        md: '0 4px 12px rgba(15, 23, 42, 0.08)',
        lg: '0 18px 48px rgba(15, 23, 42, 0.10)',
        xl: '-8px 0 32px rgba(15, 23, 42, 0.1)',
        fab: '0 8px 24px rgba(180, 83, 9, 0.35)',
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      animation: {
        'shimmer': 'shimmer 1.5s infinite',
        'slide-in': 'slideIn 0.25s ease-out',
        'slide-out': 'slideOut 0.25s ease-out',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        slideOut: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
};
