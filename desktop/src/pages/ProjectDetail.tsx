import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "../store/useApp";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  AvatarStack,
  Badge,
  Bar,
  Button,
  Card,
  CardHead,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHead,
  RowMenu,
} from "../components/ui";
import { ProjectFormModal, RequestFormModal, ReturnModal, StockOutModal } from "../components/forms";
import { Icon, type IconName } from "../components/Icons";
import { projectActivity, projectStats } from "../lib/derive";
import {
  dateShort,
  daysBetween,
  inr,
  inrCompact,
  num,
  projectStatusLabel,
  projectStatusTone,
  requestStatusLabel,
  requestStatusTone,
  relTime,
} from "../lib/format";
import { canDeleteRecords, canManageInventory, canManageProjects } from "../lib/permissions";
import type { Item, Project } from "../lib/types";

const PROJECT_DETAIL_REFERENCE_DATE = new Date().toISOString();

const TXN_META: Record<string, { label: string; icon: "arrow-down-left" | "arrow-up-right" | "corner-up-left" | "sliders" }> = {
  in: { label: "Stock in", icon: "arrow-down-left" },
  out: { label: "Issued", icon: "arrow-up-right" },
  return: { label: "Returned", icon: "corner-up-left" },
  adjust: { label: "Adjusted", icon: "sliders" },
};

/* ------------------------------------------------------------------ */
/* Consumption recorder                                                */
/* ------------------------------------------------------------------ */

function ConsumeModal({
  open,
  onClose,
  project,
  item,
}: {
  open: boolean;
  onClose: () => void;
  project?: Project;
  item?: Item;
}) {
  if (!open || !project || !item) return null;
  return <ConsumeForm key={`${project.id}:${item.id}`} onClose={onClose} project={project} item={item} />;
}

