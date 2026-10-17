import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { API_URL } from "../config";
import { useTestClock } from "../testClock";
import { TestClockBanner, TestClockPanel } from "./TestClock";

export function Layout({ children }: { children: ReactNode }) {
  const testClock = useTestClock();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <TestClockBanner />
      <header className="site-header">
        <div className="container site-header__inner">
          <Link to="/items" className="brand">
            Equipment Rental Desk
          </Link>
          <nav aria-label="Main">
            <NavLink to="/items">Items</NavLink>
            <NavLink to="/members">Members</NavLink>
            <NavLink to="/overdue">Overdue</NavLink>
          </nav>
        </div>
      </header>
      {/* Changing the test clock remounts the page so everything is fetched again at the new time. */}
      <main id="main" tabIndex={-1} className="container" key={testClock ?? "real-time"}>
        {children}
      </main>
      <footer className="container site-footer">
        <p className="muted">API: {API_URL ?? "not configured"}. Times are shown in IST.</p>
        <TestClockPanel />
      </footer>
    </>
  );
}
