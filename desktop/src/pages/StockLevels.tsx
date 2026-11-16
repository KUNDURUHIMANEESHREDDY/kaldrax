import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../store/useApp";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  Badge,
  Bar,
  Button,
  Card,
  CardHead,
  EmptyState,
  ItemThumb,
  PageHead,
  SearchField,
  StatCard,
  StockBadge,
} from "../components/ui";
import { StockAdjustModal, StockInModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { categoryById, supplierById } from "../lib/derive";
import { inr, inrCompact, itemStatus, num, plainNum } from "../lib/format";
import { canManageInventory } from "../lib/permissions";
import type { Item } from "../lib/types";

type Filter = "attention" | "low" | "out" | "all";

export default function StockLevels() {
  usePageTitle("Stock levels");
  const { state, role } = useApp();
  const [filter, setFilter] = useState<Filter>("attention");
  const [query, setQuery] = useState("");
  const [stockInFor, setStockInFor] = useState<Item | undefined>();
  const [adjustFor, setAdjustFor] = useState<Item | undefined>();

  const canEdit = canManageInventory(role);

  const low = useMemo(() => state.items.filter((i) => itemStatus(i) === "low-stock"), [state.items]);
  const out = useMemo(() => state.items.filter((i) => itemStatus(i) === "out-of-stock"), [state.items]);
  const healthy = useMemo(() => state.items.filter((i) => itemStatus(i) === "in-stock"), [state.items]);
  const value = state.items.reduce((s, i) => s + i.qty * i.unitCost, 0);
  const units = state.items.reduce((s, i) => s + i.qty, 0);

  const base = filter === "low" ? low : filter === "out" ? out : filter === "all" ? state.items : [...out, ...low];

  const rows = base.filter((item) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      item.name.toLowerCase().includes(q) ||
      item.id.toLowerCase().includes(q) ||
      (categoryById(state, item.categoryId)?.name ?? "").toLowerCase().includes(q)
    );
  });

  const reorder = [...out, ...low].map((item) => {
    const supplier = supplierById(state, item.supplierId);
    const suggested = Math.max(item.minQty * 2 - item.qty, item.minQty || 1);
    return {
      item,
      supplier,
      suggested,
      cost: suggested * item.unitCost,
    };
  });

  const totalReorderCost = reorder.reduce((s, r) => s + r.cost, 0);

  return (
    <>
      <PageHead
        title="Stock levels"
        sub="Threshold-based view of what is healthy, running thin, or already depleted."
        actions={
          canEdit ? (
            <Button variant="primary" size="sm" icon="download" onClick={() => setStockInFor(state.items[0])}>
              Receive stock
            </Button>
          ) : null
        }
      />

      <div className="stats" style={{ marginBottom: "var(--gutter)" }}>
        <StatCard
          label="Healthy stock"
          value={num(healthy.length)}
          suffix="items"
          icon="check-circle"
          foot={`${num(healthy.reduce((s, i) => s + i.qty, 0))} units available`}
          footRight={<Badge tone="green" dot>OK</Badge>}
        />
        <StatCard
          label="Low stock"
          value={num(low.length)}
          suffix="items"
          icon="alert-triangle"
          foot={low.length ? `Shortfall of ${num(low.reduce((s, i) => s + Math.max(0, i.minQty - i.qty), 0))} units` : "Nothing near threshold"}
          footRight={low.length ? <Badge tone="amber">Restock</Badge> : null}
        />
        <StatCard
          label="Out of stock"
          value={num(out.length)}
          suffix="items"
          icon="x"
          foot={out.length ? `${out[0].name}${out.length > 1 ? ` +${out.length - 1} more` : ""}` : "Fully stocked"}
          footRight={out.length ? <Badge tone="red">Urgent</Badge> : null}
        />
        <StatCard
          label="Inventory value"
          value={inrCompact(value)}
          icon="chart"
          foot={`${num(units)} units on hand`}
          footRight={<span className="mono">{inr(value)}</span>}
        />
      </div>

      <div className="grid" style={{ marginBottom: "var(--gutter)" }}>
        <div className="col-8">
          <Card flush>
            <div style={{ padding: "18px 18px 12px" }}>
              <div className="toolbar">
                <div className="segmented" role="group" aria-label="Stock filter">
                  {(
                    [
                      ["attention", `Needs attention`, out.length + low.length],
                      ["low", "Low stock", low.length],
                      ["out", "Out of stock", out.length],
                      ["all", "All items", state.items.length],
                    ] as const
                  ).map(([value_, label, count]) => (
                    <button
                      key={value_}
                      type="button"
                      className={filter === value_ ? "is-active" : undefined}
                      onClick={() => setFilter(value_)}
                    >
                      {label}
                      <span className="segmented__count">{count}</span>
                    </button>
                  ))}
                </div>
                <span className="toolbar__spacer" />
                <SearchField value={query} onChange={setQuery} placeholder="Find an item…" />
              </div>
            </div>

            {rows.length === 0 ? (
              <EmptyState
                small
                icon={filter === "attention" ? "check-circle" : "package"}
                title={filter === "attention" ? "Everything is above threshold" : "No items here"}
                text={
                  filter === "attention"
                    ? "No reorder action is needed right now."
                    : "Try another filter or clear the search."
                }
              />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th className="num">On hand</th>
                      <th className="num">Threshold</th>
                      <th style={{ width: 160 }}>Coverage</th>
                      <th>Status</th>
                      <th>Supplier</th>
                      <th className="cell-actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((item) => {
                      const cat = categoryById(state, item.categoryId);
                      const supplier = supplierById(state, item.supplierId);
                      const status = itemStatus(item);
                      const coverage = item.minQty > 0 ? Math.min(100, (item.qty / item.minQty) * 100) : 100;
                      return (
                        <tr key={item.id}>
                          <td>
                            <div className="cell-item">
                              <ItemThumb category={cat} />
                              <div>
                                <Link to={`/inventory?item=${item.id}`} className="cell-item__name">
                                  {item.name}
                                </Link>
                                <div className="cell-item__sub mono">{item.id}</div>
                              </div>
                            </div>
                          </td>
                          <td className="num">
                            <b>{num(item.qty)}</b> <span className="muted">{item.unit}</span>
                          </td>
                          <td className="num muted">{num(item.minQty)}</td>
                          <td>
                            <Bar
                              value={coverage}
                              tone={status === "out-of-stock" ? "red" : status === "low-stock" ? "amber" : "green"}
                            />
                          </td>
                          <td>
                            <StockBadge status={status} />
                          </td>
                          <td className="muted truncate" style={{ maxWidth: 150 }}>
                            {supplier?.name ?? "—"}
                          </td>
                          <td className="cell-actions">
                            {canEdit ? (
                              <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                                <Button size="sm" variant="ghost" onClick={() => setAdjustFor(item)}>
                                  Adjust
                                </Button>
                                <Button size="sm" variant="soft" icon="download" onClick={() => setStockInFor(item)}>
                                  Receive
                                </Button>
                              </div>
                            ) : null}
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
            <CardHead
              title="Reorder suggestions"
              sub="Enough to return each item to twice its threshold"
              action={<Badge outline>{reorder.length} items</Badge>}
            />
            {reorder.length === 0 ? (
              <EmptyState small icon="check-circle" title="No reorders needed" text="All items are above their minimum threshold." />
            ) : (
              <div className="stack" style={{ gap: 10 }}>
                {reorder.slice(0, 6).map(({ item, supplier, suggested }) => (
                  <div key={item.id} className="approval-row">
                    <ItemThumb category={categoryById(state, item.categoryId)} size="sm" />
                    <span className="approval-row__main">
                      <span className="approval-row__title">{item.name}</span>
                      <span className="approval-row__sub">
                        {supplier?.name ?? "Unassigned"} · {supplier ? `${supplier.leadTimeDays}d lead` : "no lead time"}
                      </span>
                    </span>
                    <span className="approval-row__qty">
                      +{num(suggested)} {item.unit}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {reorder.length > 0 ? (
              <>
                <div className="summary" style={{ marginTop: 14 }}>
                  <div className="summary__row">
                    <span>Estimated purchase value</span>
                    <b>{inr(totalReorderCost)}</b>
                  </div>
                  <div className="summary__row">
                    <span>Items below threshold</span>
                    <b>{plainNum(reorder.length)}</b>
                  </div>
                </div>
                <p className="report-note" style={{ marginTop: 10 }}>
                  Suggester uses twice the minimum threshold as a healthy buffer. Lead times come from the supplier record.
                </p>
              </>
            ) : null}
          </Card>
        </div>
      </div>

      {out.length > 0 ? (
        <div className="notice notice--red">
          <Icon name="alert-circle" />
          <div>
            <b>{out.length} items are completely depleted.</b> Requests including these items cannot be approved until stock is
            received: {out.map((i) => i.name).join(", ")}.
          </div>
        </div>
      ) : null}

      <StockInModal open={Boolean(stockInFor)} onClose={() => setStockInFor(undefined)} item={stockInFor} />
      <StockAdjustModal open={Boolean(adjustFor)} onClose={() => setAdjustFor(undefined)} item={adjustFor} />
    </>
  );
}
