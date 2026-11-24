import { useEffect, useMemo, useState } from "react";
import { ShieldCheck, Users, Images, UserCog, UserPlus, Trash2 } from "lucide-react";
import { api, type AdminStats, type AdminUser, type AdminRole, type AdminPermission } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { TableSkeleton } from "../components/Skeleton";
import "./Admin.css";

type Role = "admin" | "editor" | "viewer";

interface PendingAction {
  user: AdminUser;
  kind: "deactivate" | "reactivate" | "role" | "delete";
  newRole?: Role;
}

const ACTION_COPY: Record<PendingAction["kind"], { title: string; body: (u: AdminUser, newRole?: Role) => string }> = {
  deactivate: {
    title: "Deactivate user",
    body: (u) => `${u.display_name} (${u.email}) will no longer be able to log in. Continue?`,
  },
  reactivate: {
    title: "Reactivate user",
    body: (u) => `${u.display_name} (${u.email}) will be able to log in again. Continue?`,
  },
  role: {
    title: "Change role",
    body: (u, newRole) => `${u.display_name} (${u.email}) will become '${newRole}'. Continue?`,
  },
  delete: {
    title: "Delete user",
    body: (u) =>
      `${u.display_name} (${u.email}) and all of their media will be permanently deleted. This cannot be undone.`,
  },
};

