/**
 * Atom: Button
 *
 * Primary (accent bg) and ghost (outline) button variants.
 * Matches mockup's .btn, .btn-primary, .btn-ghost.
 */

import Link from "next/link";

type ButtonVariant = "primary" | "ghost" | "danger";

interface ButtonBaseProps {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  fullWidth?: boolean;
  children: React.ReactNode;
  className?: string;
}

interface ButtonAsButtonProps extends ButtonBaseProps, Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, keyof ButtonBaseProps> {
  href?: never;
}

interface ButtonAsLinkProps extends ButtonBaseProps {
  href: string;
}

type ButtonProps = ButtonAsButtonProps | ButtonAsLinkProps;

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-accent-500 hover:bg-accent-600 text-white border-transparent",
  ghost: "bg-transparent hover:bg-gray-100 text-gray-700 border-gray-200",
  danger: "bg-red-500 hover:bg-red-600 text-white border-transparent",
};

const SIZE_CLASSES: Record<string, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-[13px]",
};

export function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const classes = `inline-flex items-center justify-center gap-1.5 font-semibold rounded-md border transition-all duration-150 hover:-translate-y-px active:translate-y-0 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${fullWidth ? "w-full" : ""} ${className}`;

  if ("href" in rest && rest.href) {
    return (
      <Link href={rest.href} className={classes}>
        {children}
      </Link>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { href: _, ...buttonRest } = rest as ButtonAsButtonProps;
  return (
    <button type="button" className={classes} {...buttonRest}>
      {children}
    </button>
  );
}

/**
 * Atom: CopyButton
 *
 * Small accent copy button matching mockup's .copy-btn.
 */
export function CopyButton({
  text,
  label = "Copy",
  className = "",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  function handleCopy() {
    void navigator.clipboard.writeText(text);
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`px-2.5 py-1 text-[11px] font-semibold rounded bg-accent-500 text-white hover:bg-accent-600 transition-colors ${className}`}
    >
      {label}
    </button>
  );
}
