import { NavLink, useNavigate } from "react-router-dom";
import {
  Upload,
  LayoutGrid,
  Clock,
  Map as MapIcon,
  Search,
  Sparkles,
  BarChart3,
  Settings as SettingsIcon,
  Camera,
  LogOut,
  ShieldCheck,
  Folder,
  Trash2,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../lib/AuthContext";
import "./Navbar.css";

const LINKS = [
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/library", label: "Library", icon: LayoutGrid },
  { to: "/collections", label: "Collections", icon: Folder },
  { to: "/timeline", label: "Timeline", icon: Clock },
  { to: "/map", label: "Map", icon: MapIcon },
  { to: "/search", label: "Search", icon: Search },
  { to: "/ask", label: "Ask AI", icon: Sparkles },
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
  { to: "/trash", label: "Trash", icon: Trash2 },
];

export function Navbar() {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <nav className="navbar glass-card">
      <div className="navbar-brand">
        <div className="navbar-logo">
          <Camera size={20} />
        </div>
        <div>
          <div className="navbar-title">MemoryLens AI</div>
          <div className="navbar-subtitle">Personal media vault</div>
        </div>
      </div>

      <div className="navbar-links">
        {LINKS.filter(
          ({ to }) =>
            (to !== "/upload" || hasPermission("media.upload")) &&
            (to !== "/collections" || hasPermission("collections.view")) &&
            (to !== "/trash" || hasPermission("media.delete"))
        ).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `navbar-link${isActive ? " active" : ""}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
        {user?.role === "admin" && (
          <NavLink to="/admin" className={({ isActive }) => `navbar-link${isActive ? " active" : ""}`}>
            <ShieldCheck size={18} />
            <span>Admin</span>
          </NavLink>
        )}
      </div>

      <div className="navbar-footer">
        {user && (
          <div className="navbar-user">
            <div className="navbar-user-avatar">{user.display_name.charAt(0).toUpperCase()}</div>
            <div className="navbar-user-name" title={user.email}>
              {user.display_name}
            </div>
            <button className="navbar-logout" onClick={onLogout} title="Log out">
              <LogOut size={15} />
            </button>
          </div>
        )}
        <ThemeToggle />
      </div>
    </nav>
  );
}
