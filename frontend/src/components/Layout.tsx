import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { API_URL } from "../config";
import { useTestClock } from "../testClock";
import { Icon, type IconName } from "./Icon";
import { TestClockBanner, TestClockPanel } from "./TestClock";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/items", label: "Items", icon: "box" },
  { to: "/members", label: "Members", icon: "users" },
  { to: "/overdue", label: "Overdue", icon: "clock" },
  { to: "/dashboard", label: "Dashboard", icon: "chart" },
];

function Brand() {
  return (
    <Link to="/items" className="brand">
      <span className="brand-mark">
        <Icon name="box" size={20} />
      </span>
      <span>Equipment Rental Desk</span>
    </Link>
  );
}

/**
 * The application frame: a fixed navigation sidebar on large screens, and on small ones a top bar
 * whose menu button opens the same navigation as a drawer (closed again by Escape, the backdrop,
 * the close button or choosing a page).
 */
export function Layout({ children }: { children: ReactNode }) {
  const testClock = useTestClock();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const firstLink = useRef<HTMLAnchorElement>(null);

  // Following a link closes the drawer; render-time adjustment keeps it from flashing open.
  const [seenPath, setSeenPath] = useState(location.pathname);
  if (seenPath !== location.pathname) {
    setSeenPath(location.pathname);
    setMenuOpen(false);
  }

  useEffect(() => {
    if (!menuOpen) return;
    firstLink.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <aside id="sidebar" className={menuOpen ? "sidebar sidebar--open" : "sidebar"}>
          <div className="sidebar__head">
            <Brand />
            <button
              type="button"
              className="icon-button sidebar__close"
              aria-label="Close menu"
              onClick={() => {
                setMenuOpen(false);
                menuButton.current?.focus();
              }}
            >
              <Icon name="close" />
            </button>
          </div>
          <nav aria-label="Main" className="nav">
            <p className="nav__label" aria-hidden="true">
              Operations
            </p>
            {NAV.map((entry, index) => (
              <NavLink
                key={entry.to}
                to={entry.to}
                className="nav__link"
                ref={index === 0 ? firstLink : undefined}
              >
                <Icon name={entry.icon} />
                {entry.label}
              </NavLink>
            ))}
          </nav>
          <p className="sidebar__foot">All times are shown in IST. Amounts are in rupees.</p>
        </aside>
        {menuOpen && (
          <div className="scrim" aria-hidden="true" onClick={() => setMenuOpen(false)} />
        )}
        <div className="shell__main">
          <TestClockBanner />
          <div className="topbar">
            <button
              ref={menuButton}
              type="button"
              className="icon-button"
              aria-label="Menu"
              aria-expanded={menuOpen}
              aria-controls="sidebar"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <Icon name="menu" />
            </button>
            <Brand />
          </div>
          {/* While the drawer is open the page behind it cannot be reached with Tab or a screen reader. */}
          {/* Changing the test clock remounts the page so everything is fetched again at the new time. */}
          <main
            id="main"
            tabIndex={-1}
            className="page"
            key={testClock ?? "real-time"}
            inert={menuOpen}
          >
            {children}
          </main>
          <footer className="page-footer" inert={menuOpen}>
            <p className="muted">API: {API_URL ?? "not configured"}. Times are shown in IST.</p>
            <TestClockPanel />
          </footer>
        </div>
      </div>
    </>
  );
}
