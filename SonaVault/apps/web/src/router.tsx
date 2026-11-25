import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import AccountSecurityPage from "@/features/account-security/AccountSecurityPage";
import AdminConsolePage from "@/features/admin/AdminConsolePage";
import AudioWorkbenchPage from "@/features/asset-workbench/AudioWorkbenchPage";
import LoginPage from "@/features/auth/LoginPage";
import RegisterPage from "@/features/auth/RegisterPage";
import BriefingsPage from "@/features/briefings/BriefingsPage";
import DashboardPage from "@/features/dashboard-map/DashboardPage";
import DocumentViewerPage from "@/features/documents/DocumentViewerPage";
import LiveStreamsPage from "@/features/live-streams/LiveStreamsPage";
import MfaChallengePage from "@/features/mfa/MfaChallengePage";
import JobsProvenancePage from "@/features/provenance-jobs/JobsProvenancePage";
import SearchStudioPage from "@/features/search-studio/SearchStudioPage";
import VaultPage from "@/features/vault-ingest/VaultPage";

export default function AppRouter() {
  return (
    <Routes>
      {/* Public Auth Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/mfa" element={<MfaChallengePage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Authenticated Sovereign Operator Routes */}
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/streams" element={<LiveStreamsPage />} />
        <Route path="/vault" element={<VaultPage />} />
        <Route path="/workbench" element={<AudioWorkbenchPage />} />
        <Route path="/search" element={<SearchStudioPage />} />
        <Route path="/briefings" element={<BriefingsPage />} />
        <Route path="/documents" element={<DocumentViewerPage />} />
        <Route path="/jobs" element={<JobsProvenancePage />} />
        <Route path="/admin" element={<AdminConsolePage />} />
        <Route path="/settings/security" element={<AccountSecurityPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
