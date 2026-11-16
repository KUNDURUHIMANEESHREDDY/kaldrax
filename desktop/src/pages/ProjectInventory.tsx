import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store/useApp";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  Badge,
  Bar,
  Button,
  Card,
  EmptyState,
  PageHead,
  Pagination,
  SearchField,
  Segments,
  SortTh,
} from "../components/ui";
import { ReturnModal, StockOutModal } from "../components/forms";
import { Icon, type IconName } from "../components/Icons";
import { projectStats } from "../lib/derive";
import { inrCompact, num, projectStatusLabel, projectStatusTone } from "../lib/format";
import { canManageInventory } from "../lib/permissions";

type SortKey = "project" | "item" | "issued" | "inUse" | "value";

export default function ProjectInventory() {
  usePageTitle("Project inventory");
  const { state, role } = useApp();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("issued");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const [issueOpen, setIssueOpen] = useState(false);
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnProjectId, setReturnProjectId] = useState<string | undefined>();

  const canIssue = canManageInventory(role);

  const totals = useMemo(() => {
    let issued = 0;
    let consumed = 0;
    let returned = 0;
    let consumedValue = 0;
    let inUseValue = 0;
    state.projects.forEach((p) => {
      const s = projectStats(state, p);
      issued += s.issued;
      consumed += s.consumed;
      returned += s.returned;
      consumedValue += s.consumedValue;
      p.allocations.forEach((a) => {
        const item = state.items.find((i) => i.id === a.itemId);
        inUseValue += Math.max(0, a.issued - a.consumed - a.returned) * (item?.unitCost ?? 0);
      });
    });
    return { issued, consumed, returned, consumedValue, inUse: issued - consumed - returned, inUseValue };
  }, [state]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = state.projects.flatMap((project) =>
      project.allocations.map((allocation) => {
        const item = state.items.find((i) => i.id === allocation.itemId);
        return {
          key: `${project.id}-${allocation.itemId}`,
          project,
          allocation,
          item,
          inUse: allocation.issued - allocation.consumed - allocation.returned,
          value: Math.max(0, allocation.issued - allocation.consumed - allocation.returned) * (item?.unitCost ?? 0),
        };
      })
    );

    const filtered = out.filter((row) => {
      if (projectFilter !== "all" && row.project.id !== projectFilter) return false;
      if (!q) return true;
      return (
        (row.item?.name ?? "").toLowerCase().includes(q) ||
        (row.item?.id ?? "").toLowerCase().includes(q) ||
        row.project.name.toLowerCase().includes(q) ||
        row.project.id.toLowerCase().includes(q)
      );
    });

    const dir = sortDir === "asc" ? 1 : -1;
    filtered.sort((a, b) => {
      switch (sortKey) {
        case "item":
          return (a.item?.name ?? "").localeCompare(b.item?.name ?? "") * dir;
        case "inUse":
          return (a.inUse - b.inUse) * dir;
        case "value":
          return (a.value - b.value) * dir;
        case "project":
          return a.project.name.localeCompare(b.project.name) * dir;
        default:
          return (a.allocation.issued - b.allocation.issued) * dir;
      }
    });
    return filtered;
  }, [state.projects, state.items, query, projectFilter, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visible = rows.slice((safePage - 1) * pageSize, safePage * pageSize);

  const sort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "issued" || key === "inUse" || key === "value" ? "desc" : "asc");
    }
  };

  return (
    <>
      <PageHead
        title="Project inventory"
        sub="Every material committed to a PBL team, with consumption and returns reconciled."
        actions={
          canIssue ? (
            <>
              <Button variant="secondary" size="sm" icon="corner-up-left" onClick={() => setReturnOpen(true)}>
                Record return
              </Button>
              <Button variant="primary" size="sm" icon="upload" onClick={() => setIssueOpen(true)}>
                Issue materials
              </Button>
            </>
          ) : (
            <Badge tone="slate" lg>
              Read-only access
            </Badge>
          )
        }
      />

      <div className="filter-bar">
        <Segments
          items={[
            { to: "/projects", label: "All projects", end: true },
            { to: "/projects/inventory", label: "Project inventory" },
          ]}
        />
      </div>

      <div className="mini-stats" style={{ marginBottom: "var(--gutter)" }}>
        <div className="mini-stat">
          <span>Issued to projects</span>
          <b>
            {num(totals.issued)} <small>units</small>
          </b>
          <em>Across {state.projects.length} projects</em>
        </div>
        <div className="mini-stat">
          <span>Consumed</span>
          <b>
            {num(totals.consumed)} <small>units</small>
          </b>
          <em>{inrCompact(totals.consumedValue)} of material used</em>
        </div>
        <div className="mini-stat">
          <span>Returned</span>
          <b>
            {num(totals.returned)} <small>units</small>
          </b>
          <em>Reconciled back into stock</em>
        </div>
        <div className="mini-stat">
          <span>Still in use</span>
          <b style={{ color: totals.inUse > 0 ? "var(--blue)" : undefined }}>
            {num(totals.inUse)} <small>units</small>
          </b>
          <em>{inrCompact(totals.inUseValue)} committed value</em>
        </div>
      </div>

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search project or material…"
          className="toolbar__search"
        />
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={projectFilter}
            onChange={(e) => {
              setProjectFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by project"
          >
            <option value="all">All projects</option>
            {state.projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        {(query || projectFilter !== "all") && (
          <Button
            variant="ghost"
            size="sm"
            icon="refresh"
            onClick={() => {
              setQuery("");
              setProjectFilter("all");
              setPage(1);
            }}
          >
            Clear
          </Button>
        )}
        <span className="toolbar__spacer" />
        <span className="filter-count">{rows.length} allocation lines</span>
      </div>

      <Card flush>
        {rows.length === 0 ? (
          <EmptyState
            icon="layers"
            title="No allocations match"
            text="Issue materials to a project and the commitment will show up here."
            action={
              canIssue ? (
                <Button size="sm" variant="primary" icon="upload" onClick={() => setIssueOpen(true)}>
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
                  <SortTh label="Project" active={sortKey === "project"} dir={sortDir} onClick={() => sort("project")} />
                  <SortTh label="Material" active={sortKey === "item"} dir={sortDir} onClick={() => sort("item")} />
                  <SortTh label="Issued" active={sortKey === "issued"} dir={sortDir} onClick={() => sort("issued")} align="right" />
                  <th className="num">Consumed</th>
                  <th className="num">Returned</th>
                  <SortTh label="In use" active={sortKey === "inUse"} dir={sortDir} onClick={() => sort("inUse")} align="right" />
                  <SortTh label="Value" active={sortKey === "value"} dir={sortDir} onClick={() => sort("value")} align="right" />
                  <th>Closure</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  const { project, allocation, item, inUse } = row;
                  const closed = allocation.issued > 0 ? Math.round(((allocation.consumed + allocation.returned) / allocation.issued) * 100) : 0;
                  return (
                    <tr key={row.key}>
                      <td>
                        <Link to={`/projects/${project.id}`} style={{ display: "block" }}>
                          <div className="cell-item__name">{project.name}</div>
                          <div className="cell-item__sub mono">{project.id}</div>
                        </Link>
                      </td>
                      <td>
                        <div className="cell-item">
                          <span
                            className="thumb thumb--sm"
                            style={{
                              background: `${state.categories.find((c) => c.id === item?.categoryId)?.color ?? "#757575"}14`,
                              color: state.categories.find((c) => c.id === item?.categoryId)?.color,
                            }}
                          >
                            <Icon name={(state.categories.find((c) => c.id === item?.categoryId)?.icon ?? "package") as IconName} />
                          </span>
                          <div style={{ minWidth: 0 }}>
                            <div className="cell-item__name">{item?.name ?? "Deleted item"}</div>
                            <div className="cell-item__sub mono">{item?.id ?? "—"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">{num(allocation.issued)}</td>
                      <td className="num">{num(allocation.consumed)}</td>
                      <td className="num">{num(allocation.returned)}</td>
                      <td className="num">
                        <b style={{ color: inUse > 0 ? "var(--ink)" : "var(--muted)" }}>{num(inUse)}</b>{" "}
                        <small className="muted">{item?.unit}</small>
                      </td>
                      <td className="num">{inrCompact(row.value)}</td>
                      <td style={{ width: 120 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                          <Bar value={closed} tone={closed === 100 ? "green" : "olive"} />
                          <span style={{ fontSize: 10, color: "var(--muted)" }}>{closed}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {rows.length > 0 ? (
          <Pagination
            page={safePage}
            pageSize={pageSize}
            total={rows.length}
            onPage={setPage}
            onPageSize={(n) => {
              setPageSize(n);
              setPage(1);
            }}
          />
        ) : null}
      </Card>

      <div style={{ marginTop: "var(--gutter)" }} className="grid">
        <div className="col-12">
          <Card flush>
            <div style={{ padding: "18px 18px 8px" }}>
              <h2 className="card__title">Commitment by project</h2>
              <p className="card__sub">Issued value still held by each team</p>
            </div>
            <div className="table-wrap">
              <table className="table table--compact">
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Status</th>
                    <th className="num">Materials</th>
                    <th className="num">Issued</th>
                    <th className="num">In use</th>
                    <th className="num">Consumed value</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {state.projects.map((p) => {
                    const s = projectStats(state, p);
                    return (
                      <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)} style={{ cursor: "pointer" }}>
                        <td>
                          <div className="cell-item__name">{p.name}</div>
                          <div className="cell-item__sub mono">{p.id}</div>
                        </td>
                        <td>
                          <Badge tone={projectStatusTone(p.status)} dot>
                            {projectStatusLabel(p.status)}
                          </Badge>
                        </td>
                        <td className="num">{s.lines}</td>
                        <td className="num">{num(s.issued)}</td>
                        <td className="num">{num(s.inUse)}</td>
                        <td className="num">{inrCompact(s.consumedValue)}</td>
                        <td className="cell-actions">
                          {canIssue ? (
                            <span
                              className="card__link"
                              onClick={(e) => {
                                e.stopPropagation();
                                setReturnProjectId(p.id);
                                setReturnOpen(true);
                              }}
                            >
                              Return
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>

      <StockOutModal open={issueOpen} onClose={() => setIssueOpen(false)} />
      <ReturnModal
        open={returnOpen}
        onClose={() => {
          setReturnOpen(false);
          setReturnProjectId(undefined);
        }}
        projectId={returnProjectId}
      />
    </>
  );
}
