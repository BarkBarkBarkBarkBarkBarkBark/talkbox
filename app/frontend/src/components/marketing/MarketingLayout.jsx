import { NavLink, Outlet } from "react-router-dom";
import { isLocalHost } from "../../lib/isLocalHost.js";
import { cn } from "../../lib/utils.js";

const navLinkClass = ({ isActive }) =>
  cn(
    "text-sm font-semibold tracking-wide transition-colors duration-200",
    isActive ? "text-primary" : "text-foreground/70 hover:text-foreground",
  );

/** Shell for public marketing pages. Accepts `children` or a nested `<Outlet />`. */
export default function MarketingLayout({ children }) {
  // On appliance/dev hosts `/` is the kiosk; marketing live-preview uses `/site`.
  const aboutTo = isLocalHost() ? "/site" : "/";

  return (
    <div className="marketing-shell flex min-h-full flex-col">
      <header className="marketing-header sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-5 sm:px-8">
          <NavLink to={aboutTo} className="group flex items-baseline gap-2 no-underline">
            <span className="font-marketing text-xl font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
              Talk Box
            </span>
          </NavLink>
          <nav className="flex items-center gap-5 sm:gap-8" aria-label="Marketing">
            <NavLink to={aboutTo} end className={navLinkClass}>
              About
            </NavLink>
            <NavLink to="/demo" className={navLinkClass}>
              Demo
            </NavLink>
            <NavLink to="/donate" className={navLinkClass}>
              Donate
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children ?? <Outlet />}</main>

      <footer className="border-t border-border/80 py-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-5 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>
            <span className="font-semibold text-foreground">Talk Box</span>
            {" — "}a payphone for the 21st century.
          </p>
          <p>Walk up. Press Call. Get connected.</p>
        </div>
      </footer>
    </div>
  );
}
