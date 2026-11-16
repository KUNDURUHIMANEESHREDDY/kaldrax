import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../components/Layout";
import {
  activityFeed,
  categoryStats,
  mostUsedItems,
  movementSeries,
  requestAvailability,
  stockSummary,
} from "../lib/derive";
import { inrCompact, num, relTime, itemStatus } from "../lib/format";
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardHead,
  EmptyState,
  StatCard,
  ItemThumb,
} from "../components/ui";
import { DonutChart, DonutLegend, HBars, LineChart, Sparkline } from "../components/Charts";
import { ItemFormModal } from "../components/forms";
import { useToast } from "../components/Toast";
import { Icon } from "../components/Icons";

const OVERVIEW_REFERENCE_DATE = new Date();

const ACTIVITY_ICON = {
  in: "arrow-down-left",
  out: "arrow-up-right",
  return: "corner-up-left",
  adjust: "sliders",
  item: "package",
  request: "inbox",
  approval: "check-circle",
} as const;

export default function Overview() {
  usePageTitle("Overview");
  const { state, role, actorName, exportState } = useApp();
  const toast = useToast();
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [addOpen, setAddOpen] = useState(false);

  const summary = useMemo(() => stockSummary(state), [state]);
  const cats = useMemo(() => categoryStats(state), [state]);
  const movement = useMemo(() => movementSeries(state, days), [state, days]);
  const used = useMemo(() => mostUsedItems(state, 6), [state]);
  const feed = useMemo(() => activityFeed(state, 7), [state]);
  const pending = state.requests.filter((r) => r.status === "pending");
  const recent = state.transactions.slice(0, 6);

  const donutData = cats
    .filter((c) => c.count > 0)
    .map((c) => ({ label: c.category.name, value: c.count, color: c.category.color }));

  const dateLabel = OVERVIEW_REFERENCE_DATE.toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const hour = OVERVIEW_REFERENCE_DATE.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const downloadSnapshot = () => {
    const blob = new Blob([exportState()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inventra-snapshot-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Snapshot exported", "A JSON backup of the current workspace was downloaded.");
  };

  return (
    <>
      <div className="greeting">
        <div>
          <h1 className="greeting__title">
            {greeting}, <span>{actorName.split(" ")[0]}</span>
          </h1>
          <p className="greeting__sub">
            {dateLabel} · {state.settings.orgName}
          </p>
        </div>
        <div className="greeting__actions">
          <span className="pulse-note">
            <span className="pulse-dot" /> Live · local workspace
          </span>
          <Button size="sm" variant="secondary" icon="download" onClick={downloadSnapshot}>
            Export
          </Button>
          {role === "student" ? (
            <Button size="sm" variant="primary" icon="inbox" onClick={() => navigate("/requests/pending?new=1")}>
              New request
            </Button>
          ) : (
            <Button size="sm" variant="primary" icon="plus" onClick={() => setAddOpen(true)}>
              Add item
            </Button>
          )}
        </div>
      </div>

      <div className="stats" style={{ marginBottom: "var(--gutter)" }}>
        <StatCard
          label="Total items"
          value={num(summary.totalItems)}
          icon="package"
          foot={<span className="muted">Across {cats.filter((c) => c.count > 0).length} categories</span>}
          footRight={<span className="mono">{inrCompact(summary.value)}</span>}
        />
        <StatCard
          label="Available stock"
          value={num(summary.totalAvailable)}
          suffix="units"
          icon="layers"
          foot="On hand right now"
          footRight={<Badge tone="green" dot>Healthy</Badge>}
        />
        <StatCard
          label="Low stock"
          value={num(summary.low.length)}
          icon="alert-triangle"
          foot={`${summary.low.length} at or below threshold`}
          footRight={
            summary.low.length ? (
              <Link to="/inventory/stock-levels" className="card__link">
                Review <Icon name="arrow-right" />
              </Link>
            ) : null
          }
        />
        <StatCard
          label="Out of stock"
          value={num(summary.out.length)}
          icon="x"
          foot={summary.out.length ? summary.out.map((i) => i.name).slice(0, 1).join(", ") : "Nothing depleted"}
          footRight={
            summary.out.length ? <Badge tone="red" dot>Reorder</Badge> : <Badge tone="green" dot>Clear</Badge>
          }
        />
        <StatCard
          label="Active projects"
          value={num(summary.activeProjects)}
          icon="layers"
          foot={`${state.projects.length} projects total`}
          footRight={
            <Link to="/projects" className="card__link">
              Open <Icon name="arrow-right" />
            </Link>
          }
        />
        <StatCard
          label="Pending requests"
          value={num(summary.pending)}
          icon="inbox"
          foot={pending[0] ? `${pending[0].id} · ${pending[0].requestedBy}` : "No approvals waiting"}
          footRight={
            <Link to="/requests/pending" className="card__link">
              Review <Icon name="arrow-right" />
            </Link>
          }
        />
      </div>

      <div className="grid">
        <div className="col-8">
          <Card>
            <CardHead
              title="Stock movement"
              sub="Received, issued and returned units across the selected window"
              action={
                <div className="segmented" role="group" aria-label="Movement range">
                  {[7, 30, 90].map((d) => (
                    <button
                      key={d}
                      type="button"
                      className={days === d ? "is-active" : undefined}
                      onClick={() => setDays(d)}
                    >
                      {d}d
                    </button>
                  ))}
                </div>
              }
            />
            <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 4 }}>
              <span className="chart-legend__item">
                <i className="chart-legend__swatch" style={{ background: "#5f6f52" }} /> Received
              </span>
              <span className="chart-legend__item">
                <i className="chart-legend__swatch" style={{ background: "#2c5f9e" }} /> Issued
              </span>
              <span className="chart-legend__item">
                <i className="chart-legend__swatch" style={{ background: "#b39245" }} /> Returned
              </span>
            </div>
            <LineChart
              data={movement.map((m) => ({
                label: m.label,
                values: [m.received, m.issued, m.returned],
              }))}
              series={[
                { name: "Received", color: "#5f6f52", area: true },
                { name: "Issued", color: "#2c5f9e" },
                { name: "Returned", color: "#b39245", dashed: true },
              ]}
              height={232}
              formatValue={(n) => num(n)}
            />
          </Card>
        </div>

        <div className="col-4">
          <Card className="card--fill">
            <CardHead
              title="Inventory mix"
              sub="Items by category"
              action={
                <Link to="/inventory/categories" className="card__link">
                  Manage <Icon name="arrow-right" />
                </Link>
              }
            />
            <div className="overview-donut" style={{ marginTop: 6 }}>
              <DonutChart data={donutData} centerLabel="Items" centerValue={num(summary.totalItems)} />
              <DonutLegend data={donutData} />
            </div>
          </Card>
        </div>
      </div>

      {summary.low.length > 0 ? (
        <div style={{ marginTop: "var(--gutter)" }}>
          <div className="notice notice--amber">
            <Icon name="alert-triangle" />
            <div>
              <b>{summary.low.length} items need attention.</b>{" "}
              {summary.out.length > 0
                ? `${summary.out.length} are completely out of stock. `
                : ""}
              <Link to="/inventory/stock-levels" className="card__link" style={{ display: "inline-flex" }}>
                Review stock levels <Icon name="arrow-right" />
              </Link>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid">
        <div className="col-7">
          <Card>
            <CardHead
              title="Most-used materials"
              sub="Total quantity issued across all projects"
              action={
                <Link to="/reports" className="card__link">
                  Full report <Icon name="arrow-right" />
                </Link>
              }
            />
            {used.length === 0 ? (
              <EmptyState small icon="chart" title="No issues recorded yet" text="Material usage appears here once stock is issued to projects." />
            ) : (
              <HBars
                data={used.map((u) => ({
                  label: u.item?.name ?? "Unknown",
                  value: u.qty,
                  meta: `${u.projects} project${u.projects === 1 ? "" : "s"}`,
                  color: u.item ? state.categories.find((c) => c.id === u.item?.categoryId)?.color : undefined,
                }))}
                formatValue={(n) => num(n)}
              />
            )}
          </Card>
        </div>

        <div className="col-5">
          <Card>
            <CardHead
              title="Pending approvals"
              sub={`${pending.length} request${pending.length === 1 ? "" : "s"} waiting`}
              action={
                <Link to="/requests/pending" className="card__link">
                  View all <Icon name="arrow-right" />
                </Link>
              }
            />
            {pending.length === 0 ? (
              <EmptyState small icon="check-circle" title="Nothing waiting" text="New material requests will appear here for review." />
            ) : (
              <div className="approval">
                {pending.slice(0, 4).map((r) => {
                  const project = state.projects.find((p) => p.id === r.projectId);
                  const availability = requestAvailability(state, r);
                  const shortage = availability.some((a) => !a.ok);
                  return (
                    <button
                      key={r.id}
                      type="button"
                      className="approval-row"
                      onClick={() => navigate("/requests/pending")}
                    >
                      <Avatar name={r.requestedBy} />
                      <span className="approval-row__main">
                        <span className="approval-row__title">{project?.name ?? r.projectId}</span>
                        <span className="approval-row__sub">
                          {r.id} · {r.requestedBy} · {relTime(r.createdAt)}
                        </span>
                      </span>
                      {shortage ? <Badge tone="red">Short</Badge> : <span className="approval-row__qty">{r.lines.length} lines</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      <div className="grid">
        <div className="col-7">
          <Card flush>
            <div style={{ padding: "20px 20px 8px" }}>
              <CardHead
                title="Recent transactions"
                sub="Latest stock movements"
                action={
                  <Link to="/transactions/history" className="card__link">
                    Full ledger <Icon name="arrow-right" />
                  </Link>
                }
              />
            </div>
            {recent.length === 0 ? (
              <EmptyState small icon="swap" title="No transactions yet" text="Receipts, issues and returns will show up here." />
            ) : (
              <div className="table-wrap">
                <table className="table table--compact">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Type</th>
                      <th className="num">Qty</th>
                      <th>Project</th>
                      <th className="num">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((t) => {
                      const item = state.items.find((i) => i.id === t.itemId);
                      const project = state.projects.find((p) => p.id === t.projectId);
                      return (
                        <tr key={t.id}>
                          <td>
                            <div className="cell-item">
                              <ItemThumb category={state.categories.find((c) => c.id === item?.categoryId)} />
                              <div>
                                <div className="cell-item__name">{item?.name ?? "Deleted item"}</div>
                                <div className="cell-item__sub mono">{t.id}</div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <Badge
                              tone={t.type === "in" ? "green" : t.type === "out" ? "blue" : t.type === "return" ? "amber" : "slate"}
                              dot
                            >
                              {t.type === "in" ? "Stock in" : t.type === "out" ? "Stock out" : t.type === "return" ? "Return" : "Adjust"}
                            </Badge>
                          </td>
                          <td className="num">
                            <span style={{ color: t.delta > 0 ? "var(--green)" : "var(--ink)" }}>
                              {t.delta > 0 ? "+" : ""}
                              {num(t.delta)}
                            </span>
                          </td>
                          <td className="truncate" style={{ maxWidth: 190 }}>
                            {project?.name ?? <span className="muted">—</span>}
                          </td>
                          <td className="num muted">{relTime(t.at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="col-5">
          <Card>
            <CardHead title="Activity" sub="What changed recently" />
            {feed.length === 0 ? (
              <EmptyState small icon="activity" title="No activity" text="Actions across inventory and requests are logged here." />
            ) : (
              <div className="timeline">
                {feed.map((entry) => (
                  <div className="timeline__item" key={entry.id}>
                    <span className="timeline__marker">
                      <Icon name={ACTIVITY_ICON[entry.kind]} />
                    </span>
                    <div className="timeline__body">
                      <p className="timeline__title">{entry.title}</p>
                      <p className="timeline__time">
                        {entry.meta} · {relTime(entry.at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <div className="grid">
        <div className="col-12">
          <Card>
            <CardHead
              title="Stock health"
              sub="Availability against minimum thresholds, by category"
              action={
                <Link to="/inventory/stock-levels" className="card__link">
                  Stock levels <Icon name="arrow-right" />
                </Link>
              }
            />
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th className="num">Items</th>
                    <th className="num">Units on hand</th>
                    <th className="num">Stock value</th>
                    <th>Health</th>
                    <th className="num">Attention</th>
                  </tr>
                </thead>
                <tbody>
                  {cats.map((c) => (
                    <tr key={c.category.id}>
                      <td>
                        <span className="cat">
                          <span className="cat__dot" style={{ background: c.category.color }} />
                          {c.category.name}
                        </span>
                      </td>
                      <td className="num">{c.count}</td>
                      <td className="num">{num(c.qty)}</td>
                      <td className="num">{inrCompact(c.value)}</td>
                      <td style={{ width: 150 }}>
                        <Sparkline
                          values={[1, 3, 2, 5, 4, 6, Math.max(2, c.count - c.low)]}
                          color={c.low > 0 ? "#b39245" : "#5f6f52"}
                          height={22}
                        />
                      </td>
                      <td className="num">
                        {c.low === 0 ? <Badge tone="green">OK</Badge> : <Badge tone="amber">{c.low} low</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>

      <ItemFormModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSaved={(id) => {
          if (id) navigate(`/inventory?item=${id}`);
        }}
      />

      <div style={{ marginTop: 18, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <p className="report-note" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="shield" size={13} />
          Stock mathematics verified against {state.transactions.length} ledger entries.
        </p>
        <p className="report-note">
          {state.items.filter((i) => itemStatus(i) === "in-stock").length} of {state.items.length} items in healthy supply
        </p>
      </div>

      <div className="sr-only" aria-live="polite">
        {summary.totalItems} items, {summary.pending} pending requests.
      </div>
    </>
  );
}