export function AdminPage() {
  const { user: me } = useAuth();
  const [tab, setTab] = useState<"users" | "roles">("users");
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [acting, setActing] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);

  const load = async () => {
    try {
      const [usersRes, statsRes] = await Promise.all([api.adminListUsers(), api.adminStats()]);
      setUsers(usersRes.users);
      setStats(statsRes);
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Could not load admin data");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const confirmAction = async () => {
    if (!pending) return;
    setActing(true);
    try {
      if (pending.kind === "deactivate") await api.adminDeactivate(pending.user.id);
      if (pending.kind === "reactivate") await api.adminReactivate(pending.user.id);
      if (pending.kind === "role" && pending.newRole) await api.adminSetRole(pending.user.id, pending.newRole);
      if (pending.kind === "delete") await api.adminDeleteUser(pending.user.id);
      setSuccess(`${ACTION_COPY[pending.kind].title} succeeded for ${pending.user.email}.`);
      setPending(null);
      await load();
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Action failed");
      setPending(null);
    } finally {
      setActing(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Workspace oversight</span>
        <h1>Admin<span className="heading-period">.</span></h1>
        <p>User management, roles, and workspace stats.</p>
      </div>

      {error && <div className="auth-error">{error}</div>}
      {success && <div className="auth-success">{success}</div>}

      <div className="admin-stats">
        <div className="admin-stat-tile glass-card">
          <Users size={18} />
          <div>
            <div className="admin-stat-value">{stats?.total_users ?? "—"}</div>
            <div className="admin-stat-label">Total users</div>
          </div>
        </div>
        <div className="admin-stat-tile glass-card">
          <Images size={18} />
          <div>
            <div className="admin-stat-value">{stats?.total_media ?? "—"}</div>
            <div className="admin-stat-label">Total media</div>
          </div>
        </div>
        <div className="admin-stat-tile glass-card">
          <ShieldCheck size={18} />
          <div>
            <div className="admin-stat-value">{stats?.total_admins ?? "—"}</div>
            <div className="admin-stat-label">Admins</div>
          </div>
        </div>
      </div>

      <div className="admin-tabs">
        <button className={`admin-tab ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
          Users
        </button>
        <button className={`admin-tab ${tab === "roles" ? "active" : ""}`} onClick={() => setTab("roles")}>
          Roles &amp; permissions
        </button>
      </div>

      {tab === "users" && (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowAddUser(true)}>
              <UserPlus size={14} /> Add user
            </button>
          </div>

          <div className="glass-card admin-table-card">
            {!users ? (
              <TableSkeleton rows={5} cols={7} />
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Name</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Media</th>
                      <th className="admin-col-created">Created</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>{u.email}</td>
                        <td>{u.display_name}</td>
                        <td>
                          <span className={`badge badge-${u.role}`}>{u.role}</span>
                        </td>
                        <td>
                          <span className={`badge ${u.is_active ? "badge-active" : "badge-inactive"}`}>
                            {u.is_active ? "active" : "inactive"}
                          </span>
                        </td>
                        <td>{u.media_count}</td>
                        <td className="admin-col-created">{new Date(u.created_at).toLocaleDateString()}</td>
                        <td className="admin-row-actions">
                          {u.id !== me?.id && (
                            <>
                              {u.is_active ? (
                                <button
                                  className="btn btn-sm"
                                  onClick={() => setPending({ user: u, kind: "deactivate" })}
                                >
                                  Deactivate
                                </button>
                              ) : (
                                <button
                                  className="btn btn-sm"
                                  onClick={() => setPending({ user: u, kind: "reactivate" })}
                                >
                                  Reactivate
                                </button>
                              )}
                              <label className="admin-role-select">
                                <UserCog size={14} />
                                <select
                                  value={u.role}
                                  onChange={(e) =>
                                    setPending({ user: u, kind: "role", newRole: e.target.value as Role })
                                  }
                                >
                                  <option value="admin">admin</option>
                                  <option value="editor">editor</option>
                                  <option value="viewer">viewer</option>
                                </select>
                              </label>
                              <button
                                className="btn btn-sm"
                                title="Delete user"
                                onClick={() => setPending({ user: u, kind: "delete" })}
                              >
                                <Trash2 size={14} />
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {tab === "roles" && <RolesPanel />}

      {pending && (
        <div className="admin-modal-overlay" onClick={() => !acting && setPending(null)}>
          <div className="admin-modal glass-card" onClick={(e) => e.stopPropagation()}>
            <h3>{ACTION_COPY[pending.kind].title}</h3>
            <p>{ACTION_COPY[pending.kind].body(pending.user, pending.newRole)}</p>
            <div className="admin-modal-actions">
              <button className="btn" onClick={() => setPending(null)} disabled={acting}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={confirmAction} disabled={acting}>
                {acting ? "Working…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAddUser && (
        <AddUserModal
          onClose={() => setShowAddUser(false)}
          onCreated={async (msg) => {
            setShowAddUser(false);
            setError(null);
            setSuccess(msg);
            await load();
            setTimeout(() => setSuccess(null), 4000);
          }}
          onError={(msg) => setError(msg)}
        />
      )}
    </div>
  );
}

function AddUserModal({
  onClose,
  onCreated,
  onError,
}: {
  onClose: () => void;
  onCreated: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = async () => {
    setSubmitting(true);
    setLocalError(null);
    try {
      const created = await api.adminCreateUser(email, password, displayName, role);
      onCreated(`${created.display_name} (${created.email}) was created as ${created.role}.`);
    } catch (err) {
      const msg = (err as Error).message.replace(/^\d+\s*/, "") || "Could not create user";
      setLocalError(msg);
      onError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="admin-modal-overlay" onClick={() => !submitting && onClose()}>
      <div className="admin-modal admin-modal-wide glass-card" onClick={(e) => e.stopPropagation()}>
        <h3>Add user</h3>
        {localError && <div className="auth-error">{localError}</div>}
        <div className="admin-form-field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" />
        </div>
        <div className="admin-form-field">
          <label>Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Jane Doe" />
        </div>
        <div className="admin-form-field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
          />
        </div>
        <div className="admin-form-field">
          <label>Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="admin">admin</option>
            <option value="editor">editor</option>
            <option value="viewer">viewer</option>
          </select>
        </div>
        <div className="admin-modal-actions">
          <button className="btn" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={submitting || !email || !password || !displayName}
          >
            {submitting ? "Creating…" : "Create user"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RolesPanel() {
  const [roles, setRoles] = useState<AdminRole[] | null>(null);
  const [permissions, setPermissions] = useState<AdminPermission[] | null>(null);
  const [draft, setDraft] = useState<Record<number, Set<string>>>({});
  const [savingRoleId, setSavingRoleId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = async () => {
    const [rolesRes, permsRes] = await Promise.all([api.adminListRoles(), api.adminListPermissions()]);
    setRoles(rolesRes.roles);
    setPermissions(permsRes.permissions);
    setDraft(Object.fromEntries(rolesRes.roles.map((r) => [r.id, new Set(r.permissions)])));
  };

  useEffect(() => {
    load();
  }, []);

  const grouped = useMemo(() => {
    const byResource: Record<string, AdminPermission[]> = {};
    for (const p of permissions ?? []) {
      (byResource[p.resource] ??= []).push(p);
    }
    return byResource;
  }, [permissions]);

  const toggle = (roleId: number, code: string) => {
    setDraft((prev) => {
      const next = new Set(prev[roleId]);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return { ...prev, [roleId]: next };
    });
  };

  const save = async (role: AdminRole) => {
    setSavingRoleId(role.id);
    setMessage(null);
    try {
      await api.adminUpdateRolePermissions(role.id, Array.from(draft[role.id] ?? []));
      setMessage({ kind: "ok", text: `Saved permissions for '${role.slug}'.` });
      await load();
    } catch (err) {
      setMessage({ kind: "err", text: (err as Error).message.replace(/^\d+\s*/, "") || "Could not save" });
    } finally {
      setSavingRoleId(null);
      setTimeout(() => setMessage(null), 4000);
    }
  };

  if (!roles || !permissions) {
    return <TableSkeleton rows={3} cols={1} />;
  }

  return (
    <div>
      {message && <div className={message.kind === "ok" ? "auth-success" : "auth-error"}>{message.text}</div>}
      <div className="admin-roles-grid">
        {roles.map((role) => {
          const selected = draft[role.id] ?? new Set<string>();
          return (
            <div key={role.id} className="glass-card admin-role-card">
              <div className="admin-role-card-head">
                <h3>{role.slug}</h3>
                <span className="admin-role-count">
                  {role.user_count} user{role.user_count === 1 ? "" : "s"}
                </span>
              </div>
              <p className="admin-role-desc">{role.description}</p>

              {Object.entries(grouped).map(([resource, perms]) => (
                <div key={resource} className="admin-perm-group">
                  <div className="admin-perm-group-title">{resource.replace("_", " ")}</div>
                  {perms.map((p) => (
                    <label key={p.code} className="admin-perm-toggle">
                      <input
                        type="checkbox"
                        checked={selected.has(p.code)}
                        onChange={() => toggle(role.id, p.code)}
                      />
                      <span>{p.action}</span>
                    </label>
                  ))}
                </div>
              ))}

              <div className="admin-role-card-footer">
                <span className="admin-perm-selected-count">
                  {selected.size} / {permissions.length} selected
                </span>
                <button className="btn btn-primary btn-sm" onClick={() => save(role)} disabled={savingRoleId === role.id}>
                  {savingRoleId === role.id ? "Saving…" : "Save"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
