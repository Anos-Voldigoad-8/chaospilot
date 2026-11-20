interface ShinyTextProps {
  text: string;
  disabled?: boolean;
  speed?: number;
  className?: string;
  textColor?: string;
  shineColor?: string;
}

export function ShinyText({
  text,
  disabled = false,
  speed = 4,
  className = "",
  textColor = "#1E222B",
  shineColor = "#6366F1",
}: ShinyTextProps) {
  const animationDuration = `${speed}s`;

  return (
    <span
      className={`inline-block font-mono tracking-wider ${className}`}
      style={{
        backgroundImage: disabled
          ? "none"
          : `linear-gradient(120deg, ${textColor} 0%, ${textColor} 35%, ${shineColor} 50%, ${textColor} 65%, ${textColor} 100%)`,
        backgroundSize: "200% 100%",
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        color: disabled ? textColor : "transparent",
        animation: disabled ? "none" : `shiny-sweep ${animationDuration} ease-in-out infinite`,
      }}
    >
      {text}
    </span>
  );
}
