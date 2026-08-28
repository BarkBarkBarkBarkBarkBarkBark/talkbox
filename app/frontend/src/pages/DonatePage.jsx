import { useEffect } from "react";
import { ExternalLink, Heart } from "lucide-react";
import { DONATE_LINK_PROPS, DONATE_URL } from "../lib/donate.js";
import { Button } from "../components/ui/Button.jsx";

export default function DonatePage() {
  useEffect(() => {
    window.location.replace(DONATE_URL);
  }, []);

  return (
    <div className="mx-auto max-w-xl px-5 py-16 sm:px-8 sm:py-20">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Heart className="h-6 w-6" aria-hidden />
      </div>
      <h1 className="mt-6 font-marketing text-4xl font-bold tracking-tight text-foreground">
        Continue to GoFundMe
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
        Talk Box fundraising is on GoFundMe. If you are not redirected, use
        the button below.
      </p>
      <Button asChild size="lg" className="mt-8 gap-2">
        <a {...DONATE_LINK_PROPS}>
          Donate on GoFundMe
          <ExternalLink className="h-4 w-4" aria-hidden />
        </a>
      </Button>
    </div>
  );
}
