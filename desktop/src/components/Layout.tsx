import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useApp } from "../store/AppStore";
import { alerts, searchAll, categoryById } from "../lib/derive";
import { ROLE_ACTORS, ROLE_LABELS } from "../lib/permissions";
import { Icon, BrandGlyph, type IconName } from "./Icons";
import { Avatar, ItemThumb, useOutsideClose } from "./ui";
import { itemStatus } from "../lib/format";
import type { Role } from "../lib/types";

type NavChild = { label: string; to: string };

type NavItem = {
  label: string;
  icon: IconName;
  to: string;
  base?: string;
  children?: NavChild[];
  badge?: number;
  adminOnly?: boolean;
};

const PIN_KEY = "inventra.rail.pinned";

export function useRailBadges() {
  const { state } = useApp();
  const low = state.items.filter((i) => itemStatus(i) !== "in-stock").length;
  const pending = state.requests.filter((r) => r.status === "pending").length;
  return { low, pending };
}

function NavItems({
  onNavigate,
  mobile,
}: {
  onNavigate?: () => void;
  mobile?: boolean;
}) {
  const { state, role } = useApp();
  const location = useLocation();
  const badges = useRailBadges();

  const items: NavItem[] = [
    { label: "Overview", icon: "grid", to: "/", base: "/", },
    {
      label: "Inventory",
      icon: "package",
      to: "/inventory",
      base: "/inventory",
      badge: badges.low,
      children: [
        { label: "All items", to: "/inventory" },
        { label: "Categories", to: "/inventory/categories" },
        { label: "Stock levels", to: "/inventory/stock-levels" },
      ],
    },
    {
      label: "Projects",
      icon: "layers",
      to: "/projects",
      base: "/projects",
      children: [
        { label: "All projects", to: "/projects" },
        { label: "Project inventory", to: "/projects/inventory" },
      ],
    },
    {
      label: "Transactions",
      icon: "swap",
      to: "/transactions/in",
      base: "/transactions",
      children: [
        { label: "Stock in", to: "/transactions/in" },
        { label: "Stock out", to: "/transactions/out" },
        { label: "Returns", to: "/transactions/returns" },
        { label: "History", to: "/transactions/history" },
      ],
    },
    {
      label: "Requests",
      icon: "inbox",
      to: "/requests/pending",
      base: "/requests",
      badge: badges.pending,
      children: [
        { label: "Pending requests", to: "/requests/pending" },
        { label: "Approved", to: "/requests/approved" },
        { label: "Request history", to: "/requests/history" },
      ],
    },
    { label: "Suppliers", icon: "truck", to: "/suppliers", base: "/suppliers" },
    { label: "Reports", icon: "chart", to: "/reports", base: "/reports", adminOnly: false },
  ];

  const isGroupActive = (item: NavItem) => {
    if (item.base === "/") return location.pathname === "/";
    return location.pathname === item.base || location.pathname.startsWith(`${item.base}/`);
  };

  return (
    <nav className="rail__nav" aria-label="Main navigation">
      {items.map((item) => {
        const active = isGroupActive(item);
        const showBadge = item.badge && item.badge > 0;
        return (
          <div key={item.label} className={`rail__group${active && item.children ? " is-open" : ""}`}>
            <NavLink
              to={item.to}
              end={item.base === "/"}
              onClick={onNavigate}
              className={`rail__link${active ? " is-active" : ""}`}
              aria-current={active ? "page" : undefined}
              title={item.label}
            >
              <Icon name={item.icon} />
              <span className="rail__label">{item.label}</span>
              {showBadge ? <span className="rail__badge">{item.badge}</span> : null}
            </NavLink>
            {item.children ? (
              <div className="rail__children">
                {item.children.map((child) => (
                  <NavLink
                    key={child.to}
                    to={child.to}
                    end
                    onClick={onNavigate}
                    className={({ isActive }) => `rail__child${isActive ? " is-active" : ""}`}
                  >
                    {child.label}
                  </NavLink>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
      {role !== "student" ? null : <span className="sr-only">Student access: requests and read-only inventory</span>}
      {!mobile && state.role === "student" ? null : null}
    </nav>
  );
}

export function Sidebar({
  mobileOpen,
  onCloseMobile,
}: {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const { role } = useApp();
  const [pinned, setPinned] = useState(() => {
    try {
      return localStorage.getItem(PIN_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(PIN_KEY, pinned ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [pinned]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseMobile();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen, onCloseMobile]);

  const actor = ROLE_ACTORS[role];

  const content = (mobile: boolean) => (
    <>
      <div className="rail__top">
        <Link to="/" className="brandmark" aria-label="Inventra home" onClick={mobile ? onCloseMobile : undefined}>
          <BrandGlyph />
        </Link>
        <div className="rail__word">
          <strong>Inventra</strong>
          <span>PBL Inventory</span>
        </div>
      </div>

      <Link
        to={role === "student" ? "/requests/pending?new=1" : "/inventory?new=1"}
        className="rail__quick"
        title={role === "student" ? "New material request" : "Add inventory item"}
        onClick={mobile ? onCloseMobile : undefined}
      >
        <Icon name="plus" />
        <span>{role === "student" ? "New request" : "Add item"}</span>
      </Link>

      <NavItems onNavigate={mobile ? onCloseMobile : undefined} mobile={mobile} />

      <div className="rail__spacer" />

      <div className="rail__footer">
        <NavLink
          to="/settings"
          onClick={mobile ? onCloseMobile : undefined}
          className={({ isActive }) => `rail__link${isActive ? " is-active" : ""}`}
          title="Settings"
        >
          <Icon name="settings" />
          <span className="rail__label">Settings</span>
        </NavLink>

        <div className="rail__user">
          <Avatar name={actor.name} />
          <div className="rail__user-meta">
            <strong>{actor.name}</strong>
            <span>{ROLE_LABELS[role]}</span>
          </div>
        </div>
      </div>

      {!mobile ? (
        <button
          type="button"
          className="rail__pin"
          onClick={() => setPinned((v) => !v)}
          aria-label={pinned ? "Collapse navigation" : "Pin navigation open"}
          title={pinned ? "Collapse navigation" : "Pin navigation open"}
        >
          <Icon name={pinned ? "chevrons-left" : "chevrons-right"} size={14} />
        </button>
      ) : null}
    </>
  );

  return (
    <>
      <aside className="rail" data-pinned={pinned} aria-label="Primary">
        {content(false)}
      </aside>

      {mobileOpen ? (
        <>
          <div className="rail-overlay" onClick={onCloseMobile} />
          <aside className="rail rail--mobile" aria-label="Primary navigation">
            {content(true)}
          </aside>
        </>
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Global search                                                       */
/* ------------------------------------------------------------------ */

function GlobalSearch() {
  const { state } = useApp();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useOutsideClose(open, () => setOpen(false));
  const results = searchAll(state, query);
  const hasResults =
    results.items.length + results.projects.length + results.suppliers.length + results.requests.length > 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (path: string) => {
    setOpen(false);
    setQuery("");
    navigate(path);
  };

  return (
    <div className="gsearch" ref={wrapRef}>
      <span className="gsearch__icon">
        <Icon name="search" />
      </span>
      <input
        ref={inputRef}
        className="gsearch__input"
        placeholder="Search items, projects, suppliers…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && query.trim()) {
            if (results.items[0]) go(`/inventory?item=${results.items[0].id}`);
            else if (results.projects[0]) go(`/projects/${results.projects[0].id}`);
            else go(`/inventory?q=${encodeURIComponent(query)}`);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        aria-label="Search inventory, projects and suppliers"
      />
      <span className="gsearch__kbd">
        <kbd>⌘</kbd>
        <kbd>K</kbd>
      </span>

      {open && query.trim() ? (
        <div className="search-pop" role="dialog" aria-label="Search results">
          {!hasResults ? (
            <div style={{ padding: "26px 16px", textAlign: "center" }}>
              <p style={{ fontSize: 12, fontWeight: 500 }}>No matches for “{query}”</p>
              <p style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
                Try an item ID, project code or supplier name.
              </p>
            </div>
          ) : null}

          {results.items.length > 0 ? (
            <div className="search-pop__group">
              <div className="search-pop__label">Inventory</div>
              {results.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="search-pop__item"
                  onClick={() => go(`/inventory?item=${item.id}`)}
                >
                  <ItemThumb category={categoryById(state, item.categoryId)} size="sm" />
                  <span className="search-pop__main">
                    <span className="search-pop__title">{item.name}</span>
                    <span className="search-pop__sub">
                      {item.id} · {item.qty} {item.unit} on hand
                    </span>
                  </span>
                  <Icon name="arrow-up-right" size={13} />
                </button>
              ))}
            </div>
          ) : null}

          {results.projects.length > 0 ? (
            <div className="search-pop__group">
              <div className="search-pop__label">Projects</div>
              {results.projects.map((p) => (
                <button key={p.id} type="button" className="search-pop__item" onClick={() => go(`/projects/${p.id}`)}>
                  <span className="thumb thumb--sm" style={{ background: "var(--olive-soft)", color: "var(--olive)" }}>
                    <Icon name="layers" />
                  </span>
                  <span className="search-pop__main">
                    <span className="search-pop__title">{p.name}</span>
                    <span className="search-pop__sub">
                      {p.id} · {p.supervisor}
                    </span>
                  </span>
                  <Icon name="arrow-up-right" size={13} />
                </button>
              ))}
            </div>
          ) : null}

          {results.suppliers.length > 0 || results.requests.length > 0 ? (
            <div className="search-pop__group">
              <div className="search-pop__label">More</div>
              {results.suppliers.map((s) => (
                <button key={s.id} type="button" className="search-pop__item" onClick={() => go("/suppliers")}>
                  <span className="thumb thumb--sm" style={{ background: "var(--surface-2)", color: "var(--muted)" }}>
                    <Icon name="truck" />
                  </span>
                  <span className="search-pop__main">
                    <span className="search-pop__title">{s.name}</span>
                    <span className="search-pop__sub">Supplier · {s.city}</span>
                  </span>
                </button>
              ))}
              {results.requests.map((r) => (
                <button key={r.id} type="button" className="search-pop__item" onClick={() => go("/requests/history")}>
                  <span className="thumb thumb--sm" style={{ background: "var(--surface-2)", color: "var(--muted)" }}>
                    <Icon name="inbox" />
                  </span>
                  <span className="search-pop__main">
                    <span className="search-pop__title">{r.id}</span>
                    <span className="search-pop__sub">
                      {r.requestedBy} · {r.status}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ) : null}

          <div className="search-pop__foot">
            <span>↵ open first result</span>
            <span>esc to close</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Notifications                                                       */
/* ------------------------------------------------------------------ */

function Notifications() {
  const { state } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useOutsideClose(open, () => setOpen(false));
  const { pending, low, endingSoon } = alerts(state);
  const count = pending.length + Math.min(low.length, 3);

  return (
    <div className="popover-wrap" ref={ref}>
      <button
        type="button"
        className="topbar__icon"
        aria-label={`Notifications${count ? `, ${count} unread` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="bell" />
        {count > 0 ? <span className="topbar__dot" /> : null}
      </button>

      {open ? (
        <div className="notif-pop" role="dialog" aria-label="Notifications">
          <div className="notif-pop__head">
            <strong>Notifications</strong>
            <span className="badge badge--outline">{count} new</span>
          </div>
          <div className="notif-pop__body">
            {pending.length === 0 && low.length === 0 && endingSoon.length === 0 ? (
              <p style={{ padding: "22px 12px", fontSize: 11.5, color: "var(--muted)", textAlign: "center" }}>
                You are all caught up.
              </p>
            ) : null}
            {pending.slice(0, 3).map((r) => (
              <Link key={r.id} to="/requests/pending" className="list-row" onClick={() => setOpen(false)}>
                <span className="timeline__marker">
                  <Icon name="inbox" />
                </span>
                <span className="list-row__main">
                  <span className="list-row__title">{r.id} awaiting review</span>
                  <span className="list-row__sub">
                    {r.requestedBy} · {r.lines.length} line items
                  </span>
                </span>
                <span className="badge badge--amber">Pending</span>
              </Link>
            ))}
            {low.slice(0, 3).map((i) => (
              <Link key={i.id} to="/inventory/stock-levels" className="list-row" onClick={() => setOpen(false)}>
                <span className="timeline__marker">
                  <Icon name="alert-triangle" />
                </span>
                <span className="list-row__main">
                  <span className="list-row__title">{i.name}</span>
                  <span className="list-row__sub">
                    {i.qty} {i.unit} left · threshold {i.minQty}
                  </span>
                </span>
                <span className={`badge badge--${i.qty === 0 ? "red" : "amber"}`}>
                  {i.qty === 0 ? "Out" : "Low"}
                </span>
              </Link>
            ))}
            {endingSoon.slice(0, 2).map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="list-row" onClick={() => setOpen(false)}>
                <span className="timeline__marker">
                  <Icon name="flag" />
                </span>
                <span className="list-row__main">
                  <span className="list-row__title">{p.name}</span>
                  <span className="list-row__sub">Ends soon · {new Date(p.endDate).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</span>
                </span>
              </Link>
            ))}
          </div>
          <div className="notif-pop__foot">
            <Link to="/requests/pending" className="card__link" onClick={() => setOpen(false)}>
              Review pending requests <Icon name="arrow-right" />
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Role switcher                                                       */
/* ------------------------------------------------------------------ */

function RoleMenu() {
  const { role, setRole } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useOutsideClose(open, () => setOpen(false));

  return (
    <div className="popover-wrap rolemenu" ref={ref}>
      <button
        type="button"
        className="btn btn--secondary btn--sm"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{ height: 32, gap: 6 }}
        title="Switch role to preview access levels"
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: role === "admin" ? "var(--olive)" : role === "supervisor" ? "var(--blue)" : "var(--amber)",
          }}
        />
        {ROLE_LABELS[role]}
        <Icon name="chevron-down" size={12} />
      </button>
      {open ? (
        <div className="menu" role="menu" style={{ minWidth: 240 }}>
          <div className="menu__label">Preview as</div>
          {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
            <button
              key={r}
              type="button"
              role="menuitemradio"
              aria-checked={role === r}
              className="menu__item"
              onClick={() => {
                setRole(r);
                setOpen(false);
              }}
            >
              <Avatar name={ROLE_ACTORS[r].name} />
              <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.35 }}>
                <span style={{ fontWeight: 500 }}>{ROLE_LABELS[r]}</span>
                <span style={{ fontSize: 9.5, color: "var(--muted)" }}>{ROLE_ACTORS[r].name}</span>
              </span>
              {role === r ? <Icon name="check" style={{ marginLeft: "auto", color: "var(--ink)" }} /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Top bar                                                             */
/* ------------------------------------------------------------------ */

const CRUMB_LABELS: Record<string, string> = {
  inventory: "Inventory",
  projects: "Projects",
  transactions: "Transactions",
  requests: "Requests",
  suppliers: "Suppliers",
  reports: "Reports",
  settings: "Settings",
  categories: "Categories",
  "stock-levels": "Stock levels",
  in: "Stock in",
  out: "Stock out",
  returns: "Returns",
  history: "History",
  pending: "Pending",
  approved: "Approved",
};

function Breadcrumb() {
  const { state } = useApp();
  const location = useLocation();
  const parts = location.pathname.split("/").filter(Boolean);

  if (parts.length === 0) {
    return (
      <div className="topbar__crumb">
        <Icon name="grid" />
        <b>Overview</b>
      </div>
    );
  }

  const projectId = parts[0] === "projects" && parts[1] && parts[1] !== "inventory" ? parts[1] : null;
  const project = projectId ? state.projects.find((p) => p.id === projectId) : null;
  const labels = parts
    .filter((p) => !p.startsWith("PBL-"))
    .map((p) => CRUMB_LABELS[p] ?? p);

  return (
    <div className="topbar__crumb">
      <Icon name="grid" />
      <span>Inventra</span>
      {labels.map((label, i) => (
        <span key={`${label}-${i}`} style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <Icon name="chevron-right" />
          {i === labels.length - 1 ? <b>{project?.name ?? label}</b> : <span>{label}</span>}
        </span>
      ))}
    </div>
  );
}

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { state, role, actorName, setRole } = useApp();
  const [scrolled, setScrolled] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const userRef = useOutsideClose(userOpen, () => setUserOpen(false));
  const navigate = useNavigate();
  const { pending } = alerts(state);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="topbar" data-scrolled={scrolled}>
      <div className="topbar__left">
        <button type="button" className="topbar__icon topbar__menu-btn" onClick={onMenu} aria-label="Open navigation">
          <Icon name="menu" />
        </button>
        <Breadcrumb />
      </div>

      <GlobalSearch />

      <div className="topbar__right">
        <RoleMenu />
        <Notifications />
        <Link to="/settings" className="topbar__icon" aria-label="Help and settings">
          <Icon name="help" />
        </Link>
        <div className="popover-wrap" ref={userRef}>
          <button
            type="button"
            onClick={() => setUserOpen((v) => !v)}
            aria-label="Account menu"
            aria-expanded={userOpen}
            style={{ display: "inline-flex", borderRadius: "50%" }}
          >
            <Avatar name={actorName} />
          </button>
          {userOpen ? (
            <div className="menu" role="menu" style={{ minWidth: 218 }}>
              <div className="menu__meta">
                <strong>{actorName}</strong>
                <span>{ROLE_ACTORS[role].email}</span>
              </div>
              <div className="menu__sep" />
              <div className="menu__label menu__roles-label">Preview as</div>
              {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  role="menuitemradio"
                  aria-checked={role === r}
                  className="menu__item menu__role"
                  onClick={() => {
                    setRole(r);
                    setUserOpen(false);
                  }}
                >
                  <Icon name="user" /> {ROLE_LABELS[r]}
                  {role === r ? <Icon name="check" style={{ marginLeft: "auto" }} /> : null}
                </button>
              ))}
              <div className="menu__sep menu__roles-sep" />
              <button
                type="button"
                className="menu__item"
                onClick={() => {
                  setUserOpen(false);
                  navigate("/settings");
                }}
              >
                <Icon name="settings" /> Account settings
              </button>
              <button
                type="button"
                className="menu__item"
                onClick={() => {
                  setUserOpen(false);
                  navigate("/requests/pending");
                }}
              >
                <Icon name="inbox" /> Review requests
                {pending.length > 0 ? <span className="badge badge--amber" style={{ marginLeft: "auto" }}>{pending.length}</span> : null}
              </button>
              <div className="menu__sep" />
              <button
                type="button"
                className="menu__item"
                onClick={() => {
                  setUserOpen(false);
                  navigate("/settings?tab=data");
                }}
              >
                <Icon name="database" /> Data &amp; storage
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */

export function ScrollToTop() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [location.pathname]);
  return null;
}

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Inventra`;
  }, [title]);
}
