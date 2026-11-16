import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  Badge,
  Button,
  ConfirmDialog,
  Drawer,
  EmptyState,
  ItemThumb,
  Notice,
  PageHead,
  Pagination,
  RowMenu,
  SearchField,
  Select,
  SortTh,
  StockBadge,
} from "../components/ui";
import { SupplierFormModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { categoryById, supplierStats } from "../lib/derive";
import { dateShort, inr, inrCompact, itemStatus, num, pct, relTime } from "../lib/format";
import { canDeleteRecords, canManageInventory } from "../lib/permissions";
import type { Supplier } from "../lib/types";

const SUPPLIER_SINCE_DATE = new Date(Date.now() - 1000 * 60 * 60 * 24 * 420).toISOString();

type SortKey = "name" | "items" | "value" | "lead" | "onTime" | "rating";

export default function Suppliers() {
  usePageTitle("Suppliers");
  const { state, role, deleteSupplier } = useApp();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("all");
  const [sort, setSort] = useState<SortKey>("value");
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | undefined>();
  const [deleteFor, setDeleteFor] = useState<Supplier | undefined>();
  const [detailId, setDetailId] = useState<string | undefined>();
  const canEdit = canManageInventory(role);
  const canDelete = canDeleteRecords(role);

  const rows = useMemo(
    () =>
      state.suppliers.map((supplier) => {
        const stats = supplierStats(state, supplier);
        return { supplier, ...stats };
      }),
    [state]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = rows.filter((row) => {
      if (categoryId !== "all" && !row.supplier.categoryIds.includes(categoryId)) return false;
      if (!q) return true;
      return (
        row.supplier.name.toLowerCase().includes(q) ||
        row.supplier.id.toLowerCase().includes(q) ||
        row.supplier.city.toLowerCase().includes(q) ||
        row.supplier.contactName.toLowerCase().includes(q)
      );
    });
    const direction = dir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      switch (sort) {
        case "name":
          return a.supplier.name.localeCompare(b.supplier.name) * direction;
        case "items":
          return (a.items.length - b.items.length) * direction;
        case "value":
          return (a.value - b.value) * direction;
        case "lead":
          return (a.supplier.leadTimeDays - b.supplier.leadTimeDays) * direction;
        case "onTime":
          return (a.supplier.onTimePct - b.supplier.onTimePct) * direction;
        case "rating":
          return (a.supplier.rating - b.supplier.rating) * direction;
        default:
          return 0;
      }
    });
  }, [rows, query, categoryId, sort, dir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const summary = useMemo(() => {
    const totalValue = rows.reduce((s, r) => s + r.value, 0);
    const avgLead = rows.length ? Math.round(rows.reduce((s, r) => s + r.supplier.leadTimeDays, 0) / rows.length) : 0;
    const avgOnTime = rows.length
      ? Math.round(rows.reduce((s, r) => s + r.supplier.onTimePct, 0) / rows.length)
      : 0;
    const items = new Set(rows.flatMap((r) => r.items.map((i) => i.id))).size;
    const low = rows.reduce((s, r) => s + r.low, 0);
    return { totalValue, avgLead, avgOnTime, items, low };
  }, [rows]);

  const detail = rows.find((r) => r.supplier.id === detailId);

  const handleSort = (key: SortKey) => {
    if (sort === key) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSort(key);
      setDir(key === "name" ? "asc" : "desc");
    }
    setPage(1);
  };

  const handleDelete = () => {
    if (!deleteFor) return;
    const result = deleteSupplier(deleteFor.id);
    if (!result.ok) toast.error("Supplier not deleted", result.message);
    else toast.success("Supplier removed", `${deleteFor.name} was deleted from the directory.`);
    setDeleteFor(undefined);
  };

  return (
    <>
      <PageHead
        title="Suppliers"
        sub="Vendors, lead times and the materials each one keeps in stock."
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
              Add supplier
            </Button>
          ) : null
        }
      />

      <div className="mini-stats" style={{ marginBottom: 18 }}>
        <div className="mini-stat">
          <span>Active suppliers</span>
          <b>{rows.length}</b>
          <em>{summary.items} items sourced</em>
        </div>
        <div className="mini-stat">
          <span>Stock value</span>
          <b>{inrCompact(summary.totalValue)}</b>
          <em>at current unit cost</em>
        </div>
        <div className="mini-stat">
          <span>Average lead time</span>
          <b>
            {summary.avgLead}
            <small>days</small>
          </b>
          <em>PO to delivery</em>
        </div>
        <div className="mini-stat">
          <span>On-time delivery</span>
          <b>{summary.avgOnTime}%</b>
          <em>{summary.low} lines at or below threshold</em>
        </div>
      </div>

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search suppliers, cities or contacts…"
        />
        <span className="spacer" />
        <div className="select-wrap" style={{ width: 190 }}>
          <Select
            value={categoryId}
            aria-label="Filter by category"
            onChange={(e) => {
              setCategoryId(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">All categories</option>
            {state.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
        {categoryId !== "all" ? (
          <button type="button" className="filter-chip" onClick={() => setCategoryId("all")}>
            {categoryById(state, categoryId)?.name ?? "Category"}
            <span className="filter-chip__x">
              <Icon name="x" />
            </span>
          </button>
        ) : null}
      </div>

      <div className="card table-card">
        <div className="table-card__head">
          <div>
            <h2 className="table-card__title">Supplier directory</h2>
            <p className="table-card__sub">
              {filtered.length} of {rows.length} suppliers · ranked by {sort === "onTime" ? "on-time rate" : sort}
            </p>
          </div>
        </div>

        {visible.length === 0 ? (
          <EmptyState
            icon="truck"
            title="No suppliers match"
            text="Adjust the search or category filter, or add a new vendor to the directory."
            action={
              canEdit ? (
                <Button
                  size="sm"
                  variant="primary"
                  icon="plus"
                  onClick={() => {
                    setEditing(undefined);
                    setFormOpen(true);
                  }}
                >
                  Add supplier
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <SortTh label="Supplier" active={sort === "name"} dir={dir} onClick={() => handleSort("name")} />
                    <th>Contact</th>
                    <th>Coverage</th>
                    <SortTh label="Items" align="right" active={sort === "items"} dir={dir} onClick={() => handleSort("items")} />
                    <SortTh label="Stock value" align="right" active={sort === "value"} dir={dir} onClick={() => handleSort("value")} />
                    <SortTh label="Lead" align="right" active={sort === "lead"} dir={dir} onClick={() => handleSort("lead")} />
                    <SortTh label="On-time" active={sort === "onTime"} dir={dir} onClick={() => handleSort("onTime")} />
                    <SortTh label="Rating" active={sort === "rating"} dir={dir} onClick={() => handleSort("rating")} />
                    <th style={{ width: 44 }} aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => {
                    const initials = row.supplier.name
                      .split(/\s+/)
                      .filter(Boolean)
                      .slice(0, 2)
                      .map((p) => p[0])
                      .join("");
                    return (
                      <tr
                        key={row.supplier.id}
                        className="is-clickable"
                        onClick={() => setDetailId(row.supplier.id)}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") setDetailId(row.supplier.id);
                        }}
                      >
                        <td>
                          <div className="supplier-title">
                            <span className="supplier-logo">{initials}</span>
                            <div style={{ minWidth: 0 }}>
                              <div className="cell-title">{row.supplier.name}</div>
                              <div className="cell-sub">
                                {row.supplier.id} · {row.supplier.city}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="cell-title" style={{ fontWeight: 400 }}>
                            {row.supplier.contactName}
                          </div>
                          <div className="cell-sub">{row.supplier.email}</div>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {row.supplier.categoryIds.slice(0, 2).map((id) => {
                              const cat = categoryById(state, id);
                              return cat ? (
                                <Badge key={id} tone="plain">
                                  {cat.name}
                                </Badge>
                              ) : null;
                            })}
                            {row.supplier.categoryIds.length > 2 ? (
                              <Badge tone="plain">+{row.supplier.categoryIds.length - 2}</Badge>
                            ) : null}
                          </div>
                        </td>
                        <td className="num">
                          {row.items.length}
                          {row.low > 0 ? (
                            <span style={{ color: "var(--amber)", marginLeft: 5, fontSize: 10 }}>· {row.low} low</span>
                          ) : null}
                        </td>
                        <td className="num">{inrCompact(row.value)}</td>
                        <td className="num">{row.supplier.leadTimeDays}d</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span className="bar" style={{ width: 54 }}>
                              <span
                                className={`bar__fill${row.supplier.onTimePct >= 92 ? " bar__fill--green" : row.supplier.onTimePct >= 80 ? " bar__fill--amber" : " bar__fill--red"}`}
                                style={{ width: `${row.supplier.onTimePct}%` }}
                              />
                            </span>
                            <span className="num" style={{ fontSize: 10.5 }}>
                              {row.supplier.onTimePct}%
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="rating">
                            <Icon name="star" />
                            {row.supplier.rating.toFixed(1)}
                          </span>
                        </td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <RowMenu
                            items={[
                              {
                                label: "View supplier",
                                icon: "eye",
                                onClick: () => setDetailId(row.supplier.id),
                              },
                              {
                                label: "View items",
                                icon: "package",
                                onClick: () => setDetailId(row.supplier.id),
                              },
                              {
                                label: "Edit supplier",
                                icon: "pencil",
                                hidden: !canEdit,
                                onClick: () => {
                                  setEditing(row.supplier);
                                  setFormOpen(true);
                                },
                              },
                              {
                                label: "Delete",
                                icon: "trash",
                                danger: true,
                                hidden: !canDelete,
                                onClick: () => setDeleteFor(row.supplier),
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
            <Pagination
              page={safePage}
              pageSize={pageSize}
              total={filtered.length}
              onPage={setPage}
              onPageSize={(n) => {
                setPageSize(n);
                setPage(1);
              }}
            />
          </>
        )}
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Detail drawer                                              */}
      {/* ---------------------------------------------------------- */}
      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(undefined)}
        title={detail?.supplier.name ?? "Supplier"}
        sub={detail ? `${detail.supplier.id} · ${detail.supplier.city}` : undefined}
        width={520}
        footer={
          detail && canEdit ? (
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <Button
                size="sm"
                icon="pencil"
                onClick={() => {
                  setEditing(detail.supplier);
                  setFormOpen(true);
                }}
              >
                Edit supplier
              </Button>
              <Button size="sm" variant="secondary" icon="x" onClick={() => setDetailId(undefined)}>
                Close
              </Button>
            </div>
          ) : undefined
        }
      >
        {detail ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div className="drawer-stats">
              <div className="drawer-stat">
                <span>Items</span>
                <b>{detail.items.length}</b>
              </div>
              <div className="drawer-stat">
                <span>On hand</span>
                <b>{num(detail.qty)}</b>
              </div>
              <div className="drawer-stat">
                <span>Value</span>
                <b>{inrCompact(detail.value)}</b>
              </div>
            </div>

            <div className="meta-row">
              <Icon name="user" />
              <span>{detail.supplier.contactName}</span>
            </div>
            <div className="meta-row">
              <Icon name="mail" />
              <a href={`mailto:${detail.supplier.email}`}>{detail.supplier.email}</a>
            </div>
            <div className="meta-row">
              <Icon name="phone" />
              <span>{detail.supplier.phone}</span>
            </div>
            <div className="meta-row">
              <Icon name="clock" />
              <span>
                {detail.supplier.leadTimeDays} day lead time · {detail.supplier.onTimePct}% on-time
              </span>
            </div>
            <div className="meta-row">
              <Icon name="truck" />
              <span>{num(detail.received)} units received to date</span>
            </div>

            {detail.supplier.notes ? (
              <Notice icon="info">{detail.supplier.notes}</Notice>
            ) : null}

            <div>
              <h3 className="section-head__title" style={{ fontSize: 12.5, marginBottom: 10 }}>
                Categories covered
              </h3>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {detail.supplier.categoryIds.map((id) => {
                  const cat = categoryById(state, id);
                  return cat ? (
                    <Badge key={id} tone="plain">
                      {cat.name}
                    </Badge>
                  ) : null;
                })}
              </div>
            </div>

            <div>
              <h3 className="section-head__title" style={{ fontSize: 12.5, marginBottom: 10 }}>
                Supplied items
              </h3>
              {detail.items.length === 0 ? (
                <EmptyState small icon="package" title="No items linked" text="Assign this vendor to an item from the inventory form." />
              ) : (
                <div className="approval-panel">
                  {detail.items.map((item) => (
                    <div className="approval-panel__item" key={item.id}>
                      <ItemThumb category={categoryById(state, item.categoryId)} />
                      <div style={{ minWidth: 0 }}>
                        <div className="cell-title" style={{ fontSize: 11.5 }}>
                          <Link to={`/inventory?item=${item.id}`}>{item.name}</Link>
                        </div>
                        <div className="cell-sub">{item.location}</div>
                      </div>
                      <span className="req">
                        <b>{num(item.qty)}</b> {item.unit}
                        <div style={{ marginTop: 2 }}>
                          <StockBadge status={itemStatus(item)} />
                        </div>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="section-head__title" style={{ fontSize: 12.5, marginBottom: 10 }}>
                Recent receipts
              </h3>
              {(() => {
                const receipts = state.transactions
                  .filter((t) => t.supplierId === detail.supplier.id && t.type === "in")
                  .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
                  .slice(0, 5);
                if (receipts.length === 0) {
                  return <p className="report-note">No stock receipts recorded against this supplier yet.</p>;
                }
                return (
                  <div className="approval-panel">
                    {receipts.map((t) => {
                      const item = state.items.find((i) => i.id === t.itemId);
                      return (
                        <div className="approval-panel__item" key={t.id}>
                          <div style={{ minWidth: 0 }}>
                            <div className="cell-title" style={{ fontSize: 11.5 }}>
                              {item?.name ?? t.itemId}
                            </div>
                            <div className="cell-sub">
                              {t.id} · {relTime(t.at)}
                            </div>
                          </div>
                          <span className="req">
                            <b>+{num(t.qty)}</b> {item?.unit}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>

            <p className="report-note">
              Supplier since {dateShort(SUPPLIER_SINCE_DATE)} · performance
              reviewed monthly by the lab administrator.
            </p>
          </div>
        ) : null}
      </Drawer>

      <SupplierFormModal
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditing(undefined);
        }}
        supplier={editing}
      />

      <ConfirmDialog
        open={Boolean(deleteFor)}
        title={`Delete ${deleteFor?.name ?? "supplier"}?`}
        message="Suppliers linked to inventory items cannot be deleted. Reassign those items to another vendor first."
        confirmLabel="Delete supplier"
        onConfirm={handleDelete}
        onClose={() => setDeleteFor(undefined)}
      >
        {deleteFor ? (
          <p style={{ marginTop: 10, fontSize: 11, color: "var(--muted)" }}>
            {supplierStats(state, deleteFor).items.length} item
            {supplierStats(state, deleteFor).items.length === 1 ? "" : "s"} currently reference this supplier ·{" "}
            {inr(supplierStats(state, deleteFor).value)} stock value · {pct(supplierStats(state, deleteFor).low, Math.max(1, supplierStats(state, deleteFor).items.length))}% at risk
          </p>
        ) : null}
      </ConfirmDialog>
    </>
  );
}
