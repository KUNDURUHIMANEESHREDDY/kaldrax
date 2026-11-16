import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { projectName } from "../lib/derive";
import { usePageTitle } from "../components/Layout";
import { useToast } from "../components/Toast";
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ItemThumb,
  Pagination,
  PageHead,
  RowMenu,
  SearchField,
  Segments,
  SortTh,
  type Tone,
} from "../components/ui";
import { ReturnModal, StockInModal, StockOutModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { dateShort, dateTime, inr, inrCompact, num, relTime } from "../lib/format";
import { canManageInventory } from "../lib/permissions";
import type { TransactionType } from "../lib/types";

const TYPE_META: Record<TransactionType, { label: string; tone: Tone; icon: "arrow-down-left" | "arrow-up-right" | "corner-up-left" | "sliders" }> = {
  in: { label: "Stock in", tone: "green", icon: "arrow-down-left" },
  out: { label: "Stock out", tone: "blue", icon: "arrow-up-right" },
  return: { label: "Return", tone: "amber", icon: "corner-up-left" },
  adjust: { label: "Adjustment", tone: "slate", icon: "sliders" },
};

const RANGES = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
  { value: 0, label: "All time" },
];

function inRange(at: string, days: number): boolean {
  if (days === 0) return true;
  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setDate(cutoff.getDate() - days);
  return new Date(at) >= cutoff;
}

/* ------------------------------------------------------------------ */
/* Shared movement page (stock in / out / returns)                     */
/* ------------------------------------------------------------------ */

type Kind = "in" | "out" | "return";

const KIND_CONFIG = {
  in: {
    title: "Stock in",
    sub: "Every receipt into the lab store, with supplier references and unit costs.",
    action: "Receive stock",
    icon: "download" as const,
    type: "in" as TransactionType,
    label: "Receipts",
  },
  out: {
    title: "Stock out",
    sub: "Materials issued to projects, with the balance recorded at the moment of issue.",
    action: "Issue stock",
    icon: "upload" as const,
    type: "out" as TransactionType,
    label: "Issues",
  },
  return: {
    title: "Returns",
    sub: "Unused and recovered materials coming back into the store from projects.",
    action: "Record return",
    icon: "corner-up-left" as const,
    type: "return" as TransactionType,
    label: "Returns",
  },
};

