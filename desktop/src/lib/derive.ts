import type {
  AppState,
  Category,
  Item,
  MaterialRequest,
  Project,
  Supplier,
  Transaction,
} from "./types";
import { dayLabel, itemStatus, num, daysBetween } from "./format";

/* ------------------------------------------------------------------ */
/* Lookups                                                             */
/* ------------------------------------------------------------------ */

export function itemById(state: AppState, id: string): Item | undefined {
  return state.items.find((i) => i.id === id);
}

export function categoryById(state: AppState, id: string): Category | undefined {
  return state.categories.find((c) => c.id === id);
}

export function supplierById(state: AppState, id: string): Supplier | undefined {
  return state.suppliers.find((s) => s.id === id);
}

export function projectById(state: AppState, id: string): Project | undefined {
  return state.projects.find((p) => p.id === id);
}

export function projectName(state: AppState, id?: string): string {
  if (!id) return "—";
  return projectById(state, id)?.name ?? id;
}

export function requestById(state: AppState, id: string): MaterialRequest | undefined {
  return state.requests.find((r) => r.id === id);
}

export function transactionsForItem(state: AppState, itemId: string): Transaction[] {
  return state.transactions
    .filter((t) => t.itemId === itemId)
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
}

/* ------------------------------------------------------------------ */
/* Stock aggregates                                                    */
/* ------------------------------------------------------------------ */

export function stockSummary(state: AppState) {
  const totalItems = state.items.length;
  const totalAvailable = state.items.reduce((sum, i) => sum + i.qty, 0);
  const low = state.items.filter((i) => itemStatus(i) === "low-stock");
  const out = state.items.filter((i) => itemStatus(i) === "out-of-stock");
  const activeProjects = state.projects.filter((p) => p.status === "active").length;
  const pending = state.requests.filter((r) => r.status === "pending").length;
  const value = state.items.reduce((sum, i) => sum + i.qty * i.unitCost, 0);
  const valueLow = low.reduce((sum, i) => sum + i.qty * i.unitCost, 0);
  const healthScore = Math.max(
    32,
    Math.min(100, Math.round(100 - low.length * 3 - out.length * 7 - (pending > 5 ? 4 : 0)))
  );
  return {
    totalItems,
    totalAvailable,
    low,
    out,
    activeProjects,
    pending,
    value,
    valueLow,
    healthScore,
  };
}

export function categoryStats(state: AppState) {
  return state.categories
    .map((category) => {
      const items = state.items.filter((i) => i.categoryId === category.id);
      return {
        category,
        count: items.length,
        qty: items.reduce((s, i) => s + i.qty, 0),
        value: items.reduce((s, i) => s + i.qty * i.unitCost, 0),
        low: items.filter((i) => itemStatus(i) !== "in-stock").length,
      };
    })
    .sort((a, b) => b.value - a.value);
}

/* ------------------------------------------------------------------ */
/* Movement series                                                     */
/* ------------------------------------------------------------------ */

export type MovementPoint = {
  key: string;
  label: string;
  received: number;
  issued: number;
  returned: number;
};

export function movementSeries(state: AppState, days = 30): MovementPoint[] {
  const points: MovementPoint[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const buckets = new Map<string, { received: number; issued: number; returned: number }>();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toDateString();
    buckets.set(key, { received: 0, issued: 0, returned: 0 });
    points.push({ key, label: dayLabel(d.toISOString()), received: 0, issued: 0, returned: 0 });
  }

  state.transactions.forEach((t) => {
    const d = new Date(t.at);
    const key = new Date(d.getFullYear(), d.getMonth(), d.getDate()).toDateString();
    const bucket = buckets.get(key);
    if (!bucket) return;
    if (t.type === "in") bucket.received += t.qty;
    else if (t.type === "out") bucket.issued += t.qty;
    else if (t.type === "return") bucket.returned += t.qty;
    else if (t.type === "adjust" && t.delta < 0) bucket.issued += Math.abs(t.delta);
  });

  points.forEach((p) => {
    const b = buckets.get(p.key);
    if (b) {
      p.received = b.received;
      p.issued = b.issued;
      p.returned = b.returned;
    }
  });

  return points;
}

export function weeklyMovement(state: AppState, weeks = 12): MovementPoint[] {
  const points: MovementPoint[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let w = weeks - 1; w >= 0; w -= 1) {
    const end = new Date(today);
    end.setDate(end.getDate() - w * 7);
    const start = new Date(end);
    start.setDate(start.getDate() - 6);
    points.push({
      key: start.toISOString(),
      label: `${start.getDate()} ${start.toLocaleDateString("en-IN", { month: "short" })}`,
      received: 0,
      issued: 0,
      returned: 0,
    });
    state.transactions.forEach((t) => {
      const at = new Date(t.at);
      if (at >= start && at <= new Date(end.getTime() + 86399999)) {
        const p = points[points.length - 1];
        if (t.type === "in") p.received += t.qty;
        else if (t.type === "out") p.issued += t.qty;
        else if (t.type === "return") p.returned += t.qty;
        else if (t.type === "adjust" && t.delta < 0) p.issued += Math.abs(t.delta);
      }
    });
  }
  return points;
}

