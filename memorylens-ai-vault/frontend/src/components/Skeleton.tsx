import type { CSSProperties } from "react";
import "./Skeleton.css";

export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <div className={`skeleton ${className}`} style={style} />;
}

export function MediaCardSkeleton() {
  return (
    <div className="skeleton-card">
      <Skeleton className="skeleton-card-thumb" />
      <div className="skeleton-card-body">
        <Skeleton className="skeleton-line" style={{ width: "70%" }} />
        <Skeleton className="skeleton-line" style={{ width: "40%" }} />
      </div>
    </div>
  );
}

export function LibrarySkeletonGrid({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cards">
      {Array.from({ length: count }).map((_, i) => (
        <MediaCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function StatTileSkeleton() {
  return (
    <div className="glass-card skeleton-tile">
      <Skeleton className="skeleton-line" style={{ width: 60, height: 22 }} />
      <Skeleton className="skeleton-line" style={{ width: "55%" }} />
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div>
      {Array.from({ length: rows }).map((_, r) => (
        <div className="skeleton-table-row" key={r}>
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="skeleton-line" style={{ width: c === 0 ? "22%" : "14%" }} />
          ))}
        </div>
      ))}
    </div>
  );
}
