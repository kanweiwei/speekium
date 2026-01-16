interface SpeekiumIconProps {
  className?: string;
  size?: number;
  animated?: boolean;
}

/**
 * Speekium brand icon - microphone with sound waves
 * Represents intelligent voice assistant with brand identity
 */
export function SpeekiumIcon({ className, size = 80, animated = true }: SpeekiumIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Main gradient - blue to purple */}
        <linearGradient id="speekium-main-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#9333EA" />
        </linearGradient>

        {/* Accent gradient - cyan to blue for sound waves */}
        <linearGradient id="speekium-accent-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#06B6D4" />
          <stop offset="100%" stopColor="#3B82F6" />
        </linearGradient>

        {/* Glow filter */}
        <filter id="speekium-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Background rounded square */}
      <rect x="4" y="4" width="72" height="72" rx="20" fill="url(#speekium-main-grad)" />

      {/* Microphone body - rounded capsule */}
      <rect x="32" y="24" width="16" height="28" rx="8" fill="white" />

      {/* Microphone base */}
      <path
        d="M28 48 L52 48 L52 52 C52 56 48 58 40 58 C32 58 28 56 28 52 Z"
        fill="white"
      />

      {/* Microphone stand */}
      <path
        d="M38 58 L38 62 M42 58 L42 62"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Sound waves on the right - emanating from mic */}
      <g className={animated ? 'animate-pulse' : ''} style={{ animationDuration: '2s' }}>
        {/* Inner wave */}
        <path
          d="M56 32 Q62 40 56 48"
          fill="none"
          stroke="url(#speekium-accent-grad)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.95"
        />

        {/* Outer wave */}
        <path
          d="M60 28 Q68 40 60 52"
          fill="none"
          stroke="url(#speekium-accent-grad)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.7"
        />
      </g>
    </svg>
  );
}