function MovementPage({ kind }: { kind: Kind }) {
  const config = KIND_CONFIG[kind];
  const { state, role } = useApp();
  const navigate = useNavigate();
  usePageTitle(config.title);

  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("all");
  const [range, setRange] = useState(30);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [modalOpen, setModalOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const canEdit = canManageInventory(role);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.transactions
      .filter((t) => t.type === config.type)
      .filter((t) => inRange(t.at, range))
      .filter((t) => {
        if (scope === "all") return true;
        return kind === "in" ? t.supplierId === scope : t.projectId === scope;
      })
      .filter((t) => {
        if (!q) return true;
        const item = state.items.find((i) => i.id === t.itemId);
        return (
          t.id.toLowerCase().includes(q) ||
          (item?.name ?? "").toLowerCase().includes(q) ||
          (item?.id ?? "").toLowerCase().includes(q) ||
          t.note.toLowerCase().includes(q) ||
          (t.actor ?? "").toLowerCase().includes(q)
        );
      });
  }, [state.transactions, state.items, config.type, query, scope, range, kind]);

  const summary = useMemo(() => {
    const scoped = state.transactions.filter((t) => t.type === config.type && inRange(t.at, range));
    const units = scoped.reduce((s, t) => s + t.qty, 0);
    const actors = new Set(scoped.map((t) => (kind === "in" ? t.supplierId : t.projectId)).filter(Boolean));
    const value = scoped.reduce((s, t) => {
      const item = state.items.find((i) => i.id === t.itemId);
      return s + t.qty * (item?.unitCost ?? 0);
    }, 0);
    return { count: scoped.length, units, entities: actors.size, value };
  }, [state.transactions, state.items, config.type, range, kind]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visible = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  const detail = detailId ? state.transactions.find((t) => t.id === detailId) : undefined;
  const detailItem = detail ? state.items.find((i) => i.id === detail.itemId) : undefined;

  const scopeOptions =
    kind === "in"
      ? state.suppliers.map((s) => ({ value: s.id, label: s.name }))
      : state.projects.map((p) => ({ value: p.id, label: p.name }));

  return (
    <>
      <PageHead
        title={config.title}
        sub={config.sub}
        actions={
          canEdit ? (
            <Button variant="primary" size="sm" icon={config.icon} onClick={() => setModalOpen(true)}>
              {config.action}
            </Button>
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
            { to: "/transactions/in", label: "Stock in" },
            { to: "/transactions/out", label: "Stock out" },
            { to: "/transactions/returns", label: "Returns" },
            { to: "/transactions/history", label: "History" },
          ]}
        />
      </div>

      <div className="mini-stats" style={{ marginBottom: "var(--gutter)" }}>
        <div className="mini-stat">
          <span>{config.label}</span>
          <b>{num(summary.count)}</b>
          <em>{range === 0 ? "All recorded" : `In the last ${range} days`}</em>
        </div>
        <div className="mini-stat">
          <span>Units moved</span>
          <b>
            {num(summary.units)} <small>units</small>
          </b>
          <em>Across all materials</em>
        </div>
        <div className="mini-stat">
          <span>{kind === "in" ? "Suppliers" : "Projects"}</span>
          <b>{num(summary.entities)}</b>
          <em>{kind === "in" ? "Delivering stock" : "Receiving materials"}</em>
        </div>
        <div className="mini-stat">
          <span>Approx. value</span>
          <b>{inrCompact(summary.value)}</b>
          <em>At current unit cost</em>
        </div>
      </div>

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search item, reference or note…"
          className="toolbar__search"
        />
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
              setPage(1);
            }}
            aria-label={kind === "in" ? "Filter by supplier" : "Filter by project"}
          >
            <option value="all">{kind === "in" ? "All suppliers" : "All projects"}</option>
            {scopeOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={range}
            onChange={(e) => {
              setRange(Number(e.target.value));
              setPage(1);
            }}
            aria-label="Filter by date range"
          >
            {RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        <span className="toolbar__spacer" />
        <span className="filter-count">
          {rows.length} {config.label.toLowerCase()}
        </span>
      </div>

      <Card flush>
        {visible.length === 0 ? (
          <EmptyState
            icon={config.icon}
            title={`No ${config.label.toLowerCase()} found`}
            text="Adjust the filters, or record a new movement to get started."
            action={
              canEdit ? (
                <Button size="sm" variant="primary" icon={config.icon} onClick={() => setModalOpen(true)}>
                  {config.action}
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Material</th>
                  <th className="num">Quantity</th>
                  <th className="num">Balance after</th>
                  <th>{kind === "in" ? "Supplier" : "Project"}</th>
                  <th>Recorded by</th>
                  <th className="num">When</th>
                  <th className="cell-actions" />
                </tr>
              </thead>
              <tbody>
                {visible.map((t) => {
                  const item = state.items.find((i) => i.id === t.itemId);
                  const raw = kind === "in" ? t.supplierId : t.projectId;
                  const label =
                    kind === "in"
                      ? state.suppliers.find((s) => s.id === t.supplierId)?.name
                      : projectName(state, t.projectId);
                  return (
                    <tr key={t.id} onClick={() => setDetailId(t.id)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="mono">{t.id}</div>
                        <div className="cell-item__sub truncate" style={{ maxWidth: 170 }} title={t.note}>
                          {t.note}
                        </div>
                      </td>
                      <td>
                        <div className="cell-item">
                          <ItemThumb category={state.categories.find((c) => c.id === item?.categoryId)} />
                          <div style={{ minWidth: 0 }}>
                            <div className="cell-item__name">{item?.name ?? "Deleted item"}</div>
                            <div className="cell-item__sub mono">{item?.id ?? "—"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">
                        <span style={{ color: t.delta > 0 ? "var(--green)" : "var(--red)" }}>
                          {t.delta > 0 ? "+" : "−"}
                          {num(Math.abs(t.delta))} <small className="muted">{item?.unit}</small>
                        </span>
                      </td>
                      <td className="num">{num(t.balanceAfter)}</td>
                      <td className="truncate" style={{ maxWidth: 190 }}>
                        {raw ? label : <span className="muted">—</span>}
                      </td>
                      <td className="muted truncate" style={{ maxWidth: 130 }}>
                        {t.actor}
                      </td>
                      <td className="num muted" title={dateTime(t.at)}>
                        {relTime(t.at)}
                      </td>
                      <td className="cell-actions" onClick={(e) => e.stopPropagation()}>
                        <RowMenu
                          items={[
                            { label: "View transaction", icon: "eye", onClick: () => setDetailId(t.id) },
                            {
                              label: "Open material",
                              icon: "package",
                              onClick: () => {
                                navigate(`/inventory?item=${t.itemId}`);
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

      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(null)}
        title={detail ? detail.id : "Transaction"}
        sub={detail ? dateTime(detail.at) : undefined}
        width={430}
        footer={
          detail && canEdit && kind === "in" ? (
            <Button variant="secondary" size="sm" icon="download" onClick={() => setModalOpen(true)}>
              Receive more stock
            </Button>
          ) : undefined
        }
      >
        {detail ? (
          <>
            <div className="item-hero">
              <ItemThumb category={state.categories.find((c) => c.id === detailItem?.categoryId)} size="lg" />
              <div style={{ minWidth: 0 }}>
                <h3 className="item-hero__name">{detailItem?.name ?? "Deleted item"}</h3>
                <div className="item-hero__meta">
                  <Badge tone={TYPE_META[detail.type].tone} dot>
                    {TYPE_META[detail.type].label}
                  </Badge>
                  <span className="mono muted">{detailItem?.id ?? detail.itemId}</span>
                </div>
              </div>
            </div>

            <div className="drawer-stats">
              <div className="drawer-stat">
                <span>Quantity</span>
                <b>
                  {detail.delta > 0 ? "+" : "−"}
                  {num(Math.abs(detail.delta))} <small>{detailItem?.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Balance after</span>
                <b>
                  {num(detail.balanceAfter)} <small>{detailItem?.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Value</span>
                <b>{inr(Math.abs(detail.delta) * (detailItem?.unitCost ?? 0))}</b>
              </div>
            </div>

            <dl className="kv">
              <dt>Note</dt>
              <dd>{detail.note}</dd>
              <dt>Recorded by</dt>
              <dd>{detail.actor}</dd>
              <dt>Date</dt>
              <dd>{dateShort(detail.at)}</dd>
              {detail.projectId ? (
                <>
                  <dt>Project</dt>
                  <dd>
                    <Link to={`/projects/${detail.projectId}`} className="card__link">
                      {projectName(state, detail.projectId)}
                    </Link>
                  </dd>
                </>
              ) : null}
              {detail.requestId ? (
                <>
                  <dt>Request</dt>
                  <dd className="mono">{detail.requestId}</dd>
                </>
              ) : null}
              {detail.supplierId ? (
                <>
                  <dt>Supplier</dt>
                  <dd>{state.suppliers.find((s) => s.id === detail.supplierId)?.name ?? "—"}</dd>
                </>
              ) : null}
              <dt>Material on hand</dt>
              <dd>
                {detailItem ? `${num(detailItem.qty)} ${detailItem.unit}` : "—"}
              </dd>
            </dl>

            {detailItem ? (
              <Link
                to={`/inventory?item=${detailItem.id}`}
                className="card__link"
                style={{ marginTop: 14, display: "inline-flex" }}
                onClick={() => setDetailId(null)}
              >
                Open material record <Icon name="arrow-right" />
              </Link>
            ) : null}

            <p className="report-note" style={{ marginTop: 18 }}>
              {config.label} are stored in the immutable ledger. Corrections should be recorded as an adjustment
              rather than editing this entry.
            </p>
          </>
        ) : null}
      </Drawer>

      {kind === "in" ? <StockInModal open={modalOpen} onClose={() => setModalOpen(false)} /> : null}
      {kind === "out" ? <StockOutModal open={modalOpen} onClose={() => setModalOpen(false)} /> : null}
      {kind === "return" ? <ReturnModal open={modalOpen} onClose={() => setModalOpen(false)} /> : null}

      <p className="sr-only" aria-live="polite">
        {rows.length} {config.label.toLowerCase()} match the current filters.
      </p>
    </>
  );
}

export function StockIn() {
  return <MovementPage kind="in" />;
}

export function StockOut() {
  return <MovementPage kind="out" />;
}

export function Returns() {
  return <MovementPage kind="return" />;
}

/* ------------------------------------------------------------------ */
/* Full ledger                                                         */
/* ------------------------------------------------------------------ */

type HistorySort = "at" | "qty" | "item";

export function History() {
  usePageTitle("Transaction history");
  const { state, role } = useApp();
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [type, setType] = useState<TransactionType | "all">("all");
  const [range, setRange] = useState(90);
  const [sortKey, setSortKey] = useState<HistorySort>("at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const canEdit = canManageInventory(role);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: state.transactions.length, in: 0, out: 0, return: 0, adjust: 0 };
    state.transactions.forEach((t) => {
      map[t.type] = (map[t.type] ?? 0) + 1;
    });
    return map;
  }, [state.transactions]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = state.transactions
      .filter((t) => (type === "all" ? true : t.type === type))
      .filter((t) => inRange(t.at, range))
      .filter((t) => {
        if (!q) return true;
        const item = state.items.find((i) => i.id === t.itemId);
        return (
          t.id.toLowerCase().includes(q) ||
          t.note.toLowerCase().includes(q) ||
          t.actor.toLowerCase().includes(q) ||
          (item?.name ?? "").toLowerCase().includes(q) ||
          (item?.id ?? "").toLowerCase().includes(q)
        );
      });

    const dir = sortDir === "asc" ? 1 : -1;
    filtered.sort((a, b) => {
      if (sortKey === "qty") return (a.qty - b.qty) * dir;
      if (sortKey === "item") {
        const an = state.items.find((i) => i.id === a.itemId)?.name ?? "";
        const bn = state.items.find((i) => i.id === b.itemId)?.name ?? "";
        return an.localeCompare(bn) * dir;
      }
      return (new Date(a.at).getTime() - new Date(b.at).getTime()) * dir;
    });
    return filtered;
  }, [state.transactions, state.items, query, type, range, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visible = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  const detail = detailId ? state.transactions.find((t) => t.id === detailId) : undefined;
  const detailItem = detail ? state.items.find((i) => i.id === detail.itemId) : undefined;

  const sort = (key: HistorySort) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "at" ? "desc" : "asc");
    }
  };

  const exportCsv = () => {
    const header = ["Transaction", "Type", "Item ID", "Item", "Qty", "Delta", "Balance", "Project", "Request", "Supplier", "Actor", "Note", "At"];
    const lines = rows.map((t) =>
      [
        t.id,
        t.type,
        t.itemId,
        `"${(state.items.find((i) => i.id === t.itemId)?.name ?? "").replace(/"/g, '""')}"`,
        t.qty,
        t.delta,
        t.balanceAfter,
        t.projectId ?? "",
        t.requestId ?? "",
        t.supplierId ?? "",
        `"${t.actor}"`,
        `"${t.note.replace(/"/g, '""')}"`,
        t.at,
      ].join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inventra-ledger-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Ledger exported", `${rows.length} entries written to file.`);
  };

  return (
    <>
      <PageHead
        title="Transaction history"
        sub="The complete, chronological ledger for every stock movement in the lab."
        actions={
          <>
            <Button variant="secondary" size="sm" icon="download" onClick={exportCsv}>
              Export ledger
            </Button>
            {canEdit ? (
              <Button variant="primary" size="sm" icon="plus" onClick={() => setModalOpen(true)}>
                Record stock in
              </Button>
            ) : null}
          </>
        }
      />

      <div className="filter-bar">
        <Segments
          items={[
            { to: "/transactions/in", label: "Stock in" },
            { to: "/transactions/out", label: "Stock out" },
            { to: "/transactions/returns", label: "Returns" },
            { to: "/transactions/history", label: "History" },
          ]}
        />
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
        {(["all", "in", "out", "return", "adjust"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`filter-chip${type === t ? " is-active" : ""}`}
            style={type === t ? { background: "var(--ink)", borderColor: "var(--ink)", color: "#fff" } : undefined}
            onClick={() => {
              setType(t);
              setPage(1);
            }}
          >
            {t === "all" ? "All entries" : TYPE_META[t].label}
            <span className="segmented__count" style={{ opacity: 0.7 }}>
              {counts[t] ?? 0}
            </span>
          </button>
        ))}
      </div>

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search item, note, actor or transaction ID…"
          className="toolbar__search"
        />
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={range}
            onChange={(e) => {
              setRange(Number(e.target.value));
              setPage(1);
            }}
            aria-label="Filter by date range"
          >
            {RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        <span className="toolbar__spacer" />
        <span className="filter-count">
          {rows.length} of {state.transactions.length} entries
        </span>
      </div>

      <Card flush>
        {visible.length === 0 ? (
          <EmptyState
            icon="swap"
            title="No ledger entries match"
            text="Try a different type, date range or search term."
            action={
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setQuery("");
                  setType("all");
                  setRange(0);
                  setPage(1);
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <SortTh label="Material" active={sortKey === "item"} dir={sortDir} onClick={() => sort("item")} />
                  <th>Type</th>
                  <SortTh label="Qty" active={sortKey === "qty"} dir={sortDir} onClick={() => sort("qty")} align="right" />
                  <th className="num">Balance</th>
                  <th>Context</th>
                  <th>Actor</th>
                  <SortTh label="When" active={sortKey === "at"} dir={sortDir} onClick={() => sort("at")} align="right" />
                </tr>
              </thead>
              <tbody>
                {visible.map((t) => {
                  const item = state.items.find((i) => i.id === t.itemId);
                  const meta = TYPE_META[t.type];
                  return (
                    <tr key={t.id} onClick={() => setDetailId(t.id)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="mono">{t.id}</div>
                        <div className="cell-item__sub truncate" style={{ maxWidth: 160 }} title={t.note}>
                          {t.note}
                        </div>
                      </td>
                      <td>
                        <div className="cell-item">
                          <ItemThumb category={state.categories.find((c) => c.id === item?.categoryId)} size="sm" />
                          <div style={{ minWidth: 0 }}>
                            <div className="cell-item__name">{item?.name ?? "Deleted item"}</div>
                            <div className="cell-item__sub mono">{item?.id ?? "—"}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Badge tone={meta.tone} dot>
                          {meta.label}
                        </Badge>
                      </td>
                      <td className="num">
                        <span style={{ color: t.delta > 0 ? "var(--green)" : t.delta < 0 ? "var(--red)" : "var(--muted)" }}>
                          {t.delta > 0 ? "+" : t.delta < 0 ? "−" : ""}
                          {num(Math.abs(t.delta))}
                        </span>
                      </td>
                      <td className="num">{num(t.balanceAfter)}</td>
                      <td className="truncate" style={{ maxWidth: 190 }}>
                        {t.projectId ? (
                          <Link to={`/projects/${t.projectId}`} className="card__link" onClick={(e) => e.stopPropagation()}>
                            {projectName(state, t.projectId)}
                          </Link>
                        ) : t.supplierId ? (
                          state.suppliers.find((s) => s.id === t.supplierId)?.name ?? <span className="muted">—</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="muted truncate" style={{ maxWidth: 130 }}>
                        {t.actor}
                      </td>
                      <td className="num muted" title={dateTime(t.at)}>
                        {dateShort(t.at)}
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

      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(null)}
        title={detail ? detail.id : "Transaction"}
        sub={detail ? TYPE_META[detail.type].label : undefined}
        width={430}
      >
        {detail ? (
          <>
            <div className="item-hero">
              <ItemThumb category={state.categories.find((c) => c.id === detailItem?.categoryId)} size="lg" />
              <div style={{ minWidth: 0 }}>
                <h3 className="item-hero__name">{detailItem?.name ?? "Deleted item"}</h3>
                <div className="item-hero__meta">
                  <Badge tone={TYPE_META[detail.type].tone} dot>
                    {TYPE_META[detail.type].label}
                  </Badge>
                  <span className="mono muted">{detailItem?.id ?? detail.itemId}</span>
                </div>
              </div>
            </div>

            <div className="drawer-stats">
              <div className="drawer-stat">
                <span>Quantity</span>
                <b>
                  {detail.delta > 0 ? "+" : "−"}
                  {num(Math.abs(detail.delta))} <small>{detailItem?.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Balance after</span>
                <b>
                  {num(detail.balanceAfter)} <small>{detailItem?.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Value</span>
                <b>{inr(Math.abs(detail.delta) * (detailItem?.unitCost ?? 0))}</b>
              </div>
            </div>

            <dl className="kv">
              <dt>Note</dt>
              <dd>{detail.note}</dd>
              <dt>Actor</dt>
              <dd>{detail.actor}</dd>
              <dt>Timestamp</dt>
              <dd>{dateTime(detail.at)}</dd>
              <dt>Project</dt>
              <dd>{detail.projectId ? projectName(state, detail.projectId) : "—"}</dd>
              <dt>Request</dt>
              <dd className="mono">{detail.requestId ?? "—"}</dd>
              <dt>Supplier</dt>
              <dd>{state.suppliers.find((s) => s.id === detail.supplierId)?.name ?? "—"}</dd>
            </dl>

            {detailItem ? (
              <Link
                to={`/inventory?item=${detailItem.id}`}
                className="card__link"
                style={{ marginTop: 14, display: "inline-flex" }}
                onClick={() => setDetailId(null)}
              >
                Open material record <Icon name="arrow-right" />
              </Link>
            ) : null}
          </>
        ) : null}
      </Drawer>

      <StockInModal open={modalOpen} onClose={() => setModalOpen(false)} />

      <p className="sr-only" aria-live="polite">
        {rows.length} ledger entries match the current filters.
      </p>
    </>
  );
}
