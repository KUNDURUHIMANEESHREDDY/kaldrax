import { useEffect, useState } from "react";
import { useApp } from "../store/useApp";
import { useToast } from "../hooks/useToast";
import { Button, Field, Input, Modal, Select, Textarea } from "./ui";
import type {
  Category,
  Item,
  ItemInput,
  Priority,
  Project,
  ProjectInput,
  ProjectStatus,
  RequiredMaterial,
  Supplier,
} from "../lib/types";
import { num } from "../lib/format";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const UNITS = ["pcs", "units", "sets", "kits", "boxes", "metres", "spools", "litres", "pairs"];

function emptyItem(categoryId: string, supplierId: string, minQty: number): ItemInput {
  return {
    name: "",
    categoryId,
    description: "",
    qty: 0,
    minQty,
    unit: "pcs",
    location: "",
    supplierId,
    unitCost: 0,
    openingNote: "",
  };
}

/* ------------------------------------------------------------------ */
/* Item create / edit                                                  */
/* ------------------------------------------------------------------ */

export function ItemFormModal({
  open,
  onClose,
  item,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  item?: Item;
  onSaved?: (id?: string) => void;
}) {
  const { state, addItem, updateItem } = useApp();
  const toast = useToast();
  const [form, setForm] = useState<ItemInput>(() => emptyItem("", "", 5));
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setErrors({});
    if (item) {
      setForm({
        name: item.name,
        categoryId: item.categoryId,
        description: item.description,
        qty: item.qty,
        minQty: item.minQty,
        unit: item.unit,
        location: item.location,
        supplierId: item.supplierId,
        unitCost: item.unitCost,
        openingNote: "",
      });
    } else {
      setForm(
        emptyItem(
          state.categories[0]?.id ?? "",
          state.suppliers[0]?.id ?? "",
          state.settings.defaultMinThreshold
        )
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, item]);

  const set = <K extends keyof ItemInput>(key: K, value: ItemInput[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = () => {
    const next: Record<string, string> = {};
    if (!form.name.trim()) next.name = "Give the item a recognisable name.";
    if (!form.categoryId) next.categoryId = "Pick a category.";
    if (form.qty < 0) next.qty = "Quantity cannot be negative.";
    if (form.minQty < 0) next.minQty = "Threshold cannot be negative.";
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const result = item ? updateItem(item.id, form) : addItem(form);
    if (!result.ok) {
      toast.error("Could not save item", result.message);
      return;
    }
    toast.success(
      item ? "Item updated" : "Item added to inventory",
      item ? `${form.name} was updated.` : `${form.name} · ${num(form.qty)} ${form.unit} recorded.`
    );
    onSaved?.(result.id ?? item?.id);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={item ? "Edit inventory item" : "Add inventory item"}
      sub={item ? `${item.id} · last updated ${new Date(item.updatedAt).toLocaleDateString("en-IN")}` : "Record a new material for the PBL lab."}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="check">
            {item ? "Save changes" : "Add item"}
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Item name" required error={errors.name} className="span-2" htmlFor="item-name">
          <Input
            id="item-name"
            value={form.name}
            error={Boolean(errors.name)}
            onChange={(e) => set("name", e.target.value)}
            placeholder="e.g. ESP32 DevKit V1"
          />
        </Field>

        <Field label="Category" required error={errors.categoryId} htmlFor="item-cat">
          <Select
            id="item-cat"
            value={form.categoryId}
            error={Boolean(errors.categoryId)}
            onChange={(e) => set("categoryId", e.target.value)}
          >
            <option value="">Select category…</option>
            {state.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Supplied by" htmlFor="item-supplier">
          <Select id="item-supplier" value={form.supplierId} onChange={(e) => set("supplierId", e.target.value)}>
            <option value="">Unassigned</option>
            {state.suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Quantity on hand" required error={errors.qty} htmlFor="item-qty">
          <Input
            id="item-qty"
            type="number"
            min={0}
            value={form.qty}
            error={Boolean(errors.qty)}
            onChange={(e) => set("qty", Number(e.target.value))}
          />
        </Field>

        <Field
          label="Minimum threshold"
          error={errors.minQty}
          hint="Low-stock alerts trigger at or below this level."
          htmlFor="item-min"
        >
          <Input
            id="item-min"
            type="number"
            min={0}
            value={form.minQty}
            error={Boolean(errors.minQty)}
            onChange={(e) => set("minQty", Number(e.target.value))}
          />
        </Field>

        <Field label="Unit of measure" htmlFor="item-unit">
          <Select id="item-unit" value={form.unit} onChange={(e) => set("unit", e.target.value)}>
            {UNITS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Unit cost (₹)" htmlFor="item-cost">
          <Input
            id="item-cost"
            type="number"
            min={0}
            step="0.5"
            value={form.unitCost}
            onChange={(e) => set("unitCost", Number(e.target.value))}
          />
        </Field>

        <Field label="Storage location" hint="Shelf, bin or lab room." htmlFor="item-loc">
          <Input
            id="item-loc"
            value={form.location}
            onChange={(e) => set("location", e.target.value)}
            placeholder="e.g. Lab 2 · Shelf C4"
          />
        </Field>

        <Field label="Notes" className="span-2" htmlFor="item-desc">
          <Textarea
            id="item-desc"
            rows={3}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="Specification, variant, compatible boards…"
          />
        </Field>

        {!item ? (
          <Field
            label="Opening note"
            className="span-2"
            hint="Added to the stock-in transaction for audit."
            htmlFor="item-note"
          >
            <Input
              id="item-note"
              value={form.openingNote ?? ""}
              onChange={(e) => set("openingNote", e.target.value)}
              placeholder="Purchase order, invoice or donor reference"
            />
          </Field>
        ) : null}
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Stock adjustment                                                    */
/* ------------------------------------------------------------------ */

const ADJUST_REASONS = [
  "Cycle count correction",
  "Damaged / scrapped",
  "Found in storage",
  "Data entry fix",
  "Sample consumed in lab",
];

export function StockAdjustModal({
  open,
  onClose,
  item,
}: {
  open: boolean;
  onClose: () => void;
  item?: Item;
}) {
  if (!open || !item) return null;
  return <StockAdjustForm key={item.id} onClose={onClose} item={item} />;
}

function StockAdjustForm({ onClose, item }: { onClose: () => void; item: Item }) {
  const { adjustStock } = useApp();
  const toast = useToast();
  const [mode, setMode] = useState<"set" | "add" | "remove">("set");
  const [qty, setQty] = useState(item.qty);
  const [reason, setReason] = useState(ADJUST_REASONS[0]);
  const [note, setNote] = useState("");

  const projected = mode === "set" ? qty : mode === "add" ? item.qty + qty : item.qty - qty;

  const submit = () => {
    const result = adjustStock({ itemId: item.id, mode, qty, reason, note });
    if (!result.ok) {
      toast.error("Adjustment not saved", result.message);
      return;
    }
    toast.success("Stock adjusted", `${item.name} is now ${num(projected)} ${item.unit}.`);
    onClose();
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Adjust stock"
      sub={`${item.id} · ${item.name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="sliders">
            Save adjustment
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <div className="segmented" role="group" aria-label="Adjustment mode">
          {(
            [
              ["set", "Set to"],
              ["add", "Add"],
              ["remove", "Remove"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={mode === value ? "is-active" : undefined}
              onClick={() => {
                setMode(value);
                setQty(value === "set" ? item.qty : 0);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <Field label={mode === "set" ? "New quantity on hand" : "Quantity"} required htmlFor="adj-qty">
          <Input
            id="adj-qty"
            type="number"
            min={0}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            autoFocus
          />
        </Field>

        <div className="summary">
          <div className="summary__row">
            <span>Current on hand</span>
            <b>
              {num(item.qty)} {item.unit}
            </b>
          </div>
          <div className="summary__row">
            <span>After adjustment</span>
            <b style={{ color: projected < 0 ? "var(--red)" : undefined }}>
              {num(projected)} {item.unit}
            </b>
          </div>
        </div>

        <Field label="Reason" required htmlFor="adj-reason">
          <Select id="adj-reason" value={reason} onChange={(e) => setReason(e.target.value)}>
            {ADJUST_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Note" hint="Optional context for the audit trail." htmlFor="adj-note">
          <Input id="adj-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. 3 units cracked in transit" />
        </Field>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Stock in                                                            */
/* ------------------------------------------------------------------ */

export function StockInModal({
  open,
  onClose,
  item,
  initialItemId,
}: {
  open: boolean;
  onClose: () => void;
  item?: Item;
  initialItemId?: string;
}) {
  const { state, stockIn } = useApp();
  const toast = useToast();
  const [itemId, setItemId] = useState("");
  const [qty, setQty] = useState(1);
  const [supplierId, setSupplierId] = useState("");
  const [unitCost, setUnitCost] = useState(0);
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!open) return;
    const id = item?.id ?? initialItemId ?? state.items[0]?.id ?? "";
    const target = state.items.find((i) => i.id === id);
    setItemId(id);
    setQty(1);
    setSupplierId(target?.supplierId ?? "");
    setUnitCost(target?.unitCost ?? 0);
    setReference("");
    setNote("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, item, initialItemId]);

  const selected = state.items.find((i) => i.id === itemId);

  const submit = () => {
    const result = stockIn({ itemId, qty, supplierId, unitCost, note, reference });
    if (!result.ok) {
      toast.error("Stock not received", result.message);
      return;
    }
    toast.success(
      "Stock received",
      `${num(qty)} ${selected?.unit ?? "units"} of ${selected?.name ?? "item"} added${reference ? ` · ${reference}` : ""}.`
    );
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Receive stock"
      sub="Increases on-hand quantity and records a stock-in transaction."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="download">
            Receive stock
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <Field label="Item" required htmlFor="in-item">
          <Select
            id="in-item"
            value={itemId}
            onChange={(e) => {
              setItemId(e.target.value);
              const target = state.items.find((i) => i.id === e.target.value);
              setSupplierId(target?.supplierId ?? "");
              setUnitCost(target?.unitCost ?? 0);
            }}
          >
            {state.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} · {i.id}
              </option>
            ))}
          </Select>
        </Field>

        <div className="form-grid">
          <Field label="Quantity received" required htmlFor="in-qty">
            <Input id="in-qty" type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
          </Field>
          <Field label="Unit cost (₹)" htmlFor="in-cost">
            <Input
              id="in-cost"
              type="number"
              min={0}
              step="0.5"
              value={unitCost}
              onChange={(e) => setUnitCost(Number(e.target.value))}
            />
          </Field>
        </div>

        <Field label="Supplier" htmlFor="in-supplier">
          <Select id="in-supplier" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Unassigned</option>
            {state.suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Reference" hint="Purchase order, invoice or GRN number." htmlFor="in-ref">
          <Input id="in-ref" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="PO-2026-0184" />
        </Field>

        <Field label="Note" htmlFor="in-note">
          <Textarea id="in-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Batch, condition or delivery remarks" />
        </Field>

        {selected ? (
          <div className="summary">
            <div className="summary__row">
              <span>On hand now</span>
              <b>
                {num(selected.qty)} {selected.unit}
              </b>
            </div>
            <div className="summary__row">
              <span>After receiving</span>
              <b>
                {num(selected.qty + Math.max(0, Math.round(qty)))} {selected.unit}
              </b>
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Stock out                                                           */
/* ------------------------------------------------------------------ */

export function StockOutModal({
  open,
  onClose,
  item,
  projectId,
  initialItemId,
}: {
  open: boolean;
  onClose: () => void;
  item?: Item;
  projectId?: string;
  initialItemId?: string;
}) {
  const { state, stockOut } = useApp();
  const toast = useToast();
  const [itemId, setItemId] = useState("");
  const [qty, setQty] = useState(1);
  const [project, setProject] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!open) return;
    setItemId(item?.id ?? initialItemId ?? state.items.find((i) => i.qty > 0)?.id ?? "");
    setQty(1);
    setProject(projectId ?? "");
    setNote("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, item, projectId, initialItemId]);

  const selected = state.items.find((i) => i.id === itemId);
  const available = selected?.qty ?? 0;
  const maxQty = Math.max(0, available);

  const submit = () => {
    const result = stockOut({ itemId, qty, projectId: project || undefined, note });
    if (!result.ok) {
      toast.error("Stock not issued", result.message);
      return;
    }
    toast.success("Stock issued", `${num(qty)} ${selected?.unit ?? "units"} of ${selected?.name ?? "item"} checked out.`);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Issue stock"
      sub="Removes stock from the store and records it against a project."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="upload">
            Issue stock
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <Field label="Item" required htmlFor="out-item">
          <Select id="out-item" value={itemId} onChange={(e) => setItemId(e.target.value)}>
            {state.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} · {num(i.qty)} {i.unit} available
              </option>
            ))}
          </Select>
        </Field>

        <div className="form-grid">
          <Field label="Quantity" required hint={`Available: ${num(maxQty)} ${selected?.unit ?? ""}`} htmlFor="out-qty">
            <Input
              id="out-qty"
              type="number"
              min={1}
              max={maxQty}
              value={qty}
              onChange={(e) => setQty(Number(e.target.value))}
            />
          </Field>
          <Field label="Project" htmlFor="out-project">
            <Select id="out-project" value={project} onChange={(e) => setProject(e.target.value)}>
              <option value="">Not project-specific</option>
              {state.projects
                .filter((p) => p.status !== "completed")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </Select>
          </Field>
        </div>

        <Field label="Note" htmlFor="out-note">
          <Textarea
            id="out-note"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Purpose, bench number or expected return date"
          />
        </Field>

        {selected && qty > available ? (
          <p style={{ fontSize: 11, color: "var(--red)" }}>
            Only {num(available)} {selected.unit} are on hand.
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Returns                                                             */
/* ------------------------------------------------------------------ */

export function ReturnModal({
  open,
  onClose,
  projectId,
  itemId,
}: {
  open: boolean;
  onClose: () => void;
  projectId?: string;
  itemId?: string;
}) {
  const { state, returnStock } = useApp();
  const toast = useToast();
  const [project, setProject] = useState("");
  const [item, setItem] = useState("");
  const [qty, setQty] = useState(1);
  const [condition, setCondition] = useState("Good · reusable");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!open) return;
    setProject(projectId ?? state.projects.find((p) => p.status === "active")?.id ?? "");
    setItem(itemId ?? "");
    setQty(1);
    setCondition("Good · reusable");
    setNote("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectId, itemId]);

  const activeProject = state.projects.find((p) => p.id === project);
  const allocations = (activeProject?.allocations ?? []).filter(
    (a) => a.issued - a.consumed - a.returned > 0
  );
  const selectedItem = state.items.find((i) => i.id === item);
  const inUse = allocations.find((a) => a.itemId === item);
  const maxQty = inUse ? inUse.issued - inUse.consumed - inUse.returned : 0;

  useEffect(() => {
    if (!open) return;
    if (allocations.length === 0) {
      setItem("");
      return;
    }
    if (!allocations.some((a) => a.itemId === item)) setItem(allocations[0].itemId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, project]);

  const submit = () => {
    const result = returnStock({ projectId: project, itemId: item, qty, condition, note });
    if (!result.ok) {
      toast.error("Return not recorded", result.message);
      return;
    }
    toast.success(
      "Return recorded",
      `${num(qty)} ${selectedItem?.unit ?? "units"} of ${selectedItem?.name ?? "item"} back in stock.`
    );
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record a return"
      sub="Returned materials go back into stock and reduce what the project holds."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="corner-up-left">
            Record return
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <Field label="Project" required htmlFor="ret-project">
          <Select id="ret-project" value={project} onChange={(e) => setProject(e.target.value)}>
            <option value="">Select project…</option>
            {state.projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>

        {allocations.length === 0 ? (
          <p style={{ fontSize: 11.5, color: "var(--muted)" }}>
            This project has no materials in use, so there is nothing to return.
          </p>
        ) : (
          <>
            <Field label="Material" required htmlFor="ret-item">
              <Select id="ret-item" value={item} onChange={(e) => setItem(e.target.value)}>
                {allocations.map((a) => {
                  const it = state.items.find((i) => i.id === a.itemId);
                  if (!it) return null;
                  return (
                    <option key={a.itemId} value={a.itemId}>
                      {it.name} · {num(a.issued - a.consumed - a.returned)} in use
                    </option>
                  );
                })}
              </Select>
            </Field>

            <div className="form-grid">
              <Field
                label="Quantity returning"
                required
                hint={`In use: ${num(maxQty)} ${selectedItem?.unit ?? ""}`}
                htmlFor="ret-qty"
              >
                <Input
                  id="ret-qty"
                  type="number"
                  min={1}
                  max={maxQty}
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value))}
                />
              </Field>
              <Field label="Condition" htmlFor="ret-cond">
                <Select id="ret-cond" value={condition} onChange={(e) => setCondition(e.target.value)}>
                  <option>Good · reusable</option>
                  <option>Good · needs calibration</option>
                  <option>Damaged · quarantine</option>
                  <option>Partially damaged</option>
                </Select>
              </Field>
            </div>

            <Field label="Note" htmlFor="ret-note">
              <Textarea id="ret-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </>
        )}
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Material requests                                                   */
/* ------------------------------------------------------------------ */

const PRIORITIES: Priority[] = ["low", "normal", "high", "urgent"];

export function RequestFormModal({
  open,
  onClose,
  projectId,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  projectId?: string;
  onCreated?: (id?: string) => void;
}) {
  const { state, actorName, createRequest } = useApp();
  const toast = useToast();
  const [project, setProject] = useState("");
  const [requestedBy, setRequestedBy] = useState(actorName);
  const [priority, setPriority] = useState<Priority>("normal");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Array<{ itemId: string; qty: number }>>([{ itemId: "", qty: 1 }]);

  useEffect(() => {
    if (!open) return;
    setProject(projectId ?? state.projects.find((p) => p.status === "active")?.id ?? "");
    setRequestedBy(actorName);
    setPriority("normal");
    setNote("");
    setLines([{ itemId: state.items.find((i) => i.qty > 0)?.id ?? "", qty: 1 }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectId, actorName]);

  const updateLine = (index: number, patch: Partial<{ itemId: string; qty: number }>) =>
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const submit = () => {
    const result = createRequest({
      projectId: project,
      requestedBy,
      priority,
      note,
      lines: lines.filter((l) => l.itemId),
    });
    if (!result.ok) {
      toast.error("Request not submitted", result.message);
      return;
    }
    toast.success("Request submitted", `${result.id} is waiting for supervisor review.`);
    onCreated?.(result.id);
    onClose();
  };

  const estimated = lines.reduce((sum, l) => {
    const it = state.items.find((i) => i.id === l.itemId);
    return sum + (it ? it.unitCost * l.qty : 0);
  }, 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New material request"
      sub="Requests are reviewed by a supervisor before materials are issued."
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="inbox">
            Submit for review
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 16 }}>
        <div className="form-grid">
          <Field label="Project" required htmlFor="req-project" className="span-2">
            <Select id="req-project" value={project} onChange={(e) => setProject(e.target.value)}>
              <option value="">Select project…</option>
              {state.projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.id}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Requested by" required htmlFor="req-by">
            <Input id="req-by" value={requestedBy} onChange={(e) => setRequestedBy(e.target.value)} />
          </Field>
          <Field label="Priority" htmlFor="req-priority">
            <Select id="req-priority" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div>
          <p className="field__label" style={{ marginBottom: 8 }}>
            Materials<span className="req">*</span>
          </p>
          <div className="request-lines">
            {lines.map((line, index) => {
              const it = state.items.find((i) => i.id === line.itemId);
              const short = it ? line.qty > it.qty : false;
              return (
                <div className="request-line" key={index}>
                  <Select value={line.itemId} onChange={(e) => updateLine(index, { itemId: e.target.value })} aria-label="Material">
                    <option value="">Select material…</option>
                    {state.items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.name} · {num(i.qty)} {i.unit}
                      </option>
                    ))}
                  </Select>
                  <Input
                    type="number"
                    min={1}
                    value={line.qty}
                    onChange={(e) => updateLine(index, { qty: Number(e.target.value) })}
                    aria-label="Quantity"
                  />
                  <span className="request-line__hint" style={{ color: short ? "var(--red)" : undefined }}>
                    {it ? (short ? `only ${it.qty} left` : `${num(it.qty)} avail.`) : "—"}
                  </span>
                  <button
                    type="button"
                    className="request-line__remove"
                    aria-label="Remove line"
                    disabled={lines.length === 1}
                    onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
          <Button
            size="sm"
            variant="ghost"
            icon="plus"
            style={{ marginTop: 8 }}
            onClick={() => setLines((prev) => [...prev, { itemId: "", qty: 1 }])}
          >
            Add material
          </Button>
        </div>

        <Field label="Justification" htmlFor="req-note">
          <Textarea
            id="req-note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What is this material for? Mention the milestone or experiment it supports."
          />
        </Field>

        <div className="request-summary">
          <span>
            {lines.filter((l) => l.itemId).length} material line
            {lines.filter((l) => l.itemId).length === 1 ? "" : "s"} · estimated value
          </span>
          <b>₹{Math.round(estimated).toLocaleString("en-IN")}</b>
        </div>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Projects                                                            */
/* ------------------------------------------------------------------ */

const PROJECT_STATUSES: ProjectStatus[] = ["planning", "active", "on-hold", "completed"];

export function ProjectFormModal({
  open,
  onClose,
  project,
}: {
  open: boolean;
  onClose: () => void;
  project?: Project;
}) {
  const { state, addProject, updateProject } = useApp();
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [team, setTeam] = useState("");
  const [supervisor, setSupervisor] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("planning");
  const [materials, setMaterials] = useState<RequiredMaterial[]>([]);

  useEffect(() => {
    if (!open) return;
    if (project) {
      setName(project.name);
      setDescription(project.description);
      setTeam(project.team.join(", "));
      setSupervisor(project.supervisor);
      setStartDate(project.startDate.slice(0, 10));
      setEndDate(project.endDate.slice(0, 10));
      setStatus(project.status);
      setMaterials(project.required);
    } else {
      const today = new Date();
      const later = new Date();
      later.setDate(later.getDate() + 90);
      setName("");
      setDescription("");
      setTeam("");
      setSupervisor("");
      setStartDate(today.toISOString().slice(0, 10));
      setEndDate(later.toISOString().slice(0, 10));
      setStatus("planning");
      setMaterials([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, project]);

  const updateMaterial = (index: number, patch: Partial<RequiredMaterial>) =>
    setMaterials((prev) => prev.map((m, i) => (i === index ? { ...m, ...patch } : m)));

  const submit = () => {
    const input: ProjectInput = {
      name,
      description,
      team: team
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      supervisor,
      startDate: new Date(startDate).toISOString(),
      endDate: new Date(endDate).toISOString(),
      status,
      required: materials.filter((m) => m.name.trim() && m.qty > 0),
    };
    const result = project ? updateProject(project.id, input) : addProject(input);
    if (!result.ok) {
      toast.error("Project not saved", result.message);
      return;
    }
    toast.success(project ? "Project updated" : "Project created", `${name} · ${result.id ?? project?.id ?? ""}`);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={project ? "Edit project" : "Create a project"}
      sub={project ? project.id : "New PBL project with a team, supervisor and material requirements."}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="check">
            {project ? "Save project" : "Create project"}
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Project title" required className="span-2" htmlFor="proj-name">
          <Input
            id="proj-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Smart Campus Energy Monitor"
          />
        </Field>
        <Field label="Description" className="span-2" htmlFor="proj-desc">
          <Textarea
            id="proj-desc"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="One paragraph on the problem, approach and expected outcome."
          />
        </Field>
        <Field label="Team members" required hint="Comma separated." className="span-2" htmlFor="proj-team">
          <Input
            id="proj-team"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            placeholder="Aarav Sharma, Diya Patel"
          />
        </Field>
        <Field label="Supervisor" required htmlFor="proj-sup">
          <Input id="proj-sup" value={supervisor} onChange={(e) => setSupervisor(e.target.value)} placeholder="Dr. Ananya Rao" />
        </Field>
        <Field label="Status" htmlFor="proj-status">
          <Select id="proj-status" value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
            {PROJECT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === "on-hold" ? "On hold" : s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Start date" required htmlFor="proj-start">
          <Input id="proj-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </Field>
        <Field label="Target end date" required htmlFor="proj-end">
          <Input id="proj-end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>

        <div className="span-2">
          <p className="field__label" style={{ marginBottom: 8 }}>
            Required materials
          </p>
          <div className="request-lines">
            {materials.map((m, index) => (
              <div
                key={index}
                className="request-line"
                style={{ gridTemplateColumns: "minmax(0, 1.4fr) 66px 74px minmax(0, 1fr) 28px" }}
              >
                <Input
                  value={m.name}
                  onChange={(e) => updateMaterial(index, { name: e.target.value })}
                  placeholder="Material name"
                  aria-label="Material name"
                />
                <Input
                  type="number"
                  min={1}
                  value={m.qty}
                  onChange={(e) => updateMaterial(index, { qty: Number(e.target.value) })}
                  aria-label="Quantity"
                />
                <Input
                  value={m.unit}
                  onChange={(e) => updateMaterial(index, { unit: e.target.value })}
                  aria-label="Unit"
                />
                <Select
                  value={m.itemId ?? ""}
                  onChange={(e) => updateMaterial(index, { itemId: e.target.value || undefined })}
                  aria-label="Link to stock item"
                >
                  <option value="">Not stocked</option>
                  {state.items.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </Select>
                <button
                  type="button"
                  className="request-line__remove"
                  aria-label="Remove material"
                  onClick={() => setMaterials((prev) => prev.filter((_, i) => i !== index))}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <Button
            size="sm"
            variant="ghost"
            icon="plus"
            style={{ marginTop: 8 }}
            onClick={() => setMaterials((prev) => [...prev, { name: "", qty: 1, unit: "pcs" }])}
          >
            Add material
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Suppliers                                                           */
/* ------------------------------------------------------------------ */

export function SupplierFormModal({
  open,
  onClose,
  supplier,
}: {
  open: boolean;
  onClose: () => void;
  supplier?: Supplier;
}) {
  const { saveSupplier } = useApp();
  const toast = useToast();
  const [form, setForm] = useState<Omit<Supplier, "id">>({
    name: "",
    contactName: "",
    email: "",
    phone: "",
    city: "",
    leadTimeDays: 5,
    rating: 4.5,
    categoryIds: [],
    onTimePct: 95,
    notes: "",
  });

  useEffect(() => {
    if (!open) return;
    if (supplier) {
      setForm({
        name: supplier.name,
        contactName: supplier.contactName,
        email: supplier.email,
        phone: supplier.phone,
        city: supplier.city,
        leadTimeDays: supplier.leadTimeDays,
        rating: supplier.rating,
        categoryIds: supplier.categoryIds,
        onTimePct: supplier.onTimePct,
        notes: supplier.notes,
      });
    } else {
      setForm({
        name: "",
        contactName: "",
        email: "",
        phone: "",
        city: "",
        leadTimeDays: 5,
        rating: 4.5,
        categoryIds: [],
        onTimePct: 95,
        notes: "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, supplier]);

  const submit = () => {
    const result = saveSupplier(supplier ? { ...form, id: supplier.id } : form);
    if (!result.ok) {
      toast.error("Supplier not saved", result.message);
      return;
    }
    toast.success(supplier ? "Supplier updated" : "Supplier added", form.name);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={supplier ? "Edit supplier" : "Add supplier"}
      sub="Vendors used by the PBL lab for material procurement."
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="check">
            {supplier ? "Save supplier" : "Add supplier"}
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Supplier name" required className="span-2" htmlFor="sup-name">
          <Input id="sup-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Contact person" htmlFor="sup-contact">
          <Input
            id="sup-contact"
            value={form.contactName}
            onChange={(e) => setForm({ ...form, contactName: e.target.value })}
          />
        </Field>
        <Field label="City" htmlFor="sup-city">
          <Input id="sup-city" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
        </Field>
        <Field label="Email" htmlFor="sup-email">
          <Input id="sup-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Phone" htmlFor="sup-phone">
          <Input id="sup-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </Field>
        <Field label="Lead time (days)" htmlFor="sup-lead">
          <Input
            id="sup-lead"
            type="number"
            min={0}
            value={form.leadTimeDays}
            onChange={(e) => setForm({ ...form, leadTimeDays: Number(e.target.value) })}
          />
        </Field>
        <Field label="On-time delivery (%)" htmlFor="sup-ontime">
          <Input
            id="sup-ontime"
            type="number"
            min={0}
            max={100}
            value={form.onTimePct}
            onChange={(e) => setForm({ ...form, onTimePct: Number(e.target.value) })}
          />
        </Field>
        <Field label="Notes" className="span-2" htmlFor="sup-notes">
          <Textarea
            id="sup-notes"
            rows={2}
            value={form.notes ?? ""}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </Field>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Categories                                                          */
/* ------------------------------------------------------------------ */

const CATEGORY_ICONS = ["chip", "activity", "circuit", "battery", "cog", "wrench", "layers", "shield", "package", "ruler"];

export function CategoryFormModal({
  open,
  onClose,
  category,
}: {
  open: boolean;
  onClose: () => void;
  category?: Category;
}) {
  const { saveCategory } = useApp();
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("#5f6f52");
  const [icon, setIcon] = useState("package");

  useEffect(() => {
    if (!open) return;
    setName(category?.name ?? "");
    setDescription(category?.description ?? "");
    setColor(category?.color ?? "#5f6f52");
    setIcon(category?.icon ?? "package");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, category]);

  const submit = () => {
    const result = saveCategory({ id: category?.id, name, description, color, icon });
    if (!result.ok) {
      toast.error("Category not saved", result.message);
      return;
    }
    toast.success(category ? "Category updated" : "Category created", name);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={category ? "Edit category" : "New category"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} icon="check">
            Save category
          </Button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <Field label="Category name" required htmlFor="cat-name">
          <Input id="cat-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sensors & Modules" />
        </Field>
        <Field label="Description" htmlFor="cat-desc">
          <Textarea id="cat-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="form-grid">
          <Field label="Colour" htmlFor="cat-color">
            <Input id="cat-color" type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ padding: 3, height: 36 }} />
          </Field>
          <Field label="Icon" htmlFor="cat-icon">
            <Select id="cat-icon" value={icon} onChange={(e) => setIcon(e.target.value)}>
              {CATEGORY_ICONS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Small shared helpers                                                */
/* ------------------------------------------------------------------ */

