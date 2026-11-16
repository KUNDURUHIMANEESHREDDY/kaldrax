import type { Actor, Role } from "./types";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrator",
  supervisor: "Faculty supervisor",
  student: "Student",
};

export const ROLE_ACTORS: Record<Role, Actor> = {
  admin: { name: "Himaneesh Reddy", role: "admin", email: "himaneesh@meridian.edu.in" },
  supervisor: { name: "Dr. Ananya Rao", role: "supervisor", email: "ananya.rao@meridian.edu.in" },
  student: { name: "Aarav Sharma", role: "student", email: "aarav.s26@meridian.edu.in" },
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  admin: "Full access to inventory, projects, approvals and settings.",
  supervisor: "Manage materials and projects, review and issue student requests.",
  student: "Browse inventory and submit material requests for your project.",
};

export function canManageInventory(role: Role): boolean {
  return role === "admin" || role === "supervisor";
}

export function canDeleteRecords(role: Role): boolean {
  return role === "admin";
}

export function canApproveRequests(role: Role): boolean {
  return role === "admin" || role === "supervisor";
}

export function canManageProjects(role: Role): boolean {
  return role !== "student";
}

export function canManageSettings(role: Role): boolean {
  return role === "admin";
}

export function canViewReports(role: Role): boolean {
  return role !== "student";
}
