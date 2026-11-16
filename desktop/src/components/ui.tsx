import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
  type CSSProperties,
  type TextareaHTMLAttributes,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { NavLink } from "react-router-dom";
import { Icon, type IconName } from "./Icons";
import { initials, stockLabel, stockTone } from "../lib/format";
import type { Category, ItemStatus } from "../lib/types";

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */

type Variant = "primary" | "secondary" | "ghost" | "soft" | "danger" | "danger-soft";
type Size = "sm" | "md" | "lg";

export function buttonClass(variant: Variant = "secondary", size: Size = "md", extra = ""): string {
  return ["btn", `btn--${variant}`, size !== "md" ? `btn--${size}` : "", extra].filter(Boolean).join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  iconRight,
  loading,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={buttonClass(variant, size, className ?? "")}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <span className="spinner" aria-hidden /> : icon ? <Icon name={icon} /> : null}
      {children}
      {iconRight ? <Icon name={iconRight} /> : null}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Badges                                                              */
/* ------------------------------------------------------------------ */

export type Tone = "green" | "amber" | "red" | "blue" | "violet" | "slate" | "olive" | "ink" | "plain";

export function Badge({
  tone = "plain",
  dot,
  children,
  outline,
  lg,
}: {
  tone?: Tone;
  dot?: boolean;
  children: ReactNode;
  outline?: boolean;
  lg?: boolean;
}) {
  const cls = [
    "badge",
    tone !== "plain" ? `badge--${tone}` : "",
    outline ? "badge--outline" : "",
    lg ? "badge--lg" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={cls}>
      {dot ? <span className="badge__dot" /> : null}
      {children}
    </span>
  );
}

export function StockBadge({ status }: { status: ItemStatus }) {
  return (
    <Badge tone={stockTone(status)} dot>
      {stockLabel(status)}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* Cards & structure                                                   */
/* ------------------------------------------------------------------ */

export function Card({
  children,
  className = "",
  flush,
  hover,
  style,
}: {
  children: ReactNode;
  className?: string;
  flush?: boolean;
  hover?: boolean;
  style?: CSSProperties;
}) {
  return (
    <div
      className={["card", flush ? "card--flush" : "", hover ? "card--hover" : "", className].filter(Boolean).join(" ")}
      style={style}
    >
      {children}
    </div>
  );
}

export function CardHead({
  title,
  sub,
  action,
}: {
  title: ReactNode;
  sub?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="card__head">
      <div>
        <h2 className="card__title">{title}</h2>
        {sub ? <p className="card__sub">{sub}</p> : null}
      </div>
      {action ? <div className="card__action">{action}</div> : null}
    </div>
  );
}

export function SectionHead({
  title,
  sub,
  actions,
}: {
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="section-head">
      <div>
        <h2 className="section-head__title">{title}</h2>
        {sub ? <p className="section-head__sub">{sub}</p> : null}
      </div>
      {actions ? <div className="section-head__actions">{actions}</div> : null}
    </div>
  );
}

export function PageHead({
  title,
  sub,
  actions,
  compact,
}: {
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`page-head${compact ? " page-head--compact" : ""}`}>
      <div>
        <h1 className="page-head__title">{title}</h1>
        {sub ? <p className="page-head__sub">{sub}</p> : null}
      </div>
      {actions ? <div className="page-head__actions">{actions}</div> : null}
    </div>
  );
}

export function StatCard({
  label,
  value,
  suffix,
  icon,
  foot,
  footRight,
  accent,
}: {
  label: string;
  value: ReactNode;
  suffix?: ReactNode;
  icon?: IconName;
  foot?: ReactNode;
  footRight?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`stat${accent ? " stat--accent" : ""}`}>
      <div className="stat__top">
        <span className="stat__label">{label}</span>
        {icon ? (
          <span className="stat__icon">
            <Icon name={icon} />
          </span>
        ) : null}
      </div>
      <div className="stat__value">
        {value}
        {suffix ? <small>{suffix}</small> : null}
      </div>
      <div className="stat__foot">
        <span>{foot}</span>
        {footRight ? <span>{footRight}</span> : null}
      </div>
    </div>
  );
}

