import { Compass, Moon, Sun } from "lucide-react";
import { useTheme } from "../lib/theme.jsx";
import { Button } from "./ui/Button.jsx";

export function AppHeader() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Compass className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-foreground">Talk Box</p>
            <p className="text-[11px] text-muted-foreground">Shelter routing assistant</p>
          </div>
        </div>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