/* ------------------------------------------------------------------ */
/* Usage analytics                                                     */
/* ------------------------------------------------------------------ */

export function mostUsedItems(state: AppState, limit = 6) {
  const map = new Map<string, { qty: number; out: number; projects: Set<string> }>();
  state.transactions.forEach((t) => {
    if (t.type !== "out") return;
    const row = map.get(t.itemId) ?? { qty: 0, out: 0, projects: new Set<string>() };
    row.qty += t.qty;
    row.out += 1;
    if (t.projectId) row.projects.add(t.projectId);
    map.set(t.itemId, row);
  });
  return [...map.entries()]
    .map(([itemId, row]) => ({
      item: itemById(state, itemId),
      qty: row.qty,
      movements: row.out,
      projects: row.projects.size,
      value: row.qty * (itemById(state, itemId)?.unitCost ?? 0),
    }))
    .filter((r) => Boolean(r.item))
    .sort((a, b) => b.qty - a.qty)
    .slice(0, limit);
}

export function projectStats(state: AppState, project: Project) {
  let issued = 0;
  let consumed = 0;
  let returned = 0;
  let consumedValue = 0;
  project.allocations.forEach((a) => {
    const item = itemById(state, a.itemId);
    issued += a.issued;
    consumed += a.consumed;
    returned += a.returned;
    consumedValue += a.consumed * (item?.unitCost ?? 0);
  });
  const inUse = Math.max(0, issued - consumed - returned);
  const progress = issued > 0 ? Math.round(((consumed + returned) / issued) * 100) : 0;
  return {
    issued,
    consumed,
    returned,
    inUse,
    progress: Math.min(100, progress),
    consumedValue,
    lines: project.allocations.length,
  };
}

export function projectActivity(state: AppState, projectId: string, limit = 8) {
  return state.transactions
    .filter((t) => t.projectId === projectId)
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, limit);
}

export function allocationFor(project: Project, itemId: string) {
  return project.allocations.find((a) => a.itemId === itemId);
}

export function requestAvailability(state: AppState, request: MaterialRequest) {
  return request.lines.map((line) => {
    const item = itemById(state, line.itemId);
    const available = item?.qty ?? 0;
    return {
      item,
      qty: line.qty,
      available,
      ok: available >= line.qty,
      shortfall: Math.max(0, line.qty - available),
    };
  });
}

export function requestValue(state: AppState, request: MaterialRequest): number {
  return request.lines.reduce((sum, l) => {
    const item = itemById(state, l.itemId);
    return sum + (item ? item.unitCost * l.qty : 0);
  }, 0);
}

/* ------------------------------------------------------------------ */
/* Activity feed                                                       */
/* ------------------------------------------------------------------ */

export type ActivityKind = "in" | "out" | "return" | "adjust" | "item" | "request" | "approval";

export type ActivityEntry = {
  id: string;
  kind: ActivityKind;
  title: string;
  meta: string;
  at: string;
  href?: string;
};

export function activityFeed(state: AppState, limit = 8): ActivityEntry[] {
  const entries: ActivityEntry[] = [];

  state.transactions.forEach((t) => {
    if (t.note.startsWith("Opening stock")) return;
    const item = itemById(state, t.itemId);
    if (!item) return;
    const project = t.projectId ? projectById(state, t.projectId) : undefined;
    if (t.type === "in") {
      entries.push({
        id: t.id,
        kind: "in",
        title: `Received ${num(t.qty)} ${item.unit} of ${item.name}`,
        meta: project ? project.name : `Stock in · ${t.actor}`,
        at: t.at,
        href: `/inventory?item=${item.id}`,
      });
    } else if (t.type === "out") {
      entries.push({
        id: t.id,
        kind: "out",
        title: `Issued ${num(t.qty)} ${item.unit} of ${item.name}`,
        meta: project ? `To ${project.name}` : `Stock out · ${t.actor}`,
        at: t.at,
        href: project ? `/projects/${project.id}` : `/inventory?item=${item.id}`,
      });
    } else if (t.type === "return") {
      entries.push({
        id: t.id,
        kind: "return",
        title: `Returned ${num(t.qty)} ${item.unit} of ${item.name}`,
        meta: project ? `From ${project.name}` : "Returned to store",
        at: t.at,
        href: project ? `/projects/${project.id}` : "/transactions/returns",
      });
    } else {
      entries.push({
        id: t.id,
        kind: "adjust",
        title: `${t.delta >= 0 ? "Increased" : "Reduced"} ${item.name} by ${num(Math.abs(t.delta))} ${item.unit}`,
        meta: t.note,
        at: t.at,
        href: `/inventory?item=${item.id}`,
      });
    }
  });

  state.requests.forEach((r) => {
    const project = projectById(state, r.projectId);
    const lines = r.lines.length;
    if (r.status === "pending") {
      entries.push({
        id: `${r.id}-submitted`,
        kind: "request",
        title: `${r.requestedBy} submitted ${r.id}`,
        meta: `${project?.name ?? r.projectId} · ${lines} line item${lines === 1 ? "" : "s"}`,
        at: r.createdAt,
        href: "/requests/pending",
      });
    } else if (r.status === "approved" && r.reviewedAt) {
      entries.push({
        id: `${r.id}-approved`,
        kind: "approval",
        title: `${r.id} approved by ${r.reviewedBy ?? "administrator"}`,
        meta: `${project?.name ?? r.projectId} · ready to issue`,
        at: r.reviewedAt,
        href: "/requests/approved",
      });
    } else if (r.status === "issued" && r.issuedAt) {
      entries.push({
        id: `${r.id}-issued`,
        kind: "out",
        title: `Materials issued for ${r.id}`,
        meta: `${project?.name ?? r.projectId} · ${lines} line item${lines === 1 ? "" : "s"}`,
        at: r.issuedAt,
        href: "/requests/history",
      });
    }
  });

  state.items.forEach((item) => {
    const age = daysBetween(item.createdAt, new Date().toISOString());
    if (age <= 45) {
      entries.push({
        id: `${item.id}-created`,
        kind: "item",
        title: `${item.name} added to inventory`,
        meta: `${item.id} · ${num(item.qty)} ${item.unit} on hand`,
        at: item.createdAt,
        href: `/inventory?item=${item.id}`,
      });
    }
  });

  return entries.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()).slice(0, limit);
}