export function MiniStat({
  label,
  value,
  suffix,
  hint,
}: {
  label: string;
  value: ReactNode;
  suffix?: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="mini-stat">
      <span>{label}</span>
      <b>
        {value}
        {suffix ? <small>{suffix}</small> : null}
      </b>
      {hint ? <em>{hint}</em> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Forms                                                               */
/* ------------------------------------------------------------------ */

export function Field({
  label,
  required,
  error,
  hint,
  htmlFor,
  children,
  className,
}: {
  label?: ReactNode;
  required?: boolean;
  error?: string;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`field ${className ?? ""}`}>
      {label ? (
        <label className="field__label" htmlFor={htmlFor}>
          {label}
          {required ? <span className="req">*</span> : null}
        </label>
      ) : null}
      {children}
      {error ? (
        <span className="field__error">
          <Icon name="alert-circle" />
          {error}
        </span>
      ) : hint ? (
        <span className="field__hint">{hint}</span>
      ) : null}
    </div>
  );
}

export function Input({ className = "", error, ...rest }: InputHTMLAttributes<HTMLInputElement> & { error?: boolean }) {
  return <input className={`input ${error ? "input--error" : ""} ${className}`} {...rest} />;
}

export function Textarea({
  className = "",
  error,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { error?: boolean }) {
  return <textarea className={`textarea ${error ? "input--error" : ""} ${className}`} {...rest} />;
}

export function Select({
  className = "",
  error,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { error?: boolean }) {
  return (
    <span className="select-wrap">
      <select className={`select ${error ? "select--error" : ""} ${className}`} {...rest}>
        {children}
      </select>
      <Icon name="chevron-down" className="chev" />
    </span>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder = "Search…",
  className = "",
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <div className={`input-wrap ${className}`}>
      <Icon name="search" />
      <input
        className="input input--search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
      />
      {value ? (
        <button type="button" className="input-wrap__clear" onClick={() => onChange("")} aria-label="Clear search">
          <Icon name="x" />
        </button>
      ) : null}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="switch"
      data-on={checked}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Modal / drawer                                                      */
/* ------------------------------------------------------------------ */

function useLockBody(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [active]);
}

export function Modal({
  open,
  onClose,
  title,
  sub,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  sub?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const id = useId();
  useLockBody(open);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`modal modal--${size}`} role="dialog" aria-modal="true" aria-labelledby={id}>
        <div className="modal__head">
          <div>
            <h2 className="modal__title" id={id}>
              {title}
            </h2>
            {sub ? <p className="modal__sub">{sub}</p> : null}
          </div>
          <button type="button" className="icon-btn modal__close" onClick={onClose} aria-label="Close dialog">
            <Icon name="x" />
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer ? <div className="modal__foot">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export function Drawer({
  open,
  onClose,
  title,
  sub,
  children,
  footer,
  width,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  sub?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  useLockBody(open);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : "Details"}
        style={width ? { width } : undefined}
      >
        <div className="drawer__head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="modal__title">{title}</h2>
            {sub ? <p className="modal__sub">{sub}</p> : null}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close panel">
            <Icon name="x" />
          </button>
        </div>
        <div className="drawer__body">{children}</div>
        {footer ? <div className="drawer__foot">{footer}</div> : null}
      </aside>
    </div>,
    document.body
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "danger",
  onConfirm,
  onClose,
  children,
}: {
  open: boolean;
  title: ReactNode;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            {cancelLabel}
          </button>
          <button type="button" className={`btn btn--${tone}`} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </>
      }
    >
      {message ? <p style={{ fontSize: 12.5, color: "var(--ink-3)", lineHeight: 1.65 }}>{message}</p> : null}
      {children}
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Menus                                                               */
/* ------------------------------------------------------------------ */

export type MenuItem = {
  label: string;
  icon?: IconName;
  onClick: () => void;
  danger?: boolean;
  hidden?: boolean;
};

export function RowMenu({
  items,
  label = "Row actions",
  align = "right",
}: {
  items: MenuItem[];
  label?: string;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const visible = items.filter((i) => !i.hidden);
  if (visible.length === 0) return null;

  return (
    <div className="popover-wrap" ref={wrapRef}>
      <button
        type="button"
        className="icon-btn"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="more" />
      </button>
      {open ? (
        <div className={`menu${align === "left" ? " menu--left" : ""}`} role="menu">
          {visible.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={`menu__item${item.danger ? " menu__item--danger" : ""}`}
              onClick={() => {
                setOpen(false);
                item.onClick();
              }}
            >
              {item.icon ? <Icon name={item.icon} /> : null}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Misc display                                                        */
/* ------------------------------------------------------------------ */

const AVATAR_TONES = ["olive", "sand", "blue", "rose", "violet", "slate"];

export function avatarTone(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) % 997;
  return AVATAR_TONES[hash % AVATAR_TONES.length];
}

export function Avatar({ name, size, tone }: { name: string; size?: "sm" | "lg"; tone?: string }) {
  return (
    <span className={`avatar avatar--${tone ?? avatarTone(name)}${size ? ` avatar--${size}` : ""}`} title={name}>
      {initials(name)}
    </span>
  );
}

export function AvatarStack({ names, max = 3 }: { names: string[]; max?: number }) {
  const shown = names.slice(0, max);
  const rest = names.length - shown.length;
  return (
    <span className="avatar-stack">
      {shown.map((n) => (
        <Avatar key={n} name={n} size="sm" />
      ))}
      {rest > 0 ? <span className="avatar avatar--sm avatar--slate">+{rest}</span> : null}
    </span>
  );
}

export function ItemThumb({
  category,
  size,
}: {
  category?: Category;
  size?: "sm" | "lg";
}) {
  const color = category?.color ?? "#757575";
  return (
    <span
      className={`thumb${size ? ` thumb--${size}` : ""}`}
      style={{ background: `${color}14`, color }}
      aria-hidden="true"
    >
      <Icon name={(category?.icon ?? "package") as IconName} />
    </span>
  );
}

export function Bar({ value, tone }: { value: number; tone?: "green" | "amber" | "red" | "olive" | "slate" }) {
  return (
    <span className="bar">
      <span
        className={`bar__fill${tone ? ` bar__fill--${tone}` : ""}`}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </span>
  );
}

export function EmptyState({
  icon = "inbox",
  title,
  text,
  action,
  small,
}: {
  icon?: IconName;
  title: string;
  text?: ReactNode;
  action?: ReactNode;
  small?: boolean;
}) {
  return (
    <div className={`empty${small ? " empty--sm" : ""}`}>
      <span className="empty__icon">
        <Icon name={icon} />
      </span>
      <p className="empty__title">{title}</p>
      {text ? <p className="empty__text">{text}</p> : null}
      {action ? <div className="empty__action">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ width, height, radius }: { width?: number | string; height?: number; radius?: number }) {
  return (
    <span
      className="sk"
      style={{ width: width ?? "100%", height: height ?? 12, display: "block", borderRadius: radius ?? 6 }}
    />
  );
}

export function SkeletonTable({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div style={{ padding: 18 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} height={9} width={i === 0 ? 140 : 80} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 14 }}>
          <Skeleton height={30} width={30} radius={9} />
          {Array.from({ length: cols - 1 }).map((__, j) => (
            <Skeleton key={j} height={10} width={j === 0 ? 160 : 70} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function Notice({
  tone,
  icon = "info",
  children,
}: {
  tone?: "amber" | "red" | "green";
  icon?: IconName;
  children: ReactNode;
}) {
  return (
    <div className={`notice${tone ? ` notice--${tone}` : ""}`}>
      <Icon name={icon} />
      <div>{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pagination                                                          */
/* ------------------------------------------------------------------ */

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
  onPageSize?: (n: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  const pages = useMemo(() => {
    const list: Array<number | "…"> = [];
    if (pageCount <= 7) {
      for (let i = 1; i <= pageCount; i += 1) list.push(i);
    } else {
      list.push(1);
      if (page > 3) list.push("…");
      for (let i = Math.max(2, page - 1); i <= Math.min(pageCount - 1, page + 1); i += 1) list.push(i);
      if (page < pageCount - 2) list.push("…");
      list.push(pageCount);
    }
    return list;
  }, [page, pageCount]);

  return (
    <div className="pager">
      <div className="pager__info">
        Showing <b>{from}</b>–<b>{to}</b> of <b>{total}</b>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {onPageSize ? (
          <div className="select-wrap" style={{ width: 100 }}>
            <select
              className="select filter-select"
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              aria-label="Rows per page"
              style={{ minWidth: 0, height: 30, fontSize: 11 }}
            >
              {[8, 12, 20, 40].map((n) => (
                <option key={n} value={n}>
                  {n} rows
                </option>
              ))}
            </select>
            <Icon name="chevron-down" className="chev" />
          </div>
        ) : null}
        <div className="pager__pages">
          <button
            type="button"
            className="page-btn"
            onClick={() => onPage(page - 1)}
            disabled={page <= 1}
            aria-label="Previous page"
          >
            <Icon name="chevron-left" />
          </button>
          {pages.map((p, i) =>
            p === "…" ? (
              <span key={`e${i}`} className="page-btn" style={{ pointerEvents: "none" }}>
                …
              </span>
            ) : (
              <button
                type="button"
                key={p}
                className={`page-btn${p === page ? " is-active" : ""}`}
                onClick={() => onPage(p)}
                aria-current={p === page ? "page" : undefined}
              >
                {p}
              </button>
            )
          )}
          <button
            type="button"
            className="page-btn"
            onClick={() => onPage(page + 1)}
            disabled={page >= pageCount}
            aria-label="Next page"
          >
            <Icon name="chevron-right" />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tabs                                                                */
/* ------------------------------------------------------------------ */

export function Segments({
  items,
}: {
  items: Array<{ to: string; label: string; count?: number; end?: boolean }>;
}) {
  return (
    <div className="segmented" role="navigation">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => (isActive ? "is-active" : undefined)}
        >
          {item.label}
          {item.count !== undefined ? <span className="segmented__count">{item.count}</span> : null}
        </NavLink>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sortable table header                                               */
/* ------------------------------------------------------------------ */

export function SortTh({
  label,
  active,
  dir,
  onClick,
  align,
  width,
}: {
  label: string;
  active?: boolean;
  dir?: "asc" | "desc";
  onClick: () => void;
  align?: "right";
  width?: number;
}) {
  return (
    <th className={`is-sortable${align === "right" ? " num" : ""}`} style={width ? { width } : undefined}>
      <button type="button" className={`th-sort${active ? " is-active" : ""}`} onClick={onClick}>
        {label}
        <Icon name={active ? (dir === "asc" ? "chevron-up" : "chevron-down") : "chevron-down"} />
      </button>
    </th>
  );
}

/* ------------------------------------------------------------------ */
/* Popover shell (search / notifications)                              */
/* ------------------------------------------------------------------ */

export function useOutsideClose(active: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!active) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [active, onClose]);
  return ref;
}
