import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../store/useApp";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  Badge,
  Button,
  Card,
  CardHead,
  EmptyState,
  MiniStat,
  PageHead,
  Select,
  StatCard,
  SortTh,
} from "../components/ui";
import { DonutChart, DonutLegend, HBars, LineChart } from "../components/Charts";
import { Icon } from "../components/Icons";
import {
  categoryStats,
  consumptionByCategory,
  monthlyMovement,
  mostUsedItems,
  projectStats,
  stockSummary,
  supplierStats,
} from "../lib/derive";
import { inr, inrCompact, num, pct } from "../lib/format";
import { canViewReports } from "../lib/permissions";
import type { Project } from "../lib/types";

const MONTH_OPTIONS = [3, 6, 12];

function csvEscape(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  usePageTitle("Reports & analytics");
  const { state, role, exportState } = useApp();
  const toast = useToast();
  const [months, setMonths] = useState(6);
  const [projectSort, setProjectSort] = useState<"value" | "consumed" | "inUse">("value");
  const [projectDir, setProjectDir] = useState<"asc" | "desc">("desc");

  const allowed = canViewReports(role);

  const summary = useMemo(() => stockSummary(state), [state]);
  const cats = useMemo(() => categoryStats(state), [state]);
  const movement = useMemo(() => monthlyMovement(state, months), [state, months]);
  const consumption = useMemo(() => consumptionByCategory(state), [state]);
  const used = useMemo(() => mostUsedItems(state, 6), [state]);
  const suppliers = useMemo(
    () =>
      state.suppliers
        .map((s) => ({ supplier: s, ...supplierStats(state, s) }))
        .sort((a, b) => b.value - a.value),
    [state]
  );

  const projectRows = useMemo(() => {
    const rows = state.projects.map((project: Project) => ({ project, ...projectStats(state, project) }));
    const direction = projectDir === "asc" ? 1 : -1;
    return rows.sort((a, b) => {
      if (projectSort === "consumed") return (a.consumed - b.consumed) * direction;
      if (projectSort === "inUse") return (a.inUse - b.inUse) * direction;
      return (a.consumedValue - b.consumedValue) * direction;
    });
  }, [state, projectSort, projectDir]);

  const totals = useMemo(() => {
    const received = movement.reduce((s, m) => s + m.received, 0);
    const issued = movement.reduce((s, m) => s + m.issued, 0);
    const returned = movement.reduce((s, m) => s + m.returned, 0);
    const consumedValue = projectRows.reduce((s, r) => s + r.consumedValue, 0);
    return { received, issued, returned, consumedValue };
  }, [movement, projectRows]);

  const chartData = movement.map((m) => ({ label: m.label, values: [m.received, m.issued, m.returned] }));

  const donutData = consumption
    .filter((c) => c.value > 0)
    .map((c) => ({ label: c.category.name, value: Math.round(c.value), color: c.category.color }));

  const maxCategoryValue = Math.max(1, ...cats.map((c) => c.value));

  const exportValuation = () => {
    const header = ["Category", "Items", "Units on hand", "Value (INR)", "Share of value", "Below threshold"];
    const lines = cats.map((c) =>
      [
        csvEscape(c.category.name),
        c.count,
        c.qty,
        Math.round(c.value),
        `${pct(c.value, summary.value)}%`,
        c.low,
      ].join(",")
    );
    lines.push(
      ["Total", summary.totalItems, summary.totalAvailable, Math.round(summary.value), "100%", summary.low.length].join(",")
    );
    download(
      `inventra-valuation-${new Date().toISOString().slice(0, 10)}.csv`,
      [header.join(","), ...lines].join("\n"),
      "text/csv;charset=utf-8"
    );
    toast.success("Valuation exported", "Category valuation was downloaded as a CSV file.");
  };

  const exportJson = () => {
    download(
      `inventra-report-${new Date().toISOString().slice(0, 10)}.json`,
      exportState(),
      "application/json"
    );
    toast.success("Workspace exported", "A full JSON snapshot of inventory, projects and requests was downloaded.");
  };

  if (!allowed) {
    return (
      <>
        <PageHead title="Reports & analytics" sub="Restricted workspace." />
        <EmptyState
          icon="lock"
          title="Reports are restricted"
          text="Students can browse inventory and submit material requests. Ask an administrator for an export if you need the numbers."
        />
        <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
          <Link to="/inventory" className="btn btn--secondary btn--sm">
            <Icon name="package" /> Browse inventory
          </Link>
          <Link to="/requests/pending" className="btn btn--secondary btn--sm">
            <Icon name="inbox" /> My requests
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Reports & analytics"
        sub="Valuation, movement and consumption across the PBL materials store."
        actions={
          <>
            <Button size="sm" icon="download" onClick={exportValuation}>
              Export CSV
            </Button>
            <Button size="sm" variant="primary" icon="file" onClick={exportJson}>
              Full snapshot
            </Button>
          </>
        }
      />

      <div className="report-kpis">
        <StatCard
          label="Stock valuation"
          value={inrCompact(summary.value)}
          icon="database"
          foot={`${num(summary.totalItems)} items · ${num(summary.totalAvailable)} units`}
          footRight={<Badge tone="plain">at cost</Badge>}
        />
        <StatCard
          label={`Received · ${months} mo`}
          value={num(totals.received)}
          suffix="units"
          icon="arrow-down"
          foot="Goods received from suppliers"
        />
        <StatCard
          label={`Issued · ${months} mo`}
          value={num(totals.issued)}
          suffix="units"
          icon="arrow-up"
          foot={`${num(totals.returned)} returned to store`}
        />
        <StatCard
          label="Consumed value"
          value={inrCompact(totals.consumedValue)}
          icon="trend"
          foot="Across all projects"
          footRight={<Badge tone="olive">materials</Badge>}
        />
      </div>

      <div className="grid" style={{ marginBottom: "var(--gutter)" }}>
        <Card className="col-8">
          <CardHead
            title="Stock movement"
            sub="Units received, issued and returned per month."
            action={
              <div style={{ width: 128 }}>
                <Select
                  value={months}
                  aria-label="Reporting period"
                  onChange={(e) => setMonths(Number(e.target.value))}
                  style={{ height: 30, fontSize: 11 }}
                >
                  {MONTH_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      Last {m} months
                    </option>
                  ))}
                </Select>
              </div>
            }
          />
          <LineChart
            data={chartData}
            series={[
              { name: "Received", color: "#5f6f52", area: true },
              { name: "Issued", color: "#b4763f" },
              { name: "Returned", color: "#6b7f9e" },
            ]}
            height={252}
            formatValue={(n) => `${num(n)}`}
          />
          <div className="chart-legend">
            {[
              { name: "Received", color: "#5f6f52" },
              { name: "Issued", color: "#b4763f" },
              { name: "Returned", color: "#6b7f9e" },
            ].map((s) => (
              <span key={s.name} className="chart-legend__item">
                <span className="chart-legend__swatch" style={{ background: s.color }} />
                {s.name}
              </span>
            ))}
          </div>
        </Card>

        <Card className="col-4">
          <CardHead title="Consumption by category" sub="Issued material value." />
          {donutData.length === 0 ? (
            <EmptyState small icon="pie" title="No issues yet" text="Category consumption appears once materials are issued." />
          ) : (
            <div className="overview-donut">
              <DonutChart
                data={donutData}
                size={158}
                centerLabel="Issued value"
                centerValue={inrCompact(donutData.reduce((s, d) => s + d.value, 0))}
              />
              <DonutLegend data={donutData} />
            </div>
          )}
        </Card>

        <Card className="col-6">
          <CardHead
            title="Most-used materials"
            sub="Ranked by total units issued to projects."
            action={
              <Link to="/inventory" className="card__link">
                Inventory <Icon name="arrow-right" />
              </Link>
            }
          />
          {used.length === 0 ? (
            <EmptyState small icon="package" title="Nothing issued yet" />
          ) : (
            <HBars
              data={used.map((u) => ({
                label: u.item?.name ?? "Deleted item",
                value: u.qty,
                meta: `${u.movements} movements · ${u.projects} project${u.projects === 1 ? "" : "s"}`,
              }))}
              formatValue={(n) => `${num(n)}`}
            />
          )}
        </Card>

        <Card className="col-6">
          <CardHead
            title="Supplier performance"
            sub="Stock value held and delivery reliability."
            action={
              <Link to="/suppliers" className="card__link">
                Suppliers <Icon name="arrow-right" />
              </Link>
            }
          />
          <div className="table-wrap">
            <table className="table table--compact">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th className="num">Value</th>
                  <th>On-time</th>
                  <th className="num">Lead</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.slice(0, 6).map(({ supplier, value, items }) => (
                  <tr key={supplier.id}>
                    <td>
                      <Link to="/suppliers" className="cell-title" style={{ fontWeight: 500 }}>
                        {supplier.name}
                      </Link>
                      <div className="cell-sub">{items.length} items · {supplier.city}</div>
                    </td>
                    <td className="num">{inrCompact(value)}</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="bar" style={{ width: 46 }}>
                          <span
                            className={`bar__fill${supplier.onTimePct >= 92 ? " bar__fill--green" : supplier.onTimePct >= 80 ? " bar__fill--amber" : " bar__fill--red"}`}
                            style={{ width: `${supplier.onTimePct}%` }}
                          />
                        </span>
                        <span className="num" style={{ fontSize: 10.5 }}>
                          {supplier.onTimePct}%
                        </span>
                      </div>
                    </td>
                    <td className="num muted">{supplier.leadTimeDays}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="col-12">
          <CardHead
            title="Project consumption"
            sub="What each PBL team has drawn from the store."
            action={
              <Link to="/projects/inventory" className="card__link">
                Project inventory <Icon name="arrow-right" />
              </Link>
            }
          />
          <div className="mini-stats" style={{ marginBottom: 16 }}>
            <MiniStat label="Projects" value={state.projects.length} hint={`${summary.activeProjects} active`} />
            <MiniStat label="Units in use" value={num(projectRows.reduce((s, r) => s + r.inUse, 0))} hint="Issued but not consumed" />
            <MiniStat label="Consumed" value={num(projectRows.reduce((s, r) => s + r.consumed, 0))} hint="Written off to builds" />
            <MiniStat label="Returned" value={num(projectRows.reduce((s, r) => s + r.returned, 0))} hint="Back in stock" />
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Supervisor</th>
                  <th className="num">Issued</th>
                  <SortTh
                    label="Consumed"
                    align="right"
                    active={projectSort === "consumed"}
                    dir={projectDir}
                    onClick={() => {
                      setProjectSort("consumed");
                      setProjectDir((d) => (d === "asc" ? "desc" : "asc"));
                    }}
                  />
                  <th className="num">Returned</th>
                  <SortTh
                    label="In use"
                    align="right"
                    active={projectSort === "inUse"}
                    dir={projectDir}
                    onClick={() => {
                      setProjectSort("inUse");
                      setProjectDir((d) => (d === "asc" ? "desc" : "asc"));
                    }}
                  />
                  <SortTh
                    label="Consumed value"
                    align="right"
                    active={projectSort === "value"}
                    dir={projectDir}
                    onClick={() => {
                      setProjectSort("value");
                      setProjectDir((d) => (d === "asc" ? "desc" : "asc"));
                    }}
                  />
                </tr>
              </thead>
              <tbody>
                {projectRows.map((row) => (
                  <tr key={row.project.id}>
                    <td>
                      <Link to={`/projects/${row.project.id}`} className="cell-title">
                        {row.project.name}
                      </Link>
                      <div className="cell-sub mono">{row.project.id}</div>
                    </td>
                    <td className="muted truncate" style={{ maxWidth: 160 }}>
                      {row.project.supervisor}
                    </td>
                    <td className="num">{num(row.issued)}</td>
                    <td className="num">{num(row.consumed)}</td>
                    <td className="num muted">{num(row.returned)}</td>
                    <td className="num">{num(row.inUse)}</td>
                    <td className="num">{inr(row.consumedValue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="col-12">
          <CardHead
            title="Inventory valuation"
            sub="Working capital tied up per category at current unit cost."
            action={
              <Button size="sm" icon="download" onClick={exportValuation}>
                CSV
              </Button>
            }
          />
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="num">Items</th>
                  <th className="num">Units on hand</th>
                  <th className="num">Value</th>
                  <th style={{ width: 200 }}>Share of value</th>
                  <th className="num">Below threshold</th>
                </tr>
              </thead>
              <tbody>
                {cats.map((c) => (
                  <tr key={c.category.id}>
                    <td>
                      <div className="supplier-title">
                        <span
                          className="cat__dot"
                          style={{ background: c.category.color, width: 8, height: 8, borderRadius: 99 }}
                        />
                        <div>
                          <div className="cell-title">{c.category.name}</div>
                          <div className="cell-sub">{c.category.description}</div>
                        </div>
                      </div>
                    </td>
                    <td className="num">{c.count}</td>
                    <td className="num">{num(c.qty)}</td>
                    <td className="num">{inr(c.value)}</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="bar" style={{ flex: 1 }}>
                          <span
                            className="bar__fill"
                            style={{
                              width: `${Math.max(2, (c.value / maxCategoryValue) * 100)}%`,
                              background: c.category.color,
                            }}
                          />
                        </span>
                        <span className="num" style={{ fontSize: 10.5, width: 32 }}>
                          {pct(c.value, summary.value)}%
                        </span>
                      </div>
                    </td>
                    <td className="num">
                      {c.low > 0 ? <Badge tone="amber">{c.low} low</Badge> : <span className="muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td style={{ fontWeight: 500 }}>Total</td>
                  <td className="num">{summary.totalItems}</td>
                  <td className="num">{num(summary.totalAvailable)}</td>
                  <td className="num" style={{ fontWeight: 500 }}>
                    {inr(summary.value)}
                  </td>
                  <td className="report-note">100% of working capital</td>
                  <td className="num">{summary.low.length}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="report-note" style={{ marginTop: 12 }}>
            Figures are computed from live stock minus materials issued to projects. Threshold breaches count both low and
            fully depleted lines.
          </p>
        </Card>
      </div>
    </>
  );
}
