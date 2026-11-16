import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  AppState,
  Category,
  Item,
  ItemInput,
  MaterialRequest,
  Project,
  ProjectInput,
  RequestInput,
  Role,
  Settings,
  Supplier,
  Transaction,
  TransactionType,
} from "../lib/types";
import { seedState } from "../lib/seed";
import {
  canApproveRequests,
  canDeleteRecords,
  canManageInventory,
  canManageProjects,
  canManageSettings,
  ROLE_ACTORS,
} from "../lib/permissions";
import { requestAvailability } from "../lib/derive";

const STORAGE_KEY = "inventra.pbl.v1";

export type ActionResult = { ok: boolean; message?: string; id?: string };

const ok = (id?: string): ActionResult => ({ ok: true, id });
const fail = (message: string): ActionResult => ({ ok: false, message });

function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as AppState;
      if (parsed && Array.isArray(parsed.items) && Array.isArray(parsed.transactions)) {
        return normalizeState(parsed);
      }
    }
  } catch {
    /* fall through to seed */
  }
  return normalizeState(seedState);
}

/* The ledger is always kept newest-first so every view can slice from the top. */
function normalizeState(input: AppState): AppState {
  return { ...input, transactions: sortTxns(input.transactions) };
}

function maxNum(ids: string[]): number {
  return ids.reduce((max, id) => {
    const n = Number.parseInt(id.replace(/\D/g, ""), 10);
    return Number.isFinite(n) ? Math.max(max, n) : max;
  }, 0);
}

function nextItemId(items: Item[]): string {
  return `ITM-${maxNum(items.map((i) => i.id)) + 1}`;
}

function nextRequestId(requests: MaterialRequest[]): string {
  return `REQ-${maxNum(requests.map((r) => r.id)) + 1}`;
}

function nextProjectId(projects: Project[]): string {
  const n = maxNum(projects.map((p) => p.id.split("-").pop() ?? "")) + 1;
  return `PBL-2026-${String(n).padStart(3, "0")}`;
}

function nextCategoryId(categories: Category[]): string {
  return `CAT-${String(maxNum(categories.map((c) => c.id)) + 1).padStart(2, "0")}`;
}

function nextSupplierId(suppliers: Supplier[]): string {
  return `SUP-${String(maxNum(suppliers.map((s) => s.id)) + 1).padStart(2, "0")}`;
}

type TxnInput = {
  type: TransactionType;
  itemId: string;
  qty: number;
  delta: number;
  balanceAfter: number;
  actor: string;
  note: string;
  at?: string;
  projectId?: string;
  requestId?: string;
  supplierId?: string;
};

function makeTxn(prev: AppState, input: TxnInput): Transaction {
  const next = maxNum(prev.transactions.map((t) => t.id)) + 1;
  return {
    id: `TXN-${next}`,
    type: input.type,
    itemId: input.itemId,
    qty: input.qty,
    delta: input.delta,
    balanceAfter: input.balanceAfter,
    actor: input.actor,
    note: input.note,
    at: input.at ?? new Date().toISOString(),
    projectId: input.projectId,
    requestId: input.requestId,
    supplierId: input.supplierId,
  };
}

function sortTxns(txns: Transaction[]): Transaction[] {
  return [...txns].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
}

export interface StoreApi {
  state: AppState;
  role: Role;
  actorName: string;
  setRole: (role: Role) => void;
  addItem: (input: ItemInput) => ActionResult;
  updateItem: (id: string, input: ItemInput) => ActionResult;
  deleteItem: (id: string) => ActionResult;
  adjustStock: (args: {
    itemId: string;
    mode: "set" | "add" | "remove";
    qty: number;
    reason: string;
    note?: string;
  }) => ActionResult;
  stockIn: (args: {
    itemId: string;
    qty: number;
    supplierId?: string;
    unitCost?: number;
    note?: string;
    reference?: string;
  }) => ActionResult;
  stockOut: (args: { itemId: string; qty: number; projectId?: string; note?: string }) => ActionResult;
  returnStock: (args: {
    projectId: string;
    itemId: string;
    qty: number;
    condition?: string;
    note?: string;
  }) => ActionResult;
  consumeMaterial: (args: { projectId: string; itemId: string; qty: number }) => ActionResult;
  allocateToProject: (args: { projectId: string; itemId: string; qty: number; note?: string }) => ActionResult;
  saveCategory: (input: {
    id?: string;
    name: string;
    description: string;
    color: string;
    icon: string;
  }) => ActionResult;
  deleteCategory: (id: string) => ActionResult;
  saveSupplier: (input: Omit<Supplier, "id"> & { id?: string }) => ActionResult;
  deleteSupplier: (id: string) => ActionResult;
  addProject: (input: ProjectInput) => ActionResult;
  updateProject: (id: string, input: ProjectInput) => ActionResult;
  deleteProject: (id: string) => ActionResult;
  createRequest: (input: RequestInput) => ActionResult;
  approveRequest: (id: string) => ActionResult;
  rejectRequest: (id: string, reason: string) => ActionResult;
  issueRequest: (id: string) => ActionResult;
  cancelRequest: (id: string) => ActionResult;
  updateSettings: (patch: Partial<Settings>) => ActionResult;
  resetData: () => void;
  exportState: () => string;
}

