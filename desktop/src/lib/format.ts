import type { Item, ItemStatus, Priority, ProjectStatus, RequestStatus } from "./types";

export const inrFmt = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export const numFmt = new Intl.NumberFormat("en-IN");

export function inr(n: number): string {
  return inrFmt.format(Math.round(n || 0));
}

export function inrCompact(n: number): string {
  if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (Math.abs(n) >= 1000) return `₹${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return `₹${Math.round(n)}`;
}

export function num(n: number): string {
  return numFmt.format(Math.round(n || 0));
}

export function qtyLabel(qty: number, unit: string): string {
  return `${num(qty)} ${unit}`;
}

export function dateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function dateMedium(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export function dateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}, ${d.toLocaleTimeString(
    "en-IN",
    { hour: "2-digit", minute: "2-digit" }
  )}`;
}

export function timeShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export function relTime(iso: string): string {
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const diff = Date.now() - d;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.round(days / 7)}w ago`;
  return dateMedium(iso);
}

export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

export function itemStatus(item: Pick<Item, "qty" | "minQty">): ItemStatus {
  if (item.qty <= 0) return "out-of-stock";
  if (item.qty <= item.minQty) return "low-stock";
  return "in-stock";
}

export function stockLabel(status: ItemStatus): string {
  return status === "in-stock" ? "In stock" : status === "low-stock" ? "Low stock" : "Out of stock";
}

export function stockTone(status: ItemStatus): "green" | "amber" | "red" {
  return status === "in-stock" ? "green" : status === "low-stock" ? "amber" : "red";
}

export function projectStatusLabel(status: ProjectStatus): string {
  return status === "active"
    ? "Active"
    : status === "planning"
      ? "Planning"
      : status === "on-hold"
        ? "On hold"
        : "Completed";
}

export function projectStatusTone(status: ProjectStatus): "green" | "blue" | "amber" | "slate" {
  return status === "active" ? "green" : status === "planning" ? "blue" : status === "on-hold" ? "amber" : "slate";
}

export function requestStatusLabel(status: RequestStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function requestStatusTone(status: RequestStatus): "amber" | "blue" | "red" | "green" | "slate" {
  return status === "pending"
    ? "amber"
    : status === "approved"
      ? "blue"
      : status === "rejected"
        ? "red"
        : status === "issued"
          ? "green"
          : "slate";
}

export function priorityTone(p: Priority): "slate" | "blue" | "amber" | "red" {
  return p === "urgent" ? "red" : p === "high" ? "amber" : p === "normal" ? "slate" : "blue";
}

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function daysBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.round(ms / 86400000);
}

const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
export function plainNum(n: number): string {
  return INR.format(n);
}

export function stem(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}