function ConsumeForm({ onClose, project, item }: { onClose: () => void; project: Project; item: Item }) {
  const { consumeMaterial } = useApp();
  const toast = useToast();
  const [qty, setQty] = useState(1);

  const allocation = project.allocations.find((allocation) => allocation.itemId === item.id);
  const inUse = allocation ? allocation.issued - allocation.consumed - allocation.returned : 0;

  const submit = () => {
    const result = consumeMaterial({ projectId: project.id, itemId: item.id, qty });
    if (!result.ok) {
      toast.error("Consumption not recorded", result.message);
      return;
    }
    toast.success("Consumption recorded", `${num(qty)} ${item.unit} of ${item.name} marked as used.`);
    onClose();
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Record consumption"
      sub={`${item.name} · ${project.id}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="check">
            Record consumption
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <Field label="Quantity consumed" required hint={`${num(inUse)} ${item.unit} currently in use on this project`} htmlFor="consume-qty">
          <Input
            id="consume-qty"
            type="number"
            min={1}
            max={inUse}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            autoFocus
          />
        </Field>
        <div className="summary">
          <div className="summary__row">
            <span>In use</span>
            <b>
              {num(inUse)} {item.unit}
            </b>
          </div>
          <div className="summary__row">
            <span>After recording</span>
            <b>
              {num(Math.max(0, inUse - qty))} {item.unit}
            </b>
          </div>
        </div>
        <p className="report-note">
          Consumption does not change stock on hand — the material was already removed from the store when it was
          issued. It only reduces what is still committed to the project.
        </p>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { state, role, deleteProject } = useApp();
  const toast = useToast();
  const project = state.projects.find((p) => p.id === id);

  usePageTitle(project?.name ?? "Project");

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnItemId, setReturnItemId] = useState<string | undefined>();
  const [consumeFor, setConsumeFor] = useState<Item | undefined>();
  const [requestOpen, setRequestOpen] = useState(false);

  const canEdit = canManageProjects(role);
  const canIssue = canManageInventory(role);
  const canDelete = canDeleteRecords(role);

  const stats = useMemo(() => (project ? projectStats(state, project) : null), [state, project]);
  const activity = useMemo(() => (project ? projectActivity(state, project.id, 12) : []), [state, project]);
  const requests = useMemo(
    () => (project ? state.requests.filter((r) => r.projectId === project.id) : []),
    [state, project]
  );


  if (!project || !stats) {
    return (
      <>
        <PageHead title="Project not found" sub="This project may have been deleted or the link is out of date." />
        <EmptyState
          icon="layers"
          title="We could not find that project"
          text="Browse the project list to pick a team."
          action={
            <Button variant="primary" size="sm" icon="arrow-left" onClick={() => navigate("/projects")}>
              Back to projects
            </Button>
          }
        />
      </>
    );
  }

  const totalRequired = project.required.length;
  const covered = project.required.filter((r) => {
    if (!r.itemId) return false;
    const allocation = project.allocations.find((a) => a.itemId === r.itemId);
    return Boolean(allocation && allocation.issued > 0);
  }).length;

  const daysLeft = daysBetween(PROJECT_DETAIL_REFERENCE_DATE, project.endDate);
  const openRequests = requests.filter((r) => r.status === "pending" || r.status === "approved");

  const handleDelete = () => {
    const result = deleteProject(project.id);
    if (!result.ok) toast.error("Project not deleted", result.message);
    else {
      toast.success("Project deleted", `${project.name} was removed.`);
      navigate("/projects");
    }
    setDeleteOpen(false);
  };

  return (
    <>
      <PageHead
        compact
        title={
          <>
            {project.name}
            <Badge tone={projectStatusTone(project.status)} dot>
              {projectStatusLabel(project.status)}
            </Badge>
          </>
        }
        sub={project.description || "No project description recorded."}
        actions={
          <>
            <Button variant="secondary" size="sm" icon="arrow-left" onClick={() => navigate("/projects")}>
              All projects
            </Button>
            {canIssue ? (
              <Button variant="secondary" size="sm" icon="upload" onClick={() => setIssueOpen(true)}>
                Issue materials
              </Button>
            ) : null}
            {canIssue ? (
              <Button variant="primary" size="sm" icon="corner-up-left" onClick={() => setReturnOpen(true)}>
                Record return
              </Button>
            ) : null}
            {canEdit ? (
              <RowMenu
                items={[
                  { label: "Edit project", icon: "pencil", onClick: () => setEditOpen(true) },
                  {
                    label: "Delete project",
                    icon: "trash",
                    danger: true,
                    hidden: !canDelete,
                    onClick: () => setDeleteOpen(true),
                  },
                ]}
              />
            ) : null}
          </>
        }
      />

      <div className="project-hero">
        <div className="project-hero__top">
          <span className="cat-card__glyph" style={{ background: "var(--olive-soft)", color: "var(--olive)", width: 46, height: 46 }}>
            <Icon name="layers" size={22} />
          </span>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div className="project-hero__code">{project.id}</div>
            <h2 className="project-hero__title">{project.name}</h2>
            <p className="project-hero__desc">{project.description || "No description recorded for this project."}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--faint)" }}>
              Materials consumed
            </div>
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.6px", marginTop: 2 }}>
              {inrCompact(stats.consumedValue)}
            </div>
            <div className="report-note">{stats.lines} tracked material lines</div>
          </div>
        </div>

        <div className="project-hero__meta">
          <span className="project-meta-item">
            <Icon name="user" /> Supervisor <b>{project.supervisor}</b>
          </span>
          <span className="project-meta-item">
            <Icon name="calendar" /> {dateShort(project.startDate)} → {dateShort(project.endDate)}
          </span>
          <span className="project-meta-item">
            <Icon name="clock" />
            {project.status === "completed"
              ? "Completed"
              : daysLeft >= 0
                ? `${daysLeft} day${daysLeft === 1 ? "" : "s"} remaining`
                : `${Math.abs(daysLeft)} days overdue`}
          </span>
          <span className="project-meta-item">
            <Icon name="users" /> Team <AvatarStack names={project.team} max={4} />
          </span>
        </div>
      </div>

      <div className="mini-stats" style={{ marginBottom: "var(--gutter)" }}>
        <div className="mini-stat">
          <span>Issued</span>
          <b>
            {num(stats.issued)} <small>units</small>
          </b>
          <em>Removed from the store</em>
        </div>
        <div className="mini-stat">
          <span>Consumed</span>
          <b>
            {num(stats.consumed)} <small>units</small>
          </b>
          <em>{inrCompact(stats.consumedValue)} of material used</em>
        </div>
        <div className="mini-stat">
          <span>Returned</span>
          <b>
            {num(stats.returned)} <small>units</small>
          </b>
          <em>Back into stock</em>
        </div>
        <div className="mini-stat">
          <span>Still in use</span>
          <b style={{ color: stats.inUse > 0 ? "var(--blue)" : undefined }}>
            {num(stats.inUse)} <small>units</small>
          </b>
          <em>{stats.progress}% closed out</em>
        </div>
      </div>

      <div className="grid">
        <div className="col-8">
          <Card flush>
            <div style={{ padding: "18px 18px 10px" }}>
              <CardHead
                title="Material allocation"
                sub="What has been issued, used and returned for this build"
                action={
                  canIssue ? (
                    <Button variant="soft" size="sm" icon="upload" onClick={() => setIssueOpen(true)}>
                      Issue
                    </Button>
                  ) : null
                }
              />
            </div>

            {project.allocations.length === 0 ? (
              <EmptyState
                small
                icon="package"
                title="No materials issued yet"
                text="Issue stock to this project and it will be tracked here."
                action={
                  canIssue ? (
                    <Button size="sm" variant="secondary" icon="upload" onClick={() => setIssueOpen(true)}>
                      Issue materials
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Material</th>
                      <th className="num">Issued</th>
                      <th className="num">Consumed</th>
                      <th className="num">Returned</th>
                      <th className="num">In use</th>
                      <th>Progress</th>
                      <th className="cell-actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {project.allocations.map((a) => {
                      const item = state.items.find((i) => i.id === a.itemId);
                      if (!item) return null;
                      const inUse = a.issued - a.consumed - a.returned;
                      const closed = a.issued > 0 ? Math.round(((a.consumed + a.returned) / a.issued) * 100) : 0;
                      return (
                        <tr key={a.itemId}>
                          <td>
                            <div className="cell-item">
                              <span
                                className="thumb thumb--sm"
                                style={{
                                  background: `${state.categories.find((c) => c.id === item.categoryId)?.color ?? "#757575"}14`,
                                  color: state.categories.find((c) => c.id === item.categoryId)?.color,
                                }}
                              >
                                <Icon name={(state.categories.find((c) => c.id === item.categoryId)?.icon ?? "package") as IconName} />
                              </span>
                              <div style={{ minWidth: 0 }}>
                                <Link to={`/inventory?item=${item.id}`} className="cell-item__name">
                                  {item.name}
                                </Link>
                                <div className="cell-item__sub mono">{item.id}</div>
                              </div>
                            </div>
                          </td>
                          <td className="num">{num(a.issued)}</td>
                          <td className="num">{num(a.consumed)}</td>
                          <td className="num">{num(a.returned)}</td>
                          <td className="num">
                            <b style={{ color: inUse > 0 ? "var(--ink)" : "var(--muted)" }}>{num(inUse)}</b>{" "}
                            <small className="muted">{item.unit}</small>
                          </td>
                          <td style={{ width: 110 }}>
                            <Bar value={closed} tone={closed === 100 ? "green" : "olive"} />
                          </td>
                          <td className="cell-actions">
                            <RowMenu
                              items={[
                                { label: "View in inventory", icon: "eye", onClick: () => navigate(`/inventory?item=${item.id}`) },
                                {
                                  label: "Record consumption",
                                  icon: "check",
                                  hidden: !canEdit || inUse <= 0,
                                  onClick: () => setConsumeFor(item),
                                },
                                {
                                  label: "Return to store",
                                  icon: "corner-up-left",
                                  hidden: !canIssue || inUse <= 0,
                                  onClick: () => {
                                    setReturnItemId(item.id);
                                    setReturnOpen(true);
                                  },
                                },
                              ]}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="col-4">
          <Card>
            <CardHead title="Required materials" sub={`${covered} of ${totalRequired} covered by issued stock`} />
            {totalRequired === 0 ? (
              <EmptyState small icon="clipboard" title="No bill of materials" text="Edit the project to list the materials this build needs." />
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {project.required.map((r, i) => {
                  const item = r.itemId ? state.items.find((x) => x.id === r.itemId) : undefined;
                  const allocation = r.itemId ? project.allocations.find((a) => a.itemId === r.itemId) : undefined;
                  const issued = allocation?.issued ?? 0;
                  const ok = issued >= r.qty;
                  return (
                    <div
                      key={`${r.name}-${i}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 10px",
                        border: "1px solid var(--line)",
                        borderRadius: "var(--r-sm)",
                      }}
                    >
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: "block", fontSize: 11.5, fontWeight: 500 }} className="truncate">
                          {item?.name ?? r.name}
                        </span>
                        <span style={{ display: "block", fontSize: 10, color: "var(--muted)" }}>
                          Needs {num(r.qty)} {r.unit}
                          {issued > 0 ? ` · ${num(issued)} issued` : ""}
                        </span>
                      </span>
                      {ok ? <Badge tone="green">Ready</Badge> : issued > 0 ? <Badge tone="amber">Partial</Badge> : <Badge tone="slate">Pending</Badge>}
                    </div>
                  );
                })}
              </div>
            )}
            {canEdit ? (
              <Button
                variant="secondary"
                size="sm"
                icon="pencil"
                className="btn--block"
                style={{ marginTop: 14 }}
                onClick={() => setEditOpen(true)}
              >
                Edit bill of materials
              </Button>
            ) : null}
          </Card>
        </div>
      </div>

      <div className="grid">
        <div className="col-7">
          <Card>
            <CardHead
              title="Project activity"
              sub="Materials issued, returned and reconciled for this build"
              action={
                <Link to="/transactions/history" className="card__link">
                  Full ledger <Icon name="arrow-right" />
                </Link>
              }
            />
            {activity.length === 0 ? (
              <EmptyState small icon="activity" title="No activity yet" text="Movements linked to this project will appear here." />
            ) : (
              <div className="timeline">
                {activity.map((t) => {
                  const item = state.items.find((i) => i.id === t.itemId);
                  const meta = TXN_META[t.type];
                  return (
                    <div className="timeline__item" key={t.id}>
                      <span className="timeline__marker">
                        <Icon name={meta.icon} />
                      </span>
                      <div className="timeline__body">
                        <p className="timeline__title">
                          <b>{meta.label}</b> · {num(t.qty)} {item?.unit ?? "units"} of {item?.name ?? "deleted item"}
                        </p>
                        <p className="timeline__time">
                          {t.actor} · {t.id} · {relTime(t.at)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        <div className="col-5">
          <Card>
            <CardHead
              title="Linked requests"
              sub={`${requests.length} request${requests.length === 1 ? "" : "s"} raised for this project`}
              action={
                <Link to="/requests/history" className="card__link">
                  All requests <Icon name="arrow-right" />
                </Link>
              }
            />
            {requests.length === 0 ? (
              <EmptyState
                small
                icon="inbox"
                title="No requests yet"
                text="Material requests from the team will be linked here."
                action={
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="plus"
                    onClick={() => {
                      setRequestOpen(true);
                    }}
                  >
                    New request
                  </Button>
                }
              />
            ) : (
              <div className="stack" style={{ gap: 6 }}>
                {requests.slice(0, 6).map((r) => (
                  <div
                    key={r.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 9,
                      padding: "9px 10px",
                      border: "1px solid var(--line)",
                      borderRadius: "var(--r-sm)",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 500 }} className="mono">
                        {r.id}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--muted)" }}>
                        {r.requestedBy} · {r.lines.length} line{r.lines.length === 1 ? "" : "s"} · {relTime(r.createdAt)}
                      </div>
                    </div>
                    <Badge tone={requestStatusTone(r.status)}>{requestStatusLabel(r.status)}</Badge>
                  </div>
                ))}
              </div>
            )}
            {openRequests.length > 0 ? (
              <Link to="/requests/pending" className="card__link" style={{ marginTop: 12, display: "inline-flex" }}>
                {openRequests.length} open request{openRequests.length === 1 ? "" : "s"} to review <Icon name="arrow-right" />
              </Link>
            ) : null}
          </Card>

          <Card className="card--fill" style={{ marginTop: "var(--gutter)" }}>
            <CardHead title="Team" sub="Students attached to this project" />
            <div className="stack" style={{ gap: 8 }}>
              {project.team.map((member) => (
                <div key={member} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <span className="avatar avatar--sm">{member.split(" ").map((p) => p[0]).slice(0, 2).join("")}</span>
                  <span style={{ fontSize: 11.5 }}>{member}</span>
                </div>
              ))}
            </div>
            <div className="divider" style={{ margin: "14px 0" }} />
            <div className="meta-row">
              <Icon name="user" /> Supervisor <b style={{ marginLeft: "auto" }}>{project.supervisor}</b>
            </div>
            <div className="meta-row">
              <Icon name="calendar" /> Timeline <b style={{ marginLeft: "auto" }}>{dateShort(project.startDate)} → {dateShort(project.endDate)}</b>
            </div>
            <div className="meta-row">
              <Icon name="package" /> Total issued value <b style={{ marginLeft: "auto" }}>{inr(project.allocations.reduce((s, a) => s + a.issued * (state.items.find((i) => i.id === a.itemId)?.unitCost ?? 0), 0))}</b>
            </div>
          </Card>
        </div>
      </div>

      <ProjectFormModal open={editOpen} onClose={() => setEditOpen(false)} project={project} />
      <StockOutModal open={issueOpen} onClose={() => setIssueOpen(false)} projectId={project.id} />
      <ReturnModal
        open={returnOpen}
        onClose={() => {
          setReturnOpen(false);
          setReturnItemId(undefined);
        }}
        projectId={project.id}
        itemId={returnItemId}
      />
      <ConsumeModal open={Boolean(consumeFor)} onClose={() => setConsumeFor(undefined)} project={project} item={consumeFor} />
      <ConfirmDialog
        open={deleteOpen}
        title={`Delete ${project.name}?`}
        message="Deleting a project removes its allocations and requests. Projects with materials still in use or open requests cannot be deleted."
        confirmLabel="Delete project"
        onConfirm={handleDelete}
        onClose={() => setDeleteOpen(false)}
      />

      {requestOpen ? (
        <RequestFormModal open={requestOpen} onClose={() => setRequestOpen(false)} projectId={project.id} />
      ) : null}
    </>
  );
}
