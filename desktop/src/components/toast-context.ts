import { createContext } from "react";

export type ToastTone = "success" | "error" | "info" | "warning";
export type ToastItem = {
  id: number;
  tone: ToastTone;
  title: string;
  message?: string;
};
export type ToastApi = {
  push: (t: { tone?: ToastTone; title: string; message?: string }) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
};
export const ToastContext = createContext<ToastApi | null>(null);
