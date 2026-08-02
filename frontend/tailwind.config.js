/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Space Grotesk Variable"', '"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#eef4ff',
          100: '#dae5ff',
          200: '#bdd1ff',
          300: '#92b4ff',
          400: '#6593ff',
          500: '#3f72ff',
          600: '#2a55f5',
          700: '#2244dc',
          800: '#1f3ab1',
          900: '#1d348c',
          950: '#161f5a',
        },
        accent: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
        },
        dark: {
          50: '#f8f9fa',
          100: '#f1f3f5',
          200: '#e9ecef',
          300: '#dee2e6',
          400: '#ced4da',
          500: '#adb5bd',
          600: '#868e96',
          700: '#495057',
          800: '#343a40',
          900: '#1a1b22',
          950: '#0a0a0f',
        },
        // Violet de liaison entre le bleu et l'orange de la marque: c'est lui
        // qui tient le dégradé signature sans virer au « gamer RGB ».
        iris: {
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
        },
        // ÉCHELLE DE SURFACES. La profondeur d'une interface sombre premium ne
        // vient pas des ombres (invisibles sur du noir) mais de l'empilement de
        // valeurs très proches, chacune soulignée d'un filet clair en haut.
        surface: {
          canvas: '#07070b',
          base: '#0b0c12',
          raised: '#101219',
          overlay: '#161822',
          hover: '#1c1f2b',
        },
      },
      borderRadius: {
        '4xl': '1.75rem',
        '5xl': '2.25rem',
      },
      fontSize: {
        // Échelle fluide: les titres respirent sur desktop sans casser le
        // mobile, et sans une seule media query.
        display: ['clamp(2.25rem, 1.2rem + 3.4vw, 3.75rem)',
                  { lineHeight: '1.02', letterSpacing: '-0.035em' }],
        title: ['clamp(1.5rem, 1.1rem + 1.6vw, 2.25rem)',
                { lineHeight: '1.1', letterSpacing: '-0.025em' }],
        heading: ['clamp(1.125rem, 1rem + 0.6vw, 1.375rem)',
                  { lineHeight: '1.25', letterSpacing: '-0.015em' }],
        overline: ['0.6875rem', { lineHeight: '1', letterSpacing: '0.18em' }],
      },
      transitionTimingFunction: {
        premium: 'cubic-bezier(0.22, 1, 0.36, 1)',
        snap: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      backgroundImage: {
        'grid-fade':
          'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(63,114,255,0.15), transparent), linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
        'brand-sweep': 'linear-gradient(120deg, #3f72ff 0%, #7c3aed 46%, #f97316 100%)',
        'sheen': 'linear-gradient(110deg, transparent 32%, rgba(255,255,255,0.22) 50%, transparent 68%)',
      },
      backgroundSize: {
        'grid-32': '32px 32px',
      },
      boxShadow: {
        'glow-primary': '0 0 0 1px rgba(63,114,255,0.4), 0 12px 40px -8px rgba(63,114,255,0.6)',
        'glow-accent': '0 0 0 1px rgba(249,115,22,0.4), 0 12px 40px -8px rgba(249,115,22,0.6)',
        'card-premium': '0 30px 60px -20px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.05)',
        // Élévations: ombre portée large et douce + filet clair intérieur en
        // haut, qui simule une source lumineuse zénithale.
        e1: '0 1px 0 0 rgba(255,255,255,0.05) inset, 0 1px 2px rgba(0,0,0,0.4)',
        e2: '0 1px 0 0 rgba(255,255,255,0.06) inset, 0 8px 24px -12px rgba(0,0,0,0.8)',
        e3: '0 1px 0 0 rgba(255,255,255,0.07) inset, 0 24px 60px -24px rgba(0,0,0,0.9)',
        e4: '0 1px 0 0 rgba(255,255,255,0.08) inset, 0 40px 90px -30px rgba(0,0,0,0.95)',
      },
      animation: {
        'float-slow': 'float 12s ease-in-out infinite',
        'float-slower': 'float 18s ease-in-out infinite',
        'shimmer': 'shimmer 2.4s linear infinite',
        'gradient-x': 'gradient-x 8s ease infinite',
        'marquee': 'marquee 38s linear infinite',
        'pulse-soft': 'pulse-soft 3.5s ease-in-out infinite',
        'orbit': 'orbit 2.4s linear infinite',
        'rise-in': 'rise-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0) translateX(0)' },
          '50%': { transform: 'translateY(-30px) translateX(20px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'gradient-x': {
          '0%, 100%': { 'background-position': '0% 50%' },
          '50%': { 'background-position': '100% 50%' },
        },
        marquee: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '0.8' },
          '50%': { opacity: '1' },
        },
        orbit: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'rise-in': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
    },
  },
  plugins: [],
}
