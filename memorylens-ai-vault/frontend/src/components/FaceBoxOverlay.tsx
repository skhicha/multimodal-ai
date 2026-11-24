import type { FaceBox } from "../lib/api";

/**
 * Draws face bounding boxes over a rendered <img>/<video>, scaling the
 * pixel coordinates stored at full resolution down to whatever size the
 * element is actually displayed at.
 */
export function FaceBoxOverlay({
  faces,
  naturalWidth,
  naturalHeight,
}: {
  faces: FaceBox[];
  naturalWidth: number;
  naturalHeight: number;
}) {
  if (!naturalWidth || !naturalHeight || faces.length === 0) return null;

  return (
    <svg
      viewBox={`0 0 ${naturalWidth} ${naturalHeight}`}
      preserveAspectRatio="none"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    >
      {faces.map((f, i) => (
        <rect
          key={i}
          x={f.x}
          y={f.y}
          width={f.w}
          height={f.h}
          fill="none"
          stroke="#3ddc97"
          strokeWidth={Math.max(naturalWidth / 220, 2)}
          rx={4}
        />
      ))}
    </svg>
  );
}
