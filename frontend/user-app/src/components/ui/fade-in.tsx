import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface FadeInProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  /** 延迟（秒） */
  delay?: number;
  /** y 位移（px），默认 8 */
  y?: number;
  className?: string;
}

/** 淡入上移动画，受 useReducedMotion 控制。 */
export function FadeIn({ children, delay = 0, y = 8, className, ...rest }: FadeInProps) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y }}
      animate={reduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay, ease: [0.22, 1, 0.36, 1] }}
      className={cn(className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
