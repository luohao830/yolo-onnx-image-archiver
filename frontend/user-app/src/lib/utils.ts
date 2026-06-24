import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind class，解决冲突并支持条件类名。 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
