import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  AvatarStack,
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  PageHead,
  RowMenu,
  SearchField,
  Segments,
} from "../components/ui";
import { ProjectFormModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { projectStats } from "../lib/derive";
import { dateShort, inrCompact, projectStatusLabel, projectStatusTone } from "../lib/format";
import { canDeleteRecords, canManageProjects } from "../lib/permissions";
import type { Project, ProjectStatus } from "../lib/types";

const STATUS_FILTERS: Array<{ value: ProjectStatus | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "planning", label: "Planning" },
  { value: "on-hold", label: "On hold" },
  { value: "completed", label: "Completed" },
];

export default function Projects() {
  usePageTitle("Projects");
  const { state, role, deleteProject } = useApp();
  const toast = useToast();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ProjectStatus | "all">("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Project | undefined>();
  const [deleteFor, setDeleteFor] = useState<Project | undefined>();

  const canEdit = canManageProjects(role);
  const canDelete = canDeleteRecords(role);

  const counts = useMemo(() => {
    const map = new Map<ProjectStatus, number>();
    state.projects.forEach((p) => map.set(p.status, (map.get(p.status) ?? 0) + 1));
    return map;
  }, [state.projects]);

  const projects = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.projects.filter((p) => {
      if (status !== "all" && p.status !== status) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.id.toLowerCase().includes(q) ||
        p.supervisor.toLowerCase().includes(q) ||
        p.team.some((t) => t.toLowerCase().includes(q)) ||
        p.description.toLowerCase().includes(q)
      );
    });
  }, [state.projects, query, status]);

  const handleDelete = () => {
    if (!deleteFor) return;
    const result = deleteProject(deleteFor.id);
    if (!result.ok) toast.error("Project not deleted", result.message);
    else toast.success("Project deleted", `${deleteFor.name} was removed.`);
    setDeleteFor(undefined);
  };

  return (
    <>
      <PageHead
        title="Projects"
        sub="PBL teams, their supervisors and the materials issued to each build."
        actions={
          canEdit ? (
            <Button
              variant="primary"
              size="sm"
              icon="plus"
              onClick={() => {
                setEditing(undefined);
                setFormOpen(true);
              }}
            >
              New project
            </Button>
          ) : null
        }
      />

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
        <Segments
          items={[
            { to: "/projects", label: "All projects", end: true },
            { to: "/projects/inventory", label: "Project inventory" },
          ]}
        />
        <span className="spacer" />
        <SearchField value={query} onChange={setQuery} placeholder="Search projects, supervisors or team…" />
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 18 }}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            className={`filter-chip${status === f.value ? " is-active" : ""}`}
            style={
              status === f.value
                ? { background: "var(--ink)", borderColor: "var(--ink)", color: "#fff" }
                : undefined
            }
            onClick={() => setStatus(f.value)}
          >
            {f.label}
            <span className="segmented__count" style={{ opacity: 0.7 }}>
              {f.value === "all" ? state.projects.length : counts.get(f.value) ?? 0}
            </span>
          </button>
        ))}
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon="layers"
          title="No projects match"
          text="Try another status filter, or create a new project to start tracking materials."
          action={
            canEdit ? (
              <Button size="sm" variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                New project
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="project-grid">
          {projects.map((project) => {
            const stats = projectStats(state, project);
            const openRequests = state.requests.filter(
              (r) => r.projectId === project.id && (r.status === "pending" || r.status === "approved")
            ).length;
            return (
              <article className="project-card" key={project.id}>
                <div className="project-card__top">
                  <span
                    className="cat-card__glyph"
                    style={{ background: "var(--olive-soft)", color: "var(--olive)" }}
                  >
                    <Icon name="layers" />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="project-card__code">{project.id}</div>
                    <Link to={`/projects/${project.id}`} className="project-card__title" style={{ display: "block" }}>
                      {project.name}
                    </Link>
                  </div>
                  {canEdit ? (
                    <RowMenu
                      items={[
                        { label: "Open project", icon: "eye", onClick: () => navigate(`/projects/${project.id}`) },
                        {
                          label: "Edit project",
                          icon: "pencil",
                          onClick: () => {
                            setEditing(project);
                            setFormOpen(true);
                          },
                        },
                        {
                          label: "Delete",
                          icon: "trash",
                          danger: true,
                          hidden: !canDelete,
                          onClick: () => setDeleteFor(project),
                        },
                      ]}
                    />
                  ) : null}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <Badge tone={projectStatusTone(project.status)} dot>
                    {projectStatusLabel(project.status)}
                  </Badge>
                  {openRequests > 0 ? <Badge tone="amber">{openRequests} open request{openRequests === 1 ? "" : "s"}</Badge> : null}
                  {stats.inUse > 0 ? <Badge outline>{stats.inUse} units in use</Badge> : null}
                </div>

                <p className="project-card__desc">{project.description}</p>

                <div className="project-card__progress">
                  <div className="project-card__progress-label">
                    <span>Materials consumed or returned</span>
                    <b>{stats.progress}%</b>
                  </div>
                  <span className="bar">
                    <span
                      className="bar__fill bar__fill--olive"
                      style={{ width: `${Math.max(stats.progress, stats.issued > 0 ? 4 : 0)}%` }}
                    />
                  </span>
                </div>

                <div className="project-card__foot">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                    <AvatarStack names={project.team} max={3} />
                    <span className="truncate" style={{ maxWidth: 150 }}>
                      {project.supervisor}
                    </span>
                  </div>
                  <span title={`${dateShort(project.startDate)} → ${dateShort(project.endDate)}`}>
                    {dateShort(project.startDate)} → {dateShort(project.endDate)}
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    fontSize: 10.5,
                    color: "var(--muted)",
                    borderTop: "1px solid var(--line)",
                    paddingTop: 10,
                  }}
                >
                  <span>{stats.lines} materials tracked</span>
                  <span>
                    <b style={{ color: "var(--ink-2)", fontWeight: 500 }}>{inrCompact(stats.consumedValue)}</b> consumed
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <ProjectFormModal
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditing(undefined);
        }}
        project={editing}
      />

      <ConfirmDialog
        open={Boolean(deleteFor)}
        title={`Delete ${deleteFor?.name ?? "project"}?`}
        message="Deleting a project removes its material allocations and open requests. Projects with materials still in use or open requests must be cleared first."
        confirmLabel="Delete project"
        onConfirm={handleDelete}
        onClose={() => setDeleteFor(undefined)}
      />
    </>
  );
}
