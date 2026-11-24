/** Animated hydrophone "ping" backdrop — ambient brand motion, not decoration
 * for its own sake: signals SonaVault's acoustic domain on every auth screen. */
export default function SonarBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden bg-sonar-grid">
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{ animationDelay: `${i * 0.8}s` }}
            className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2
                       rounded-full border border-tide-400/40 animate-sonar-ping"
          />
        ))}
      </div>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-abyss-950/60 to-abyss-950" />
    </div>
  );
}
