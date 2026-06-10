import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes with conflict resolution + truthy filtering.
 * Prefer `cn()` over string concatenation for any non-trivial className.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
