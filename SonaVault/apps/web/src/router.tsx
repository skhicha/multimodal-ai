import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import AccountSecurityPage from "@/features/account-security/AccountSecurityPage";
import LoginPage from "@/features/auth/LoginPage";
import RegisterPage from "@/features/auth/RegisterPage";
import DashboardPage from "@/features/dashboard-map/DashboardPage";
import MfaChallengePage from "@/features/mfa/MfaChallengePage";

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/mfa" element={<MfaChallengePage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/settings/security" element={<AccountSecurityPage />} />
      </Route>

      {/* TODO: /streams, /vault, /search, /briefings, /jobs, /provenance,
          /admin/* — added slice-by-slice per the frontend blueprint in docs/. */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
