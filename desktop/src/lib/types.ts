export type Role = "admin" | "supervisor" | "student";

export type ItemStatus = "in-stock" | "low-stock" | "out-of-stock";

export type ProjectStatus = "planning" | "active" | "on-hold" | "completed";

export type RequestStatus = "pending" | "approved" | "rejected" | "issued" | "returned";

export type Priority = "low" | "normal" | "high" | "urgent";

export type TransactionType = "in" | "out" | "adjust" | "return";

export interface Category {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
}

export interface Supplier {
  id: string;
  name: string;
  contactName: string;
  email: string;
  phone: string;
  city: string;
  leadTimeDays: number;
  rating: number;
  categoryIds: string[];
  onTimePct: number;
  notes?: string;
}

export interface Item {
  id: string;
  name: string;
  categoryId: string;
  description: string;
  qty: number;
  minQty: number;
  unit: string;
  location: string;
  supplierId: string;
  unitCost: number;
  createdAt: string;
  updatedAt: string;
}

export interface Allocation {
  itemId: string;
  issued: number;
  consumed: number;
  returned: number;
}

export interface RequiredMaterial {
  name: string;
  qty: number;
  unit: string;
  itemId?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  team: string[];
  supervisor: string;
  startDate: string;
  endDate: string;
  status: ProjectStatus;
  allocations: Allocation[];
  required: RequiredMaterial[];
}

export interface Transaction {
  id: string;
  type: TransactionType;
  itemId: string;
  qty: number;
  delta: number;
  balanceAfter: number;
  projectId?: string;
  requestId?: string;
  supplierId?: string;
  actor: string;
  note: string;
  at: string;
}

export interface RequestLine {
  itemId: string;
  qty: number;
}

export interface MaterialRequest {
  id: string;
  projectId: string;
  requestedBy: string;
  lines: RequestLine[];
  status: RequestStatus;
  priority: Priority;
  note: string;
  createdAt: string;
  reviewedAt?: string;
  reviewedBy?: string;
  rejectReason?: string;
  issuedAt?: string;
  returnedAt?: string;
}

export interface Settings {
  orgName: string;
  campus: string;
  currency: "INR";
  defaultMinThreshold: number;
  lowStockAlerts: boolean;
  requestAlerts: boolean;
  weeklyDigest: boolean;
  requireApproval: boolean;
  allowStudentRequests: boolean;
  semester: string;
}

export interface Actor {
  name: string;
  role: Role;
  email: string;
}

export interface AppState {
  items: Item[];
  categories: Category[];
  suppliers: Supplier[];
  projects: Project[];
  transactions: Transaction[];
  requests: MaterialRequest[];
  settings: Settings;
  role: Role;
}

export interface ItemInput {
  name: string;
  categoryId: string;
  description: string;
  qty: number;
  minQty: number;
  unit: string;
  location: string;
  supplierId: string;
  unitCost: number;
  openingNote?: string;
}

export interface ProjectInput {
  name: string;
  description: string;
  team: string[];
  supervisor: string;
  startDate: string;
  endDate: string;
  status: ProjectStatus;
  required: RequiredMaterial[];
}

export interface RequestInput {
  projectId: string;
  requestedBy: string;
  priority: Priority;
  note: string;
  lines: RequestLine[];
}
