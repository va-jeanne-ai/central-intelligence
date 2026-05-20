/**
 * Atom: PlatformTag
 *
 * Small colored pill for social platforms (Instagram, Facebook, LinkedIn, TikTok).
 * Matches mockup's .platform-tag with .tag-instagram, .tag-facebook.
 */

type Platform = "instagram" | "facebook" | "linkedin" | "tiktok";

interface PlatformTagProps {
  platform: Platform;
  short?: boolean;
  className?: string;
}

const PLATFORM_CONFIG: Record<Platform, { bg: string; label: string; short: string }> = {
  instagram: { bg: "#C13584", label: "Instagram", short: "IG" },
  facebook: { bg: "#1877F2", label: "Facebook", short: "FB" },
  linkedin: { bg: "#0A66C2", label: "LinkedIn", short: "LI" },
  tiktok: { bg: "#111827", label: "TikTok", short: "TT" },
};

export function PlatformTag({ platform, short = false, className = "" }: PlatformTagProps) {
  const config = PLATFORM_CONFIG[platform];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold text-white ${className}`}
      style={{ backgroundColor: config.bg }}
    >
      {short ? config.short : config.label}
    </span>
  );
}
