import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-bold transition-colors duration-180 ease-out focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-ring focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-55",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-brand-strong",
        secondary:
          "border border-line-strong bg-card text-ink hover:border-slate-400 hover:bg-page",
        success: "bg-green-600 text-white hover:bg-green-700",
        ghost: "bg-transparent text-ink hover:bg-slate-100",
        danger: "bg-red-600 text-white hover:bg-red-700",
      },
      size: {
        sm: "min-h-9 px-3 text-sm",
        md: "min-h-10 px-3.5",
        lg: "min-h-11 px-5 text-base",
        icon: "min-h-10 min-w-10 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export { buttonVariants };
