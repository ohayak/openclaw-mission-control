import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "icon" ? (
      <span
        className={cn(
          "font-bold text-lg leading-none select-none",
          className,
        )}
        aria-label="Mission Control"
      >
        MC
      </span>
    ) : variant === "responsive" ? (
      <>
        <span
          className={cn(
            "font-bold text-lg leading-none select-none group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          Mission Control
        </span>
        <span
          className={cn(
            "font-bold text-lg leading-none select-none hidden group-data-[collapsible=icon]:block",
            className,
          )}
          aria-label="Mission Control"
        >
          MC
        </span>
      </>
    ) : (
      <span
        className={cn("font-bold text-lg leading-none select-none", className)}
      >
        Mission Control
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
