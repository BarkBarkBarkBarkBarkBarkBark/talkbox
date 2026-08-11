import { ExternalLink, Heart } from "lucide-react";
import { Button } from "../components/ui/Button.jsx";

const DONATE_URL = (import.meta.env.VITE_DONATE_URL || "").trim();
const DONATE_LABEL = (import.meta.env.VITE_DONATE_LABEL || "Donate now").trim();

export default function DonatePage() {
  const hasLink = Boolean(DONATE_URL);

  return (
    <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-20">
      <div className="marketing-rise marketing-rise-1 max-w-2xl">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Heart className="h-6 w-6" aria-hidden />
        </div>
        <h1 className="mt-6 font-marketing text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Support Talk Box
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          Talk Box puts a free, walk-up path to 211 and local services in
          public space. Donations help build and maintain kiosks so people
          without phones can still get connected.
        </p>
      </div>

      <div className="marketing-rise marketing-rise-2 mt-12 max-w-xl rounded-md border border-border bg-secondary/40 p-6 sm:p-8">
        {hasLink ? (
          <>
            <p className="text-base leading-relaxed text-foreground">
              Every contribution helps place and operate hardware where it is
              needed most.
            </p>
            <Button asChild size="lg" className="mt-6 gap-2">
              <a href={DONATE_URL} target="_blank" rel="noopener noreferrer">
                {DONATE_LABEL}
                <ExternalLink className="h-4 w-4" aria-hidden />
              </a>
            </Button>
          </>
        ) : (
          <>
            <p className="text-base font-semibold text-foreground">
              Donation link coming soon
            </p>
            <p className="mt-2 text-base leading-relaxed text-muted-foreground">
              Set <code className="rounded bg-muted px-1.5 py-0.5 text-sm">VITE_DONATE_URL</code>{" "}
              on the Vercel project (or your build env) to enable the public
              give button. Until then, this page is ready for partners and
              visitors.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
