import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../components/Toast";
import { Badge, Button, ConfirmDialog, EmptyState, PageHead, RowMenu, SearchField } from "../components/ui";
import { CategoryFormModal } from "../components/forms";
import { Icon, type IconName } from "../components/Icons";
import { categoryStats } from "../lib/derive";
import { inrCompact, num } from "../lib/format";
import { canDeleteRecords, canManageInventory } from "../lib/permissions";
import type { Category } from "../lib/types";

export default function Categories() {
  usePageTitle("Categories");
  const { state, role, deleteCategory } = useApp();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Category | undefined>();
  const [deleteFor, setDeleteFor] = useState<Category | undefined>();

  const stats = useMemo(() => categoryStats(state), [state]);
  const canEdit = canManageInventory(role);
  const canDelete = canDeleteRecords(role);

  const filtered = stats.filter((s) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return s.category.name.toLowerCase().includes(q) || s.category.description.toLowerCase().includes(q);
  });

  const totalItems = stats.reduce((s, c) => s + c.count, 0);
  const totalValue = stats.reduce((s, c) => s + c.value, 0);
  const attention = stats.reduce((s, c) => s + c.low, 0);

  const handleDelete = () => {
    if (!deleteFor) return;
    const result = deleteCategory(deleteFor.id);
    if (!result.ok) toast.error("Category not deleted", result.message);
    else toast.success("Category deleted", `${deleteFor.name} was removed.`);
    setDeleteFor(undefined);
  };

  return (
    <>
      <PageHead
        title="Categories"
        sub="Group materials so browsing, reporting and reorder decisions stay simple."
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
              New category
            </Button>
          ) : null
        }
      />

      <div className="filter-bar">
        <SearchField value={query} onChange={setQuery} placeholder="Search categories…" className="toolbar__search" />
        <span className="toolbar__spacer" />
        <span className="filter-count">
          {filtered.length} categories · {num(totalItems)} items · {inrCompact(totalValue)} value
        </span>
      </div>

      {attention > 0 ? (
        <div className="notice notice--amber" style={{ marginBottom: 16 }}>
          <Icon name="alert-triangle" />
          <div>
            {attention} item{attention === 1 ? "" : "s"} across these categories need restocking.{" "}
            <Link to="/inventory/stock-levels" className="card__link" style={{ display: "inline-flex" }}>
              Open stock levels <Icon name="arrow-right" />
            </Link>
          </div>
        </div>
      ) : null}

      {filtered.length === 0 ? (
        <EmptyState
          icon="package"
          title="No categories found"
          text="Create a category to start grouping inventory items."
          action={
            canEdit ? (
              <Button size="sm" variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                New category
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="cat-grid">
          {filtered.map(({ category, count, qty, value, low }) => (
            <div className="cat-card" key={category.id}>
              <div className="cat-card__top">
                <span
                  className="cat-card__glyph"
                  style={{ background: `${category.color}16`, color: category.color }}
                >
                  <Icon name={category.icon as IconName} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 className="cat-card__name">{category.name}</h3>
                  <p className="cat-card__meta">
                    {count} item{count === 1 ? "" : "s"} · {num(qty)} units
                  </p>
                </div>
                {canEdit ? (
                  <RowMenu
                    items={[
                      {
                        label: "Edit category",
                        icon: "pencil",
                        onClick: () => {
                          setEditing(category);
                          setFormOpen(true);
                        },
                      },
                      {
                        label: "Delete",
                        icon: "trash",
                        danger: true,
                        hidden: !canDelete,
                        onClick: () => setDeleteFor(category),
                      },
                    ]}
                  />
                ) : null}
              </div>

              <p style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.6, minHeight: 34 }}>
                {category.description || "No description yet."}
              </p>

              <div className="cat-card__stats">
                <span>
                  Value <b>{inrCompact(value)}</b>
                </span>
                {low > 0 ? <Badge tone="amber">{low} need attention</Badge> : <Badge tone="green" dot>Healthy</Badge>}
              </div>
            </div>
          ))}
        </div>
      )}

      <CategoryFormModal
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditing(undefined);
        }}
        category={editing}
      />

      <ConfirmDialog
        open={Boolean(deleteFor)}
        title={`Delete ${deleteFor?.name ?? "category"}?`}
        message="Categories can only be deleted when no items are assigned to them. Move those items to another category first."
        confirmLabel="Delete category"
        onConfirm={handleDelete}
        onClose={() => setDeleteFor(undefined)}
      />
    </>
  );
}
