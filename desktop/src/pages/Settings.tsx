import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  Avatar,
  Badge,
  Button,
  ConfirmDialog,
  Field,
  Input,
  Notice,
  PageHead,
  Select,
  Toggle,
} from "../components/ui";
import { Icon, type IconName } from "../components/Icons";
import { ROLE_DESCRIPTIONS, ROLE_LABELS, canManageSettings } from "../lib/permissions";
import type { Role } from "../lib/types";

const TABS: Array<{ id: string; label: string; icon: IconName }> = [
  { id: "organisation", label: "Organisation", icon: "building" },
  { id: "inventory", label: "Inventory rules", icon: "package" },
  { id: "requests", label: "Requests", icon: "inbox" },
  { id: "access", label: "Roles & access", icon: "shield" },
  { id: "data", label: "Data & backup", icon: "database" },
];

const PERMISSIONS: Array<{ label: string; admin: boolean; supervisor: boolean; student: boolean }> = [
  { label: "Browse inventory & stock levels", admin: true, supervisor: true, student: true },
  { label: "Create and edit items", admin: true, supervisor: true, student: false },
  { label: "Adjust, receive and issue stock", admin: true, supervisor: true, student: false },
  { label: "Submit material requests", admin: true, supervisor: true, student: true },
  { label: "Approve or reject requests", admin: true, supervisor: true, student: false },
  { label: "Create and edit projects", admin: true, supervisor: true, student: false },
  { label: "Delete records", admin: true, supervisor: false, student: false },
  { label: "View reports and exports", admin: true, supervisor: true, student: false },
  { label: "Change organisation settings", admin: true, supervisor: false, student: false },
];

const SEMESTERS = ["Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"];

type BooleanSetting =
  | "lowStockAlerts"
  | "requestAlerts"
  | "weeklyDigest"
  | "requireApproval"
  | "allowStudentRequests";

export default function Settings() {
  const { state } = useApp();
  return <SettingsContent key={JSON.stringify(state.settings)} />;
}