/* ------------------------------------------------------------------ */
/* Notifications & alerts                                              */
/* ------------------------------------------------------------------ */

export function alerts(state: AppState) {
  const pending = state.requests.filter((r) => r.status === "pending");
  const low = state.items.filter((i) => itemStatus(i) !== "in-stock");
  const endingSoon = state.projects.filter(
    (p) => p.status === "active" && daysBetween(new Date().toISOString(), p.endDate) <= 21
  );
  return { pending, low, endingSoon };
}

/* ------------------------------------------------------------------ */
/* Supplier analytics                                                  */
/* ------------------------------------------------------------------ */

export function supplierStats(state: AppState, supplier: Supplier) {
  const items = state.items.filter((i) => i.supplierId === supplier.id);
  const qty = items.reduce((s, i) => s + i.qty, 0);
  const value = items.reduce((s, i) => s + i.qty * i.unitCost, 0);
  const low = items.filter((i) => itemStatus(i) !== "in-stock").length;
  const received = state.transactions
    .filter((t) => t.supplierId === supplier.id && t.type === "in")
    .reduce((s, t) => s + t.qty, 0);
  return { items, qty, value, low, received };
}

/* ------------------------------------------------------------------ */
/* Search                                                              */
/* ------------------------------------------------------------------ */

export function searchAll(state: AppState, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return { items: [], projects: [], suppliers: [], requests: [] };
  const match = (s: string) => s.toLowerCase().includes(q);
  return {
    items: state.items
      .filter(
        (i) =>
          match(i.name) ||
          match(i.id) ||
          match(i.location) ||
          match(categoryById(state, i.categoryId)?.name ?? "")
      )
      .slice(0, 6),
    projects: state.projects.filter((p) => match(p.name) || match(p.id) || match(p.supervisor)).slice(0, 4),
    suppliers: state.suppliers.filter((s) => match(s.name) || match(s.city)).slice(0, 3),
    requests: state.requests.filter((r) => match(r.id) || match(r.requestedBy)).slice(0, 3),
  };
}

/* ------------------------------------------------------------------ */
/* Reports                                                             */
/* ------------------------------------------------------------------ */

export function consumptionByCategory(state: AppState) {
  const map = new Map<string, number>();
  state.transactions.forEach((t) => {
    if (t.type !== "out") return;
    const item = itemById(state, t.itemId);
    if (!item) return;
    map.set(item.categoryId, (map.get(item.categoryId) ?? 0) + t.qty * item.unitCost);
  });
  return state.categories
    .map((c) => ({ category: c, value: map.get(c.id) ?? 0 }))
    .sort((a, b) => b.value - a.value);
}

export function monthlyMovement(state: AppState, months = 6) {
  const out: { label: string; received: number; issued: number; returned: number }[] = [];
  const now = new Date();
  for (let m = months - 1; m >= 0; m -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - m, 1);
    out.push({
      label: d.toLocaleDateString("en-IN", { month: "short" }),
      received: 0,
      issued: 0,
      returned: 0,
    });
  }
  const startMonth = new Date(now.getFullYear(), now.getMonth() - (months - 1), 1);
  state.transactions.forEach((t) => {
    const at = new Date(t.at);
    if (at < startMonth) return;
    const idx = (at.getFullYear() - startMonth.getFullYear()) * 12 + (at.getMonth() - startMonth.getMonth());
    const bucket = out[idx];
    if (!bucket) return;
    if (t.type === "in") bucket.received += t.qty;
    else if (t.type === "out") bucket.issued += t.qty;
    else if (t.type === "return") bucket.returned += t.qty;
  });
  return out;
}
