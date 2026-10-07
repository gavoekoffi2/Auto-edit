import { motion, useReducedMotion } from 'framer-motion'

/**
 * Transition d'entrée d'un écran connecté.
 *
 * Volontairement discrète — 10 px et 320 ms. Une page qui glisse de 60 px ou
 * qui se met à l'échelle donne l'impression d'un site vitrine; un outil doit
 * simplement « arriver ». Respecte `prefers-reduced-motion`, où il ne reste
 * qu'un fondu.
 */
export default function PageTransition({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}