function SettingsContent() {
  usePageTitle("Settings");
  const { state, role, actorName, updateSettings, resetData, exportState, setRole } = useApp();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const active = params.get("tab") ?? "organisation";
  const allowed = canManageSettings(role);

  const [org, setOrg] = useState(() => ({
    orgName: state.settings.orgName,
    campus: state.settings.campus,
    semester: state.settings.semester,
  }));
  const [threshold, setThreshold] = useState(() => String(state.settings.defaultMinThreshold));
  const [resetOpen, setResetOpen] = useState(false);

  const counts = useMemo(
    () => ({
      items: state.items.length,
      projects: state.projects.length,
      requests: state.requests.length,
      transactions: state.transactions.length,
      suppliers: state.suppliers.length,
      categories: state.categories.length,
    }),
    [state]
  );

  const go = (tab: string) => {
    const next = new URLSearchParams(params);
    next.set("tab", tab);
    setParams(next, { replace: true });
  };

  const toggle = (key: BooleanSetting, label: string) => {
    const current = state.settings[key];
    const result = updateSettings({ [key]: !current } as Partial<typeof state.settings>);
    if (!result.ok) toast.error("Not changed", result.message);
    else toast.success(`${label} ${!current ? "enabled" : "disabled"}`);
  };

  const saveOrganisation = () => {
    if (!org.orgName.trim()) {
      toast.error("Organisation name required", "Enter the name shown on exports and reports.");
      return;
    }
    if (!org.campus.trim()) {
      toast.error("Campus required", "Add the campus or lab block name.");
      return;
    }
    const result = updateSettings({
      orgName: org.orgName.trim(),
      campus: org.campus.trim(),
      semester: org.semester,
    });
    if (!result.ok) toast.error("Not saved", result.message);
    else toast.success("Organisation updated", "Exports and reports now use these details.");
  };

  const saveThreshold = () => {
    const value = Number(threshold);
    if (!Number.isFinite(value) || value < 0) {
      toast.error("Invalid threshold", "Enter a whole number greater than or equal to zero.");
      return;
    }
    const result = updateSettings({ defaultMinThreshold: Math.round(value) });
    if (!result.ok) toast.error("Not saved", result.message);
    else toast.success("Default threshold saved", `New items will start with a minimum of ${Math.round(value)} units.`);
  };

  const downloadBackup = () => {
    const blob = new Blob([exportState()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inventra-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Backup downloaded", "The JSON snapshot contains every item, project, request and transaction.");
  };

  const doReset = () => {
    resetData();
    setResetOpen(false);
    toast.success("Workspace reset", "Sample data was restored. Your changes were cleared from this browser.");
  };

  return (
    <>
      <PageHead
        title="Settings"
        sub="Organisation details, stock rules, request policy and workspace data."
        actions={<Badge tone="plain">{ROLE_LABELS[role]}</Badge>}
      />

      {!allowed ? (
        <Notice tone="amber" icon="lock">
          You are signed in as <b>{ROLE_LABELS[role]}</b>. Settings are read-only for this role — sign in as an
          administrator to change them.
        </Notice>
      ) : null}

      <div className="settings-layout" style={{ marginTop: 18 }}>
        <nav className="settings-nav" aria-label="Settings sections">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`settings-nav__item${active === tab.id ? " is-active" : ""}`}
              aria-current={active === tab.id ? "page" : undefined}
              onClick={() => go(tab.id)}
            >
              <Icon name={tab.icon} />
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="settings-panel">
          {active === "organisation" ? (
            <>
              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Organisation profile</h2>
                  <p className="settings-section__sub">Shown on reports, exports and the workspace header.</p>
                </div>
                <div className="form-grid">
                  <Field label="Organisation name" required htmlFor="org-name">
                    <Input
                      id="org-name"
                      value={org.orgName}
                      disabled={!allowed}
                      onChange={(e) => setOrg((p) => ({ ...p, orgName: e.target.value }))}
                      placeholder="Meridian Institute of Technology"
                    />
                  </Field>
                  <Field label="Campus / lab block" required htmlFor="org-campus">
                    <Input
                      id="org-campus"
                      value={org.campus}
                      disabled={!allowed}
                      onChange={(e) => setOrg((p) => ({ ...p, campus: e.target.value }))}
                      placeholder="Innovation Lab, Block C"
                    />
                  </Field>
                  <Field label="Current semester" htmlFor="org-semester">
                    <Select
                      id="org-semester"
                      value={org.semester}
                      disabled={!allowed}
                      onChange={(e) => setOrg((p) => ({ ...p, semester: e.target.value }))}
                    >
                      {SEMESTERS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Currency" hint="Inventory value is always reported in Indian rupees.">
                    <Input value="INR — Indian rupee" disabled readOnly />
                  </Field>
                </div>
                {allowed ? (
                  <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                    <Button size="sm" variant="primary" icon="check" onClick={saveOrganisation}>
                      Save changes
                    </Button>
                    <Button
                      size="sm"
                      icon="refresh"
                      onClick={() =>
                        setOrg({
                          orgName: state.settings.orgName,
                          campus: state.settings.campus,
                          semester: state.settings.semester,
                        })
                      }
                    >
                      Discard
                    </Button>
                  </div>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Signed in as</h2>
                  <p className="settings-section__sub">Role switching is available from the account menu in the top bar.</p>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">
                      <Avatar name={actorName} /> {actorName}
                    </span>
                    <span className="settings-row__sub">
                      {ROLE_LABELS[role]} · {state.settings.semester}
                    </span>
                  </div>
                  <div className="settings-row__control">
                    <Badge tone={role === "admin" ? "olive" : role === "supervisor" ? "blue" : "slate"} dot>
                      {ROLE_LABELS[role]}
                    </Badge>
                  </div>
                </div>
              </section>
            </>
          ) : null}

          {active === "inventory" ? (
            <>
              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Stock rules</h2>
                  <p className="settings-section__sub">Defaults applied when a new item is added to the store.</p>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Default minimum threshold</span>
                    <span className="settings-row__sub">
                      Items at or below this quantity are flagged{" "}
                      <Badge tone="amber">low stock</Badge>. Individual items can override it.
                    </span>
                  </div>
                  <div className="settings-row__control" style={{ display: "flex", gap: 8 }}>
                    <Input
                      type="number"
                      min={0}
                      value={threshold}
                      disabled={!allowed}
                      onChange={(e) => setThreshold(e.target.value)}
                      style={{ width: 92 }}
                      aria-label="Default minimum threshold"
                    />
                    {allowed ? (
                      <Button size="sm" icon="check" onClick={saveThreshold}>
                        Save
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Low-stock alerts</span>
                    <span className="settings-row__sub">Show threshold breaches in the notification tray and alerts card.</span>
                  </div>
                  <div className="settings-row__control">
                    <Toggle
                      checked={state.settings.lowStockAlerts}
                      label="Low-stock alerts"
                      onChange={() => toggle("lowStockAlerts", "Low-stock alerts")}
                      disabled={!allowed}
                    />
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Weekly movement digest</span>
                    <span className="settings-row__sub">Summarise receipts, issues and returns every Monday.</span>
                  </div>
                  <div className="settings-row__control">
                    <Toggle
                      checked={state.settings.weeklyDigest}
                      label="Weekly movement digest"
                      onChange={() => toggle("weeklyDigest", "Weekly digest")}
                      disabled={!allowed}
                    />
                  </div>
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Current stock posture</h2>
                  <p className="settings-section__sub">Snapshot of how the rules above are performing right now.</p>
                </div>
                <div className="mini-stats">
                  <div className="mini-stat">
                    <span>Items tracked</span>
                    <b>{counts.items}</b>
                    <em>across {counts.categories} categories</em>
                  </div>
                  <div className="mini-stat">
                    <span>Below threshold</span>
                    <b>{state.items.filter((i) => i.qty <= i.minQty).length}</b>
                    <em>low or depleted</em>
                  </div>
                  <div className="mini-stat">
                    <span>Fully depleted</span>
                    <b>{state.items.filter((i) => i.qty <= 0).length}</b>
                    <em>needs reorder</em>
                  </div>
                  <div className="mini-stat">
                    <span>Suppliers</span>
                    <b>{counts.suppliers}</b>
                    <em>active vendors</em>
                  </div>
                </div>
              </section>
            </>
          ) : null}

          {active === "requests" ? (
            <>
              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Request workflow</h2>
                  <p className="settings-section__sub">
                    Controls how student material requests move from submission to issue.
                  </p>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Require approval before issue</span>
                    <span className="settings-row__sub">
                      Requests must be approved by a supervisor before materials leave the store.
                    </span>
                  </div>
                  <div className="settings-row__control">
                    <Toggle
                      checked={state.settings.requireApproval}
                      label="Require approval before issue"
                      onChange={() => toggle("requireApproval", "Approval requirement")}
                      disabled={!allowed}
                    />
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Accept student requests</span>
                    <span className="settings-row__sub">Close submissions during audits or semester breaks.</span>
                  </div>
                  <div className="settings-row__control">
                    <Toggle
                      checked={state.settings.allowStudentRequests}
                      label="Accept student requests"
                      onChange={() => toggle("allowStudentRequests", "Student submissions")}
                      disabled={!allowed}
                    />
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Pending request alerts</span>
                    <span className="settings-row__sub">Surface the approval queue in the notification tray.</span>
                  </div>
                  <div className="settings-row__control">
                    <Toggle
                      checked={state.settings.requestAlerts}
                      label="Pending request alerts"
                      onChange={() => toggle("requestAlerts", "Request alerts")}
                      disabled={!allowed}
                    />
                  </div>
                </div>
                {!state.settings.requireApproval ? (
                  <Notice tone="amber" icon="alert-triangle">
                    Approval is currently optional. New requests can still be reviewed manually, but nothing blocks an
                    immediate issue.
                  </Notice>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Queue right now</h2>
                  <p className="settings-section__sub">Live counts from the request desk.</p>
                </div>
                <div className="mini-stats">
                  <div className="mini-stat">
                    <span>Pending</span>
                    <b>{state.requests.filter((r) => r.status === "pending").length}</b>
                    <em>awaiting review</em>
                  </div>
                  <div className="mini-stat">
                    <span>Approved</span>
                    <b>{state.requests.filter((r) => r.status === "approved").length}</b>
                    <em>ready to issue</em>
                  </div>
                  <div className="mini-stat">
                    <span>Issued</span>
                    <b>{state.requests.filter((r) => r.status === "issued").length}</b>
                    <em>materials handed over</em>
                  </div>
                  <div className="mini-stat">
                    <span>Rejected</span>
                    <b>{state.requests.filter((r) => r.status === "rejected").length}</b>
                    <em>needs rework</em>
                  </div>
                </div>
              </section>
            </>
          ) : null}

          {active === "access" ? (
            <>
              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Roles</h2>
                  <p className="settings-section__sub">Switch role to preview the workspace permissions. This demo app has no login.</p>
                </div>
                <div className="role-cards">
                  {(["admin", "supervisor", "student"] as Role[]).map((r) => (
                    <button
                      key={r}
                      type="button"
                      className={`role-card${role === r ? " is-active" : ""}`}
                      onClick={() => {
                        setRole(r);
                        toast.info(`Now viewing as ${ROLE_LABELS[r]}`, "Navigation and actions update immediately.");
                      }}
                    >
                      <span className="role-card__name">
                        {ROLE_LABELS[r]}
                        {role === r ? <Badge tone="olive">current</Badge> : null}
                      </span>
                      <span className="role-card__desc">{ROLE_DESCRIPTIONS[r]}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Permission matrix</h2>
                  <p className="settings-section__sub">What each role can do in this workspace.</p>
                </div>
                <div className="table-wrap">
                  <table className="table perm-table">
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Administrator</th>
                        <th>Faculty supervisor</th>
                        <th>Student</th>
                      </tr>
                    </thead>
                    <tbody>
                      {PERMISSIONS.map((row) => (
                        <tr key={row.label}>
                          <td>{row.label}</td>
                          {[row.admin, row.supervisor, row.student].map((value, i) => (
                            <td key={i}>
                              {value ? (
                                <span className="perm-yes">
                                  <Icon name="check" />
                                </span>
                              ) : (
                                <span className="perm-no">
                                  <Icon name="x" />
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Team</h2>
                  <p className="settings-section__sub">People with access to the materials store.</p>
                </div>
                <div className="approval-panel">
                  {(["admin", "supervisor", "student"] as Role[]).map((r) => (
                    <div className="approval-panel__item" key={r}>
                      <Avatar name={r === "admin" ? "Himaneesh Reddy" : r === "supervisor" ? "Dr. Ananya Rao" : "Aarav Sharma"} />
                      <div>
                        <div className="cell-title" style={{ fontSize: 11.5 }}>
                          {r === "admin" ? "Himaneesh Reddy" : r === "supervisor" ? "Dr. Ananya Rao" : "Aarav Sharma"}
                        </div>
                        <div className="cell-sub">{ROLE_LABELS[r]}</div>
                      </div>
                      <span className="req">
                        <Badge tone={role === r ? "olive" : "plain"}>{role === r ? "you" : "member"}</Badge>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {active === "data" ? (
            <>
              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">Workspace data</h2>
                  <p className="settings-section__sub">
                    Everything is stored locally in this browser under <span className="mono">inventra.pbl.v1</span>.
                  </p>
                </div>
                <div className="mini-stats" style={{ marginBottom: 16 }}>
                  <div className="mini-stat">
                    <span>Inventory items</span>
                    <b>{counts.items}</b>
                  </div>
                  <div className="mini-stat">
                    <span>Transactions</span>
                    <b>{counts.transactions}</b>
                  </div>
                  <div className="mini-stat">
                    <span>Projects</span>
                    <b>{counts.projects}</b>
                  </div>
                  <div className="mini-stat">
                    <span>Requests</span>
                    <b>{counts.requests}</b>
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Download a backup</span>
                    <span className="settings-row__sub">
                      JSON snapshot of items, projects, requests, suppliers and the full ledger.
                    </span>
                  </div>
                  <div className="settings-row__control">
                    <Button size="sm" icon="download" onClick={downloadBackup}>
                      Export JSON
                    </Button>
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-row__main">
                    <span className="settings-row__title">Reset to sample data</span>
                    <span className="settings-row__sub">
                      Clears this browser's workspace and restores the seeded PBL dataset.
                    </span>
                  </div>
                  <div className="settings-row__control">
                    <Button
                      size="sm"
                      variant="danger-soft"
                      icon="refresh"
                      onClick={() => (allowed ? setResetOpen(true) : toast.error("Administrator only"))}
                    >
                      Reset workspace
                    </Button>
                  </div>
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-section__head">
                  <h2 className="settings-section__title">This deployment</h2>
                  <p className="settings-section__sub">Frontend-only demo build — no server calls, no accounts.</p>
                </div>
                <div className="approval-panel">
                  <div className="approval-panel__item">
                    <Icon name="database" />
                    <div>
                      <div className="cell-title" style={{ fontSize: 11.5 }}>
                        Storage engine
                      </div>
                      <div className="cell-sub">Browser localStorage</div>
                    </div>
                    <span className="req">
                      <b>1</b> namespace
                    </span>
                  </div>
                  <div className="approval-panel__item">
                    <Icon name="file" />
                    <div>
                      <div className="cell-title" style={{ fontSize: 11.5 }}>
                        Seed dataset
                      </div>
                      <div className="cell-sub">47 items · 6 projects · 11 requests</div>
                    </div>
                    <span className="req">
                      <b>built-in</b>
                    </span>
                  </div>
                  <div className="approval-panel__item">
                    <Icon name="shield" />
                    <div>
                      <div className="cell-title" style={{ fontSize: 11.5 }}>
                        Authentication
                      </div>
                      <div className="cell-sub">Role switcher for demonstration</div>
                    </div>
                    <span className="req">
                      <b>demo</b>
                    </span>
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </div>
      </div>

      <ConfirmDialog
        open={resetOpen}
        title="Reset the workspace?"
        message="Every item, project, request and transaction you have created will be replaced with the original sample data. Download a backup first if you need to keep your work."
        confirmLabel="Reset workspace"
        onConfirm={doReset}
        onClose={() => setResetOpen(false)}
      />
    </>
  );
}
