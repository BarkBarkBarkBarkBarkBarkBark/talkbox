import { Link } from "react-router-dom";
import { ArrowLeft, Heart } from "lucide-react";
import { DONATE_LINK_PROPS } from "../../lib/donate.js";
import { isLocalHost } from "../../lib/isLocalHost.js";
import { Button } from "../ui/Button.jsx";

/**
 * Thin marketing strip above the simulated kiosk. Does not alter KioskShell.
 */
export default function DemoChrome({ children }) {
  const aboutTo = isLocalHost() ? "/site" : "/";

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="marketing-demo-chrome z-50 flex shrink-0 items-center justify-between gap-3 border-b border-border bg-background px-3 py-2 sm:px-5">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <Button asChild variant="ghost" size="sm" className="shrink-0 gap-1.5 px-2">
            <Link to={aboutTo} aria-label="Back to About">
              <ArrowLeft className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">About</span>
            </Link>
          </Button>
          <p className="truncate text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">Live demo</span>
            <span className="hidden sm:inline">
              {" "}
              — simulated kiosk; no real calls.
            </span>
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="shrink-0 gap-1.5">
          <a {...DONATE_LINK_PROPS}>
            <Heart className="h-4 w-4" aria-hidden />
            Donate
          </a>
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