const StoreContext = createContext<StoreApi | null>(null);

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>(loadState);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* storage may be full or disabled; the app still works in-memory */
    }
  }, [state]);

  const actorName = ROLE_ACTORS[state.role].name;

  const setRole = useCallback((role: Role) => {
    setState((prev) => ({ ...prev, role }));
  }, []);

  /* ---------------------------------------------------------------- */
  /* Inventory                                                         */
  /* ---------------------------------------------------------------- */

  const addItem = useCallback((input: ItemInput): ActionResult => {
    const current = stateRef.current;
    if (!canManageInventory(current.role)) return fail("You do not have permission to add inventory.");
    if (!input.name.trim()) return fail("Item name is required.");
    if (!input.categoryId) return fail("Select a category.");
    if (input.qty < 0 || input.minQty < 0) return fail("Quantities cannot be negative.");
    if (input.unitCost < 0) return fail("Unit cost cannot be negative.");

    const id = nextItemId(current.items);
    const now = new Date().toISOString();

    setState((prev) => {
      const item: Item = {
        id,
        name: input.name.trim(),
        categoryId: input.categoryId,
        description: input.description.trim(),
        qty: Math.max(0, Math.round(input.qty)),
        minQty: Math.max(0, Math.round(input.minQty)),
        unit: input.unit || "pcs",
        location: input.location.trim() || "Unassigned",
        supplierId: input.supplierId,
        unitCost: Math.max(0, input.unitCost),
        createdAt: now,
        updatedAt: now,
      };
      const transactions = [...prev.transactions];
      if (item.qty > 0) {
        transactions.push(
          makeTxn(prev, {
            type: "in",
            itemId: item.id,
            qty: item.qty,
            delta: item.qty,
            balanceAfter: item.qty,
            actor: ROLE_ACTORS[prev.role].name,
            note: input.openingNote?.trim() || "Opening stock recorded on item creation",
            supplierId: item.supplierId,
            at: now,
          })
        );
      }
      return {
        ...prev,
        items: [item, ...prev.items],
        transactions: sortTxns(transactions),
        projects: prev.projects.map((p) =>
          p.required.some((r) => r.itemId === item.id)
            ? { ...p, required: p.required.map((r) => (r.itemId === item.id ? { ...r } : r)) }
            : p
        ),
      };
    });
    return ok(id);
  }, []);

  const updateItem = useCallback((id: string, input: ItemInput): ActionResult => {
    const current = stateRef.current;
    if (!canManageInventory(current.role)) return fail("You do not have permission to edit inventory.");
    const existing = current.items.find((i) => i.id === id);
    if (!existing) return fail("Item not found.");
    if (!input.name.trim()) return fail("Item name is required.");
    if (input.qty < 0 || input.minQty < 0) return fail("Quantities cannot be negative.");

    const targetQty = Math.round(input.qty);
    const delta = targetQty - existing.qty;
    const now = new Date().toISOString();

    setState((prev) => {
      const transactions = [...prev.transactions];
      if (delta !== 0) {
        transactions.push(
          makeTxn(prev, {
            type: "adjust",
            itemId: id,
            qty: Math.abs(delta),
            delta,
            balanceAfter: targetQty,
            actor: ROLE_ACTORS[prev.role].name,
            note: "Stock corrected while editing item details",
            at: now,
          })
        );
      }
      return {
        ...prev,
        items: prev.items.map((i) =>
          i.id === id
            ? {
                ...i,
                name: input.name.trim(),
                categoryId: input.categoryId,
                description: input.description.trim(),
                qty: targetQty,
                minQty: Math.max(0, Math.round(input.minQty)),
                unit: input.unit || i.unit,
                location: input.location.trim() || i.location,
                supplierId: input.supplierId,
                unitCost: Math.max(0, input.unitCost),
                updatedAt: now,
              }
            : i
        ),
        transactions: sortTxns(transactions),
      };
    });
    return ok(id);
  }, []);

  const deleteItem = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canDeleteRecords(current.role)) return fail("Only administrators can delete inventory records.");
    const item = current.items.find((i) => i.id === id);
    if (!item) return fail("Item not found.");

    const activeAllocations = current.projects.filter((p) =>
      p.allocations.some((a) => a.itemId === id && a.issued - a.consumed - a.returned > 0)
    );
    if (activeAllocations.length > 0) {
      return fail(
        `${item.name} is currently issued to ${activeAllocations[0].name}. Record a return before deleting it.`
      );
    }
    const openRequests = current.requests.filter(
      (r) => (r.status === "pending" || r.status === "approved") && r.lines.some((l) => l.itemId === id)
    );
    if (openRequests.length > 0) {
      return fail(`${item.name} is referenced by open request ${openRequests[0].id}. Resolve it first.`);
    }

    setState((prev) => ({
      ...prev,
      items: prev.items.filter((i) => i.id !== id),
      transactions: prev.transactions.filter((t) => t.itemId !== id),
      projects: prev.projects.map((p) => ({
        ...p,
        allocations: p.allocations.filter((a) => a.itemId !== id),
        required: p.required.map((r) => (r.itemId === id ? { ...r, itemId: undefined } : r)),
      })),
    }));
    return ok();
  }, []);

  const adjustStock = useCallback<StoreApi["adjustStock"]>(
    ({ itemId, mode, qty, reason, note }) => {
      const current = stateRef.current;
      if (!canManageInventory(current.role)) return fail("You do not have permission to adjust stock.");
      const item = current.items.find((i) => i.id === itemId);
      if (!item) return fail("Item not found.");
      if (!Number.isFinite(qty) || qty < 0) return fail("Enter a valid quantity.");
      const rounded = Math.round(qty);
      let nextQty = item.qty;
      if (mode === "set") nextQty = rounded;
      else if (mode === "add") nextQty = item.qty + rounded;
      else nextQty = item.qty - rounded;
      if (nextQty < 0) return fail(`Cannot reduce below zero. ${item.name} has ${item.qty} ${item.unit} on hand.`);
      const delta = nextQty - item.qty;
      if (delta === 0) return fail("The new quantity matches the current stock.");
      if (!reason.trim()) return fail("Select a reason for the adjustment.");
      const now = new Date().toISOString();

      setState((prev) => ({
        ...prev,
        items: prev.items.map((i) => (i.id === itemId ? { ...i, qty: nextQty, updatedAt: now } : i)),
        transactions: sortTxns([
          ...prev.transactions,
          makeTxn(prev, {
            type: "adjust",
            itemId,
            qty: Math.abs(delta),
            delta,
            balanceAfter: nextQty,
            actor: ROLE_ACTORS[prev.role].name,
            note: `${reason}${note?.trim() ? ` · ${note.trim()}` : ""}`,
            at: now,
          }),
        ]),
      }));
      return ok();
    },
    []
  );

  const stockIn = useCallback<StoreApi["stockIn"]>(
    ({ itemId, qty, supplierId, unitCost, note, reference }) => {
      const current = stateRef.current;
      if (!canManageInventory(current.role)) return fail("You do not have permission to receive stock.");
      const item = current.items.find((i) => i.id === itemId);
      if (!item) return fail("Select an item.");
      if (!Number.isFinite(qty) || qty <= 0) return fail("Enter a quantity greater than zero.");
      const rounded = Math.round(qty);
      const now = new Date().toISOString();
      const balance = item.qty + rounded;

      setState((prev) => ({
        ...prev,
        items: prev.items.map((i) =>
          i.id === itemId
            ? {
                ...i,
                qty: balance,
                unitCost: unitCost && unitCost > 0 ? unitCost : i.unitCost,
                supplierId: supplierId || i.supplierId,
                updatedAt: now,
              }
            : i
        ),
        transactions: sortTxns([
          ...prev.transactions,
          makeTxn(prev, {
            type: "in",
            itemId,
            qty: rounded,
            delta: rounded,
            balanceAfter: balance,
            actor: ROLE_ACTORS[prev.role].name,
            note: `${reference ? `${reference} · ` : ""}${note?.trim() || "Stock received"}`,
            supplierId: supplierId || item.supplierId,
            at: now,
          }),
        ]),
      }));
      return ok();
    },
    []
  );

  const stockOut = useCallback<StoreApi["stockOut"]>(
    ({ itemId, qty, projectId, note }) => {
      const current = stateRef.current;
      if (!canManageInventory(current.role)) return fail("You do not have permission to issue stock.");
      const item = current.items.find((i) => i.id === itemId);
      if (!item) return fail("Select an item.");
      if (!Number.isFinite(qty) || qty <= 0) return fail("Enter a quantity greater than zero.");
      const rounded = Math.round(qty);
      if (rounded > item.qty) {
        return fail(`Only ${item.qty} ${item.unit} of ${item.name} available.`);
      }
      const project = projectId ? current.projects.find((p) => p.id === projectId) : undefined;
      if (projectId && !project) return fail("Select a valid project.");
      const now = new Date().toISOString();
      const balance = item.qty - rounded;

      setState((prev) => ({
        ...prev,
        items: prev.items.map((i) => (i.id === itemId ? { ...i, qty: balance, updatedAt: now } : i)),
        projects: prev.projects.map((p) => {
          if (!project || p.id !== project.id) return p;
          const existing = p.allocations.find((a) => a.itemId === itemId);
          const allocations = existing
            ? p.allocations.map((a) => (a.itemId === itemId ? { ...a, issued: a.issued + rounded } : a))
            : [...p.allocations, { itemId, issued: rounded, consumed: 0, returned: 0 }];
          return { ...p, allocations };
        }),
        transactions: sortTxns([
          ...prev.transactions,
          makeTxn(prev, {
            type: "out",
            itemId,
            qty: rounded,
            delta: -rounded,
            balanceAfter: balance,
            actor: ROLE_ACTORS[prev.role].name,
            note: note?.trim() || (project ? `Issued to ${project.id} · ${project.name}` : "Stock issued"),
            projectId: project?.id,
            at: now,
          }),
        ]),
      }));
      return ok();
    },
    []
  );

  const returnStock = useCallback<StoreApi["returnStock"]>(
    ({ projectId, itemId, qty, condition, note }) => {
      const current = stateRef.current;
      if (!canManageInventory(current.role)) return fail("You do not have permission to record returns.");
      const project = current.projects.find((p) => p.id === projectId);
      if (!project) return fail("Select a project.");
      const item = current.items.find((i) => i.id === itemId);
      if (!item) return fail("Select an item.");
      const allocation = project.allocations.find((a) => a.itemId === itemId);
      if (!allocation) return fail("This item is not allocated to the selected project.");
      const inUse = allocation.issued - allocation.consumed - allocation.returned;
      if (!Number.isFinite(qty) || qty <= 0) return fail("Enter a quantity greater than zero.");
      const rounded = Math.round(qty);
      if (rounded > inUse) return fail(`Only ${inUse} ${item.unit} of ${item.name} are in use on this project.`);
      const now = new Date().toISOString();
      const balance = item.qty + rounded;

      setState((prev) => ({
        ...prev,
        items: prev.items.map((i) => (i.id === itemId ? { ...i, qty: balance, updatedAt: now } : i)),
        projects: prev.projects.map((p) =>
          p.id === projectId
            ? {
                ...p,
                allocations: p.allocations.map((a) =>
                  a.itemId === itemId ? { ...a, returned: a.returned + rounded } : a
                ),
              }
            : p
        ),
        transactions: sortTxns([
          ...prev.transactions,
          makeTxn(prev, {
            type: "return",
            itemId,
            qty: rounded,
            delta: rounded,
            balanceAfter: balance,
            actor: ROLE_ACTORS[prev.role].name,
            note: `Returned from ${project.id} · ${project.name}${condition ? ` · ${condition}` : ""}${
              note?.trim() ? ` · ${note.trim()}` : ""
            }`,
            projectId,
            at: now,
          }),
        ]),
      }));
      return ok();
    },
    []
  );

  const consumeMaterial = useCallback<StoreApi["consumeMaterial"]>(
    ({ projectId, itemId, qty }) => {
      const current = stateRef.current;
      if (!canManageProjects(current.role)) return fail("You do not have permission to update consumption.");
      const project = current.projects.find((p) => p.id === projectId);
      if (!project) return fail("Project not found.");
      const allocation = project.allocations.find((a) => a.itemId === itemId);
      if (!allocation) return fail("Item is not allocated to this project.");
      const inUse = allocation.issued - allocation.consumed - allocation.returned;
      const rounded = Math.round(qty);
      if (!Number.isFinite(qty) || rounded <= 0) return fail("Enter a quantity greater than zero.");
      if (rounded > inUse) return fail(`Only ${inUse} units are currently in use.`);
      setState((prev) => ({
        ...prev,
        projects: prev.projects.map((p) =>
          p.id === projectId
            ? {
                ...p,
                allocations: p.allocations.map((a) =>
                  a.itemId === itemId ? { ...a, consumed: a.consumed + rounded } : a
                ),
              }
            : p
        ),
      }));
      return ok();
    },
    []
  );

  const allocateToProject = useCallback<StoreApi["allocateToProject"]>(
    ({ projectId, itemId, qty, note }) => {
      const current = stateRef.current;
      if (!canManageProjects(current.role)) return fail("You do not have permission to allocate materials.");
      const project = current.projects.find((p) => p.id === projectId);
      if (!project) return fail("Project not found.");
      const item = current.items.find((i) => i.id === itemId);
      if (!item) return fail("Item not found.");
      const rounded = Math.round(qty);
      if (!Number.isFinite(qty) || rounded <= 0) return fail("Enter a quantity greater than zero.");
      if (rounded > item.qty) return fail(`Only ${item.qty} ${item.unit} available in stock.`);
      const now = new Date().toISOString();
      const balance = item.qty - rounded;

      setState((prev) => ({
        ...prev,
        items: prev.items.map((i) => (i.id === itemId ? { ...i, qty: balance, updatedAt: now } : i)),
        projects: prev.projects.map((p) => {
          if (p.id !== projectId) return p;
          const existing = p.allocations.find((a) => a.itemId === itemId);
          return {
            ...p,
            allocations: existing
              ? p.allocations.map((a) => (a.itemId === itemId ? { ...a, issued: a.issued + rounded } : a))
              : [...p.allocations, { itemId, issued: rounded, consumed: 0, returned: 0 }],
          };
        }),
        transactions: sortTxns([
          ...prev.transactions,
          makeTxn(prev, {
            type: "out",
            itemId,
            qty: rounded,
            delta: -rounded,
            balanceAfter: balance,
            actor: ROLE_ACTORS[prev.role].name,
            note: note?.trim() || `Allocated to ${project.id} · ${project.name}`,
            projectId,
            at: now,
          }),
        ]),
      }));
      return ok();
    },
    []
  );

  /* ---------------------------------------------------------------- */
  /* Categories & suppliers                                            */
  /* ---------------------------------------------------------------- */

  const saveCategory = useCallback<StoreApi["saveCategory"]>((input) => {
    const current = stateRef.current;
    if (!canManageInventory(current.role)) return fail("You do not have permission to manage categories.");
    if (!input.name.trim()) return fail("Category name is required.");
    const duplicate = current.categories.find(
      (c) => c.name.toLowerCase() === input.name.trim().toLowerCase() && c.id !== input.id
    );
    if (duplicate) return fail("A category with that name already exists.");

    if (input.id) {
      setState((prev) => ({
        ...prev,
        categories: prev.categories.map((c) =>
          c.id === input.id
            ? { ...c, name: input.name.trim(), description: input.description.trim(), color: input.color, icon: input.icon }
            : c
        ),
      }));
      return ok(input.id);
    }
    const id = nextCategoryId(current.categories);
    setState((prev) => ({
      ...prev,
      categories: [
        ...prev.categories,
        {
          id,
          name: input.name.trim(),
          description: input.description.trim(),
          color: input.color,
          icon: input.icon,
        },
      ],
    }));
    return ok(id);
  }, []);

  const deleteCategory = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canDeleteRecords(current.role)) return fail("Only administrators can delete categories.");
    const count = current.items.filter((i) => i.categoryId === id).length;
    if (count > 0) return fail(`Move the ${count} item${count === 1 ? "" : "s"} in this category before deleting it.`);
    setState((prev) => ({ ...prev, categories: prev.categories.filter((c) => c.id !== id) }));
    return ok();
  }, []);

  const saveSupplier = useCallback<StoreApi["saveSupplier"]>((input) => {
    const current = stateRef.current;
    if (!canManageInventory(current.role)) return fail("You do not have permission to manage suppliers.");
    if (!input.name.trim()) return fail("Supplier name is required.");
    if (input.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email)) {
      return fail("Enter a valid email address.");
    }
    if (input.id) {
      setState((prev) => ({
        ...prev,
        suppliers: prev.suppliers.map((s) => (s.id === input.id ? { ...s, ...input, id: s.id } : s)),
      }));
      return ok(input.id);
    }
    const id = nextSupplierId(current.suppliers);
    setState((prev) => ({ ...prev, suppliers: [...prev.suppliers, { ...input, id }] }));
    return ok(id);
  }, []);

  const deleteSupplier = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canDeleteRecords(current.role)) return fail("Only administrators can delete suppliers.");
    const count = current.items.filter((i) => i.supplierId === id).length;
    if (count > 0) return fail(`${count} item${count === 1 ? " is" : "s are"} linked to this supplier. Reassign them first.`);
    setState((prev) => ({ ...prev, suppliers: prev.suppliers.filter((s) => s.id !== id) }));
    return ok();
  }, []);

  /* ---------------------------------------------------------------- */
  /* Projects                                                          */
  /* ---------------------------------------------------------------- */

  const addProject = useCallback<StoreApi["addProject"]>((input) => {
    const current = stateRef.current;
    if (!canManageProjects(current.role)) return fail("You do not have permission to create projects.");
    if (!input.name.trim()) return fail("Project name is required.");
    if (!input.supervisor.trim()) return fail("Assign a supervisor.");
    if (!input.startDate || !input.endDate) return fail("Start and end dates are required.");
    if (new Date(input.endDate) < new Date(input.startDate)) return fail("End date must be after the start date.");
    if (!input.team.length) return fail("Add at least one team member.");

    const id = nextProjectId(current.projects);
    setState((prev) => ({
      ...prev,
      projects: [
        {
          id,
          name: input.name.trim(),
          description: input.description.trim(),
          team: input.team,
          supervisor: input.supervisor.trim(),
          startDate: input.startDate,
          endDate: input.endDate,
          status: input.status,
          allocations: [],
          required: input.required,
        },
        ...prev.projects,
      ],
    }));
    return ok(id);
  }, []);

  const updateProject = useCallback((id: string, input: ProjectInput): ActionResult => {
    const current = stateRef.current;
    if (!canManageProjects(current.role)) return fail("You do not have permission to edit projects.");
    const project = current.projects.find((p) => p.id === id);
    if (!project) return fail("Project not found.");
    if (!input.name.trim()) return fail("Project name is required.");
    if (new Date(input.endDate) < new Date(input.startDate)) return fail("End date must be after the start date.");
    setState((prev) => ({
      ...prev,
      projects: prev.projects.map((p) =>
        p.id === id
          ? {
              ...p,
              name: input.name.trim(),
              description: input.description.trim(),
              team: input.team,
              supervisor: input.supervisor.trim(),
              startDate: input.startDate,
              endDate: input.endDate,
              status: input.status,
              required: input.required,
            }
          : p
      ),
    }));
    return ok(id);
  }, []);

  const deleteProject = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canDeleteRecords(current.role)) return fail("Only administrators can delete projects.");
    const project = current.projects.find((p) => p.id === id);
    if (!project) return fail("Project not found.");
    const open = current.requests.filter((r) => r.projectId === id && (r.status === "pending" || r.status === "approved"));
    if (open.length > 0) return fail(`Resolve ${open.length} open request${open.length === 1 ? "" : "s"} for this project first.`);
    const inUse = project.allocations.reduce((s, a) => s + (a.issued - a.consumed - a.returned), 0);
    if (inUse > 0) return fail("Record returns for all materials issued to this project before deleting it.");

    setState((prev) => ({
      ...prev,
      projects: prev.projects.filter((p) => p.id !== id),
      transactions: prev.transactions.map((t) => (t.projectId === id ? { ...t, projectId: undefined } : t)),
      requests: prev.requests.filter((r) => r.projectId !== id),
    }));
    return ok();
  }, []);

  /* ---------------------------------------------------------------- */
  /* Requests                                                          */
  /* ---------------------------------------------------------------- */

  const createRequest = useCallback<StoreApi["createRequest"]>((input) => {
    const current = stateRef.current;
    if (!current.settings.allowStudentRequests && current.role === "student") {
      return fail("Material requests are currently closed by the lab administrator.");
    }
    const project = current.projects.find((p) => p.id === input.projectId);
    if (!project) return fail("Select a project.");
    if (!input.requestedBy.trim()) return fail("Enter the name of the person requesting materials.");
    const lines = input.lines.filter((l) => l.itemId && l.qty > 0);
    if (lines.length === 0) return fail("Add at least one material to the request.");
    for (const line of lines) {
      const item = current.items.find((i) => i.id === line.itemId);
      if (!item) return fail("One of the selected items no longer exists.");
      if (!Number.isFinite(line.qty) || line.qty <= 0) return fail("Quantities must be greater than zero.");
    }
    if (new Set(lines.map((l) => l.itemId)).size !== lines.length) {
      return fail("The same item appears more than once. Combine the quantities into one line.");
    }

    const id = nextRequestId(current.requests);
    setState((prev) => ({
      ...prev,
      requests: [
        {
          id,
          projectId: input.projectId,
          requestedBy: input.requestedBy.trim(),
          lines: lines.map((l) => ({ itemId: l.itemId, qty: Math.round(l.qty) })),
          status: "pending",
          priority: input.priority,
          note: input.note.trim(),
          createdAt: new Date().toISOString(),
        },
        ...prev.requests,
      ],
    }));
    return ok(id);
  }, []);

  const approveRequest = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canApproveRequests(current.role)) return fail("Only administrators and supervisors can approve requests.");
    const request = current.requests.find((r) => r.id === id);
    if (!request) return fail("Request not found.");
    if (request.status !== "pending") return fail(`Request ${id} is already ${request.status}.`);

    const shortages = requestAvailability(current, request).filter((a) => !a.ok);
    if (shortages.length > 0) {
      const first = shortages[0];
      return fail(
        `Insufficient stock: ${first.item?.name ?? "item"} needs ${first.qty}, only ${first.available} available. Receive stock or reject the request.`
      );
    }

    setState((prev) => ({
      ...prev,
      requests: prev.requests.map((r) =>
        r.id === id
          ? {
              ...r,
              status: "approved",
              reviewedAt: new Date().toISOString(),
              reviewedBy: ROLE_ACTORS[prev.role].name,
            }
          : r
      ),
    }));
    return ok();
  }, []);

  const rejectRequest = useCallback((id: string, reason: string): ActionResult => {
    const current = stateRef.current;
    if (!canApproveRequests(current.role)) return fail("Only administrators and supervisors can review requests.");
    const request = current.requests.find((r) => r.id === id);
    if (!request) return fail("Request not found.");
    if (request.status !== "pending") return fail(`Request ${id} is already ${request.status}.`);
    if (!reason.trim()) return fail("Add a short reason so the team knows what to fix.");

    setState((prev) => ({
      ...prev,
      requests: prev.requests.map((r) =>
        r.id === id
          ? {
              ...r,
              status: "rejected",
              reviewedAt: new Date().toISOString(),
              reviewedBy: ROLE_ACTORS[prev.role].name,
              rejectReason: reason.trim(),
            }
          : r
      ),
    }));
    return ok();
  }, []);

  const issueRequest = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    if (!canManageInventory(current.role)) return fail("You do not have permission to issue materials.");
    const request = current.requests.find((r) => r.id === id);
    if (!request) return fail("Request not found.");
    if (request.status !== "approved") return fail("Only approved requests can be issued.");
    const project = current.projects.find((p) => p.id === request.projectId);
    if (!project) return fail("The linked project no longer exists.");

    const shortages = requestAvailability(current, request).filter((a) => !a.ok);
    if (shortages.length > 0) {
      return fail(
        `Insufficient stock: ${shortages[0].item?.name ?? "item"} needs ${shortages[0].qty}, only ${shortages[0].available} available.`
      );
    }

    const now = new Date().toISOString();
    setState((prev) => {
      let items = prev.items;
      let transactions = prev.transactions;
      request.lines.forEach((line) => {
        const item = items.find((i) => i.id === line.itemId);
        if (!item) return;
        const balance = item.qty - line.qty;
        items = items.map((i) => (i.id === line.itemId ? { ...i, qty: balance, updatedAt: now } : i));
        transactions = [
          ...transactions,
          makeTxn(prev, {
            type: "out",
            itemId: line.itemId,
            qty: line.qty,
            delta: -line.qty,
            balanceAfter: balance,
            actor: ROLE_ACTORS[prev.role].name,
            note: `Issued against ${request.id} · ${project.name}`,
            projectId: project.id,
            requestId: request.id,
            at: now,
          }),
        ];
      });

      return {
        ...prev,
        items,
        transactions: sortTxns(transactions),
        projects: prev.projects.map((p) =>
          p.id === project.id
            ? {
                ...p,
                allocations: request.lines.reduce((acc, line) => {
                  const existing = acc.find((a) => a.itemId === line.itemId);
                  if (existing) {
                    return acc.map((a) =>
                      a.itemId === line.itemId ? { ...a, issued: a.issued + line.qty } : a
                    );
                  }
                  return [...acc, { itemId: line.itemId, issued: line.qty, consumed: 0, returned: 0 }];
                }, p.allocations),
              }
            : p
        ),
        requests: prev.requests.map((r) =>
          r.id === id ? { ...r, status: "issued", issuedAt: now } : r
        ),
      };
    });
    return ok();
  }, []);

  const cancelRequest = useCallback((id: string): ActionResult => {
    const current = stateRef.current;
    const request = current.requests.find((r) => r.id === id);
    if (!request) return fail("Request not found.");
    if (request.status !== "pending") return fail("Only pending requests can be cancelled.");
    if (current.role === "student" && request.requestedBy !== ROLE_ACTORS.student.name) {
      return fail("You can only cancel your own requests.");
    }
    setState((prev) => ({
      ...prev,
      requests: prev.requests.filter((r) => r.id !== id),
    }));
    return ok();
  }, []);

  /* ---------------------------------------------------------------- */
  /* Settings                                                          */
  /* ---------------------------------------------------------------- */

  const updateSettings = useCallback((patch: Partial<Settings>): ActionResult => {
    const current = stateRef.current;
    if (!canManageSettings(current.role)) return fail("Only administrators can change organisation settings.");
    if (patch.defaultMinThreshold !== undefined && patch.defaultMinThreshold < 0) {
      return fail("The default threshold cannot be negative.");
    }
    setState((prev) => ({ ...prev, settings: { ...prev.settings, ...patch } }));
    return ok();
  }, []);

  const resetData = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setState(normalizeState(structuredClone(seedState)));
  }, []);

  const exportState = useCallback(() => JSON.stringify(stateRef.current, null, 2), []);

  const value = useMemo<StoreApi>(
    () => ({
      state,
      role: state.role,
      actorName,
      setRole,
      addItem,
      updateItem,
      deleteItem,
      adjustStock,
      stockIn,
      stockOut,
      returnStock,
      consumeMaterial,
      allocateToProject,
      saveCategory,
      deleteCategory,
      saveSupplier,
      deleteSupplier,
      addProject,
      updateProject,
      deleteProject,
      createRequest,
      approveRequest,
      rejectRequest,
      issueRequest,
      cancelRequest,
      updateSettings,
      resetData,
      exportState,
    }),
    [
      state,
      actorName,
      setRole,
      addItem,
      updateItem,
      deleteItem,
      adjustStock,
      stockIn,
      stockOut,
      returnStock,
      consumeMaterial,
      allocateToProject,
      saveCategory,
      deleteCategory,
      saveSupplier,
      deleteSupplier,
      addProject,
      updateProject,
      deleteProject,
      createRequest,
      approveRequest,
      rejectRequest,
      issueRequest,
      cancelRequest,
      updateSettings,
      resetData,
      exportState,
    ]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useApp(): StoreApi {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useApp must be used inside AppStoreProvider");
  return ctx;
}
