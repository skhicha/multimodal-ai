import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

export function ProtectedRoute({
  children,
  requireAdmin = false,
  blockRoles = [],
  requirePermission,
}: {
  children: ReactNode;
  requireAdmin?: boolean;
  blockRoles?: string[];
  /** Authoritative permission check. When given, takes precedence over
   * blockRoles once permissions have loaded; blockRoles stays as a
   * first-line fallback for the render before that fetch resolves. */
  requirePermission?: string;
}) {
  const { user, loading, permissions, hasPermission } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="empty-state">Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (requireAdmin && user.role !== "admin") {
    return <Navigate to="/library" replace />;
  }

  if (blockRoles.includes(user.role)) {
    return <Navigate to="/library" replace />;
  }

  if (requirePermission && permissions.length > 0 && !hasPermission(requirePermission)) {
    return <Navigate to="/library" replace />;
  }

  return <>{children}</>;
}
