import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { ToastContext, type ToastApi, type ToastItem, type ToastTone } from "./toast-context";
import { createPortal } from "react-dom";
import { Icon, type IconName } from "./Icons";


const ICONS: Record<ToastTone, IconName> = {
  success: "check-circle",
  error: "alert-circle",
  info: "info",
  warning: "alert-triangle",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback<ToastApi["push"]>(
    ({ tone = "success", title, message }) => {
      counter.current += 1;
      const id = counter.current;
      setItems((prev) => [...prev.slice(-3), { id, tone, title, message }]);
      window.setTimeout(() => remove(id), 4200);
    },
    [remove]
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (title, message) => push({ tone: "success", title, message }),
      error: (title, message) => push({ tone: "error", title, message }),
      info: (title, message) => push({ tone: "info", title, message }),
      warning: (title, message) => push({ tone: "warning", title, message }),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className="toasts" aria-live="polite" aria-atomic="false">
          {items.map((t) => (
            <div key={t.id} className={`toast toast--${t.tone}`} role="status">
              <span className="toast__icon">
                <Icon name={ICONS[t.tone]} />
              </span>
              <div className="toast__body">
                <p className="toast__title">{t.title}</p>
                {t.message ? <p className="toast__text">{t.message}</p> : null}
              </div>
              <button type="button" className="toast__close" onClick={() => remove(t.id)} aria-label="Dismiss notification">
                <Icon name="x" size={12} />
              </button>
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  );
}

