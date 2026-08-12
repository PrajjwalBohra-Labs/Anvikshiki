export const fadeInUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.25, ease: "easeOut" },
}

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
}

export const staggerContainer = {
  animate: { transition: { staggerChildren: 0.05 } },
}

export const listItem = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0 },
}
