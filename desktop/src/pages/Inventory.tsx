import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../components/Toast";
import {
  Badge,
  Bar,
  Button,
  Card,
  ConfirmDialog,
  Drawer,
  EmptyState,
  ItemThumb,
  PageHead,
  Pagination,
  RowMenu,
  SearchField,
  SortTh,
  StockBadge,
} from "../components/ui";
import { ItemFormModal, StockAdjustModal, StockInModal, StockOutModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { categoryById, supplierById, transactionsForItem } from "../lib/derive";
import { dateShort, inr, itemStatus, num, relTime } from "../lib/format";
import { canDeleteRecords, canManageInventory } from "../lib/permissions";
import type { Item } from "../lib/types";

type SortKey = "name" | "category" | "qty" | "value" | "updatedAt";

const TXN_LABEL: Record<string, string> = {
  in: "Stock in",
  out: "Stock out",
  return: "Return",
  adjust: "Adjustment",
};

export default function Inventory() {
  usePageTitle("Inventory");
  const { state, role, deleteItem } = useApp();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [query, setQuery] = useState(params.get("q") ?? "");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);

  const [detailId, setDetailId] = useState<string | null>(params.get("item"));
  const [addOpen, setAddOpen] = useState(params.get("new") === "1");
  const [editItem, setEditItem] = useState<Item | undefined>();
  const [editOpen, setEditOpen] = useState(false);
  const [stockInFor, setStockInFor] = useState<Item | undefined>();
  const [stockOutFor, setStockOutFor] = useState<Item | undefined>();
  const [adjustFor, setAdjustFor] = useState<Item | undefined>();
  const [deleteFor, setDeleteFor] = useState<Item | undefined>();

  const canEdit = canManageInventory(role);
  const canDelete = canDeleteRecords(role);

  /* Keep the open drawer / modal in the URL so a refresh restores context. */
  useEffect(() => {
    const next = new URLSearchParams(params);
    if (detailId) next.set("item", detailId);
    else next.delete("item");
    if (addOpen) next.set("new", "1");
    else next.delete("new");
    if (query) next.set("q", query);
    else next.delete("q");
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailId, addOpen, query]);

  const resetFilters = () => {
    setQuery("");
    setCategory("all");
    setStatus("all");
    setPage(1);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = state.items.filter((item) => {
      if (category !== "all" && item.categoryId !== category) return false;
      if (status !== "all" && itemStatus(item) !== status) return false;
      if (!q) return true;
      const cat = categoryById(state, item.categoryId)?.name ?? "";
      const sup = supplierById(state, item.supplierId)?.name ?? "";
      return (
        item.name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        item.location.toLowerCase().includes(q) ||
        cat.toLowerCase().includes(q) ||
        sup.toLowerCase().includes(q)
      );
    });

    const dir = sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      switch (sortKey) {
        case "qty":
          return (a.qty - b.qty) * dir;
        case "value":
          return (a.qty * a.unitCost - b.qty * b.unitCost) * dir;
        case "category": {
          const an = categoryById(state, a.categoryId)?.name ?? "";
          const bn = categoryById(state, b.categoryId)?.name ?? "";
          return an.localeCompare(bn) * dir;
        }
        case "updatedAt":
          return (new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime()) * dir;
        default:
          return a.name.localeCompare(b.name) * dir;
      }
    });
    return rows;
  }, [state, query, category, status, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const rows = filtered.slice((page - 1) * pageSize, page * pageSize);
  const detail = detailId ? state.items.find((i) => i.id === detailId) : undefined;
  const detailCategory = detail ? categoryById(state, detail.categoryId) : undefined;
  const detailSupplier = detail ? supplierById(state, detail.supplierId) : undefined;
  const detailHistory = detail ? transactionsForItem(state, detail.id).slice(0, 6) : [];

  const sort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "qty" || key === "value" ? "desc" : "asc");
    }
  };

  const openItem = (id: string) => setDetailId(id);

  const handleDelete = () => {
    if (!deleteFor) return;
    const result = deleteItem(deleteFor.id);
    if (!result.ok) {
      toast.error("Item not deleted", result.message);
    } else {
      toast.success("Item deleted", `${deleteFor.name} was removed from inventory.`);
      if (detailId === deleteFor.id) setDetailId(null);
    }
    setDeleteFor(undefined);
  };

  const exportCsv = () => {
    const header = ["ID", "Name", "Category", "Qty", "Unit", "Min", "Location", "Supplier", "Unit cost", "Value", "Status"];
    const lines = filtered.map((i) =>
      [
        i.id,
        `"${i.name.replace(/"/g, '""')}"`,
        `"${categoryById(state, i.categoryId)?.name ?? ""}"`,
        i.qty,
        i.unit,
        i.minQty,
        `"${i.location}"`,
        `"${supplierById(state, i.supplierId)?.name ?? ""}"`,
        i.unitCost,
        i.qty * i.unitCost,
        itemStatus(i),
      ].join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inventra-items-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV exported", `${filtered.length} rows written to file.`);
  };

  const filtersActive = query !== "" || category !== "all" || status !== "all";
  const activeFiltersCount = (query ? 1 : 0) + (category !== "all" ? 1 : 0) + (status !== "all" ? 1 : 0);

  return (
    <>
      <PageHead
        title="Inventory"
        sub="Every material in the PBL lab, with live on-hand quantities and thresholds."
        actions={
          <>
            <Button variant="secondary" size="sm" icon="download" onClick={exportCsv}>
              Export CSV
            </Button>
            {canEdit ? (
              <Button variant="primary" size="sm" icon="plus" onClick={() => setAddOpen(true)}>
                Add item
              </Button>
            ) : (
              <Badge tone="slate" lg>
                Read-only access
              </Badge>
            )}
          </>
        }
      />

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search name, ID, location or supplier…"
          className="toolbar__search"
        />
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by category"
          >
            <option value="all">All categories</option>
            {state.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        <div className="select-wrap">
          <select
            className="select filter-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by stock status"
          >
            <option value="all">Any status</option>
            <option value="in-stock">In stock</option>
            <option value="low-stock">Low stock</option>
            <option value="out-of-stock">Out of stock</option>
          </select>
          <Icon name="chevron-down" className="chev" />
        </div>
        {filtersActive ? (
          <Button variant="ghost" size="sm" icon="refresh" onClick={resetFilters}>
            Clear {activeFiltersCount > 1 ? `(${activeFiltersCount})` : ""}
          </Button>
        ) : null}
        <span className="toolbar__spacer" />
        <span className="filter-count">
          {filtered.length} of {state.items.length} items
        </span>
      </div>

      <Card flush>
        {rows.length === 0 ? (
          <EmptyState
            icon="search"
            title="No items match those filters"
            text="Try a different category, status, or search term."
            action={
              <Button size="sm" variant="secondary" onClick={resetFilters}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <SortTh label="Item" active={sortKey === "name"} dir={sortDir} onClick={() => sort("name")} />
                  <SortTh label="Category" active={sortKey === "category"} dir={sortDir} onClick={() => sort("category")} />
                  <SortTh label="On hand" active={sortKey === "qty"} dir={sortDir} onClick={() => sort("qty")} align="right" />
                  <th>Status</th>
                  <th>Location</th>
                  <SortTh label="Stock value" active={sortKey === "value"} dir={sortDir} onClick={() => sort("value")} align="right" />
                  <SortTh label="Updated" active={sortKey === "updatedAt"} dir={sortDir} onClick={() => sort("updatedAt")} align="right" />
                  <th className="cell-actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => {
                  const cat = categoryById(state, item.categoryId);
                  const statusValue = itemStatus(item);
                  const fill = item.minQty > 0 ? Math.min(100, (item.qty / (item.minQty * 2)) * 100) : 100;
                  return (
                    <tr key={item.id} onClick={() => openItem(item.id)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="cell-item">
                          <ItemThumb category={cat} />
                          <div style={{ minWidth: 0 }}>
                            <div className="cell-item__name">{item.name}</div>
                            <div className="cell-item__sub mono">
                              {item.id} · {cat?.name ?? "Uncategorised"}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="cat">
                          <span className="cat__dot" style={{ background: cat?.color ?? "#9b9b9b" }} />
                          {cat?.name ?? "—"}
                        </span>
                      </td>
                      <td className="num">
                        <div className="stock-cell">
                          <div className="stock-cell__row">
                            <b>{num(item.qty)}</b>
                            <small>{item.unit}</small>
                          </div>
                          <Bar
                            value={fill}
                            tone={statusValue === "out-of-stock" ? "red" : statusValue === "low-stock" ? "amber" : "green"}
                          />
                        </div>
                      </td>
                      <td>
                        <StockBadge status={statusValue} />
                      </td>
                      <td className="muted truncate" style={{ maxWidth: 170 }}>
                        {item.location}
                      </td>
                      <td className="num">{inr(item.qty * item.unitCost)}</td>
                      <td className="num muted" title={dateShort(item.updatedAt)}>
                        {relTime(item.updatedAt)}
                      </td>
                      <td className="cell-actions" onClick={(e) => e.stopPropagation()}>
                        <RowMenu
                          items={[
                            { label: "View details", icon: "eye", onClick: () => openItem(item.id) },
                            {
                              label: "Edit item",
                              icon: "pencil",
                              hidden: !canEdit,
                              onClick: () => {
                                setEditItem(item);
                                setEditOpen(true);
                              },
                            },
                            {
                              label: "Adjust stock",
                              icon: "sliders",
                              hidden: !canEdit,
                              onClick: () => setAdjustFor(item),
                            },
                            {
                              label: "Receive stock",
                              icon: "download",
                              hidden: !canEdit,
                              onClick: () => setStockInFor(item),
                            },
                            {
                              label: "Issue stock",
                              icon: "upload",
                              hidden: !canEdit,
                              onClick: () => setStockOutFor(item),
                            },
                            {
                              label: "Delete",
                              icon: "trash",
                              danger: true,
                              hidden: !canDelete,
                              onClick: () => setDeleteFor(item),
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
            page={page}
            pageSize={pageSize}
            total={filtered.length}
            onPage={setPage}
            onPageSize={(n) => {
              setPageSize(n);
              setPage(1);
            }}
          />
        ) : null}
      </Card>

      {/* ------------------------------------------------------------ */}
      {/* Item detail drawer                                           */}
      {/* ------------------------------------------------------------ */}
      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(null)}
        title="Item details"
        sub={detail ? `${detail.id} · ${detailCategory?.name ?? "Uncategorised"}` : undefined}
        width={470}
        footer={
          detail ? (
            <div style={{ display: "flex", gap: 8, width: "100%", flexWrap: "wrap" }}>
              <Button
                variant="secondary"
                size="sm"
                icon="pencil"
                disabled={!canEdit}
                onClick={() => {
                  setEditItem(detail);
                  setEditOpen(true);
                }}
              >
                Edit
              </Button>
              <Button variant="soft" size="sm" icon="sliders" disabled={!canEdit} onClick={() => setAdjustFor(detail)}>
                Adjust
              </Button>
              <Button variant="secondary" size="sm" icon="download" disabled={!canEdit} onClick={() => setStockInFor(detail)}>
                Receive
              </Button>
              <Button variant="primary" size="sm" icon="upload" disabled={!canEdit} onClick={() => setStockOutFor(detail)}>
                Issue
              </Button>
            </div>
          ) : null
        }
      >
        {detail ? (
          <>
            <div className="item-hero">
              <ItemThumb category={detailCategory} size="lg" />
              <div style={{ minWidth: 0 }}>
                <h3 className="item-hero__name">{detail.name}</h3>
                <div className="item-hero__meta">
                  <StockBadge status={itemStatus(detail)} />
                  <span className="badge badge--outline">{detail.unit}</span>
                  <span className="muted" style={{ fontSize: 11 }}>
                    {detailCategory?.name ?? "Uncategorised"}
                  </span>
                </div>
              </div>
            </div>

            <div className="drawer-stats">
              <div className="drawer-stat">
                <span>On hand</span>
                <b>
                  {num(detail.qty)} <small>{detail.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Threshold</span>
                <b>
                  {num(detail.minQty)} <small>{detail.unit}</small>
                </b>
              </div>
              <div className="drawer-stat">
                <span>Stock value</span>
                <b>{inr(detail.qty * detail.unitCost)}</b>
              </div>
            </div>

            {detail.qty <= detail.minQty ? (
              <div className={`notice${detail.qty === 0 ? " notice--red" : " notice--amber"}`} style={{ marginBottom: 16 }}>
                <Icon name="alert-triangle" />
                <div>
                  {detail.qty === 0
                    ? "This item is completely depleted. Receive stock before approving requests that need it."
                    : `Below the minimum threshold of ${detail.minQty} ${detail.unit}. Restock soon to avoid project delays.`}
                </div>
              </div>
            ) : null}

            <div style={{ marginBottom: 16 }}>
              <p className="field__label" style={{ marginBottom: 8 }}>
                Details
              </p>
              <dl className="kv">
                <dt>Description</dt>
                <dd>{detail.description || "No description recorded."}</dd>
                <dt>Location</dt>
                <dd>{detail.location}</dd>
                <dt>Supplier</dt>
                <dd>{detailSupplier?.name ?? "Unassigned"}</dd>
                <dt>Unit cost</dt>
                <dd>{inr(detail.unitCost)} per {detail.unit}</dd>
                <dt>Created</dt>
                <dd>{dateShort(detail.createdAt)}</dd>
                <dt>Last updated</dt>
                <dd>{dateShort(detail.updatedAt)}</dd>
              </dl>
            </div>

            <div className="card__head" style={{ padding: 0, marginBottom: 8 }}>
              <div>
                <h3 className="card__title" style={{ fontSize: 13 }}>
                  Recent movements
                </h3>
                <p className="card__sub">Latest six ledger entries for this item</p>
              </div>
            </div>

            {detailHistory.length === 0 ? (
              <EmptyState small icon="swap" title="No movements yet" text="Stock receipts, issues and returns will be listed here." />
            ) : (
              <div className="table-wrap">
                <table className="table table--compact">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th className="num">Qty</th>
                      <th className="num">Balance</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailHistory.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <Badge
                            tone={t.type === "in" ? "green" : t.type === "out" ? "blue" : t.type === "return" ? "amber" : "slate"}
                          >
                            {TXN_LABEL[t.type]}
                          </Badge>
                        </td>
                        <td className="num" style={{ color: t.delta < 0 ? "var(--red)" : "var(--green)" }}>
                          {t.delta > 0 ? "+" : ""}
                          {num(t.delta)}
                        </td>
                        <td className="num">{num(t.balanceAfter)}</td>
                        <td className="muted">{dateShort(t.at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {canDelete ? (
              <div style={{ marginTop: 22, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <Button size="sm" variant="danger-soft" icon="trash" onClick={() => setDeleteFor(detail)}>
                  Delete item
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </Drawer>

      <ItemFormModal open={addOpen} onClose={() => setAddOpen(false)} onSaved={(id) => id && setDetailId(id)} />
      <ItemFormModal
        open={editOpen}
        onClose={() => {
          setEditOpen(false);
          setEditItem(undefined);
        }}
        item={editItem}
      />
      <StockAdjustModal open={Boolean(adjustFor)} onClose={() => setAdjustFor(undefined)} item={adjustFor} />
      <StockInModal open={Boolean(stockInFor)} onClose={() => setStockInFor(undefined)} item={stockInFor} />
      <StockOutModal open={Boolean(stockOutFor)} onClose={() => setStockOutFor(undefined)} item={stockOutFor} />

      <ConfirmDialog
        open={Boolean(deleteFor)}
        title={`Delete ${deleteFor?.name ?? "item"}?`}
        message={`This removes ${deleteFor?.id ?? "the item"} and its transaction history. Items issued to a project or referenced by an open request cannot be deleted.`}
        confirmLabel="Delete item"
        onConfirm={handleDelete}
        onClose={() => setDeleteFor(undefined)}
      />

      <p className="sr-only" aria-live="polite">
        {filtered.length} items match the current filters.
      </p>
    </>
  );
}
