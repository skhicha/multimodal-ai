import { useCallback } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { CommandPalette } from "./components/CommandPalette";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { VerifyEmailBanner } from "./components/VerifyEmailBanner";
import { JustRegisteredToast } from "./components/JustRegisteredToast";
import { IdleWarningModal } from "./components/IdleWarningModal";
import { UploadsTray } from "./components/UploadsTray";
import { useIdleTimeout } from "./hooks/useIdleTimeout";
import { AuthProvider } from "./lib/AuthContext";
import { useAuth } from "./lib/AuthContext";
import { UploadStoreProvider } from "./lib/UploadStore";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { ForgotPasswordPage } from "./pages/ForgotPassword";
import { OAuthCallbackPage } from "./pages/OAuthCallback";
import { UploadPage } from "./pages/Upload";
import { LibraryPage } from "./pages/Library";
import { MediaDetailPage } from "./pages/MediaDetail";
import { TimelinePage } from "./pages/Timeline";
import { MapViewPage } from "./pages/MapView";
import { SearchPage } from "./pages/Search";
import { AskAIPage } from "./pages/AskAI";
import { DashboardPage } from "./pages/Dashboard";
import { SettingsPage } from "./pages/Settings";
import { AdminPage } from "./pages/Admin";
import { CollectionsPage } from "./pages/Collections";
import { CollectionDetailPage } from "./pages/CollectionDetail";
import { TrashPage } from "./pages/Trash";

const AUTH_ROUTES = ["/login", "/register", "/forgot-password", "/oauth/callback"];

function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isAuthRoute = AUTH_ROUTES.includes(location.pathname);
  const showShell = !!user && !isAuthRoute;

  const handleIdleTimeout = useCallback(() => {
    logout().finally(() => navigate("/login", { replace: true, state: { idleLoggedOut: true } }));
  }, [logout, navigate]);

  const { warning, stayActive } = useIdleTimeout(!!user, handleIdleTimeout);

  return (
    <div className="app-shell">
      {showShell && <Navbar />}
      {showShell && <CommandPalette />}
      {!!user && warning && <IdleWarningModal onStayActive={stayActive} />}
      {showShell && <UploadsTray />}
      <main className={isAuthRoute ? "app-main app-main-auth" : "app-main"}>
        {showShell && <JustRegisteredToast />}
        {showShell && <VerifyEmailBanner />}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
          <Route path="/" element={<Navigate to="/library" replace />} />
          <Route
            path="/upload"
            element={
              <ProtectedRoute blockRoles={["viewer"]} requirePermission="media.upload">
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/library"
            element={
              <ProtectedRoute>
                <LibraryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/media/:id"
            element={
              <ProtectedRoute>
                <MediaDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/collections"
            element={
              <ProtectedRoute requirePermission="collections.view">
                <CollectionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/collections/:id"
            element={
              <ProtectedRoute requirePermission="collections.view">
                <CollectionDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trash"
            element={
              <ProtectedRoute requirePermission="media.delete">
                <TrashPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/timeline"
            element={
              <ProtectedRoute>
                <TimelinePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map"
            element={
              <ProtectedRoute>
                <MapViewPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <SearchPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ask"
            element={
              <ProtectedRoute>
                <AskAIPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/library" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <UploadStoreProvider>
        <AppShell />
      </UploadStoreProvider>
    </AuthProvider>
  );
}
