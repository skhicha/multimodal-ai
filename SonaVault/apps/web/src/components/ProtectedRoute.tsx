import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { getAccessToken } from "@/lib/api";
import { bootstrapSession } from "@/lib/session";

export default function ProtectedRoute() {
  const [status, setStatus] = useState<"checking" | "authed" | "anon">(
    getAccessToken() ? "authed" : "checking"
  );

  useEffect(() => {
    if (status !== "checking") return;
    bootstrapSession().then((ok) => setStatus(ok ? "authed" : "anon"));
  }, [status]);

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-tide-500 border-t-transparent" />
      </div>
    );
  }

  if (status === "anon") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
