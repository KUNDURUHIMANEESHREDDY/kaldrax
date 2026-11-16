import { Link, useLocation } from "react-router-dom";
import { usePageTitle } from "../components/Layout";
import { Button } from "../components/ui";
import { Icon } from "../components/Icons";

export default function NotFound() {
  usePageTitle("Page not found");
  const location = useLocation();

  return (
    <div
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "58vh",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: 430 }}>
        <span
          style={{
            display: "inline-grid",
            placeItems: "center",
            width: 58,
            height: 58,
            borderRadius: 18,
            background: "var(--olive-soft)",
            color: "var(--olive)",
            marginBottom: 18,
          }}
        >
          <Icon name="alert-circle" />
        </span>
        <div
          className="mono"
          style={{ fontSize: 11, letterSpacing: "0.08em", color: "var(--faint)", textTransform: "uppercase" }}
        >
          404 · Not found
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.02em", margin: "8px 0 8px" }}>
          This shelf is empty
        </h1>
        <p style={{ fontSize: 12.5, color: "var(--muted)", lineHeight: 1.7, marginBottom: 18 }}>
          We couldn't find <span className="mono">{location.pathname}</span>. The page may have moved, or the link may be
          mistyped.
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
          <Link to="/" className="btn btn--primary btn--sm">
            <Icon name="grid" /> Back to overview
          </Link>
          <Link to="/inventory" className="btn btn--secondary btn--sm">
            <Icon name="package" /> Browse inventory
          </Link>
        </div>
        <p style={{ marginTop: 24 }}>
          <Button
            size="sm"
            variant="ghost"
            icon="arrow-left"
            onClick={() => {
              if (window.history.length > 1) window.history.back();
              else window.location.hash = "#/";
            }}
          >
            Go back
          </Button>
        </p>
      </div>
    </div>
  );
}
