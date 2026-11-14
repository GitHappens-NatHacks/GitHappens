interface BrandLogoProps {
  className?: string;
}

export function BrandLogo({ className = "h-12 w-12" }: BrandLogoProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect width="64" height="64" rx="16" fill="#014A35" />
      <circle cx="32" cy="32" r="21" stroke="#E3EFE9" strokeWidth="2.5" strokeDasharray="5 4" />
      <circle cx="32" cy="32" r="13" stroke="#FFFFFF" strokeWidth="3" />
      <path d="M32 7V16M32 48V57M7 32H16M48 32H57" stroke="#E3EFE9" strokeWidth="3" strokeLinecap="round" />
      <circle cx="32" cy="32" r="5" fill="#FAF7F0" stroke="#013828" strokeWidth="2" />
    </svg>
  );
}
