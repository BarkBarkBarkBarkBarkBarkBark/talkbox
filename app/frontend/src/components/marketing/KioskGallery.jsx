import { DONATE_LINK_PROPS } from "../../lib/donate.js";
import { Button } from "../ui/Button.jsx";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "../ui/Card.jsx";
import kioskPhoto from "../../assets/kiosk-photo.png";
import talkbox2 from "../../assets/talkbox-2.png";

function LiveCard() {
  return (
    <Card className="kiosk-gallery-card overflow-hidden">
      <figure className="kiosk-gallery-card__figure kiosk-gallery-card__figure--live">
        <img
          src={kioskPhoto}
          alt="Talk Box kiosk currently in service"
          className="kiosk-gallery-card__image"
        />
      </figure>
      <CardHeader>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          In service
        </p>
        <CardTitle className="font-marketing">TalkBox</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-base leading-relaxed text-muted-foreground">
          The unit in the field today — a walk-up path to 211 and local help,
          with one big button.
        </p>
      </CardContent>
      <CardFooter>
        <p className="text-sm font-semibold text-foreground">Now in the field</p>
      </CardFooter>
    </Card>
  );
}

function AdoptCard({ showCta = true }) {
  return (
    <Card className="kiosk-gallery-card overflow-hidden">
      <figure className="kiosk-gallery-card__figure kiosk-gallery-card__figure--v2">
        <img
          src={talkbox2}
          alt="TalkBox 2.0 concept render — the next kiosk to be built and placed"
          className="kiosk-gallery-card__image"
        />
        <span className="kiosk-gallery-badge">Adopt Me</span>
      </figure>
      <CardHeader>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-warning">
          Next unit
        </p>
        <CardTitle className="font-marketing">TalkBox 2.0</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-base leading-relaxed text-muted-foreground">
          Sponsor the next kiosk. It gets built and placed at a location you
          choose — a shelter, hub, or public space. We will reach out about
          the site after you give.
        </p>
      </CardContent>
      {showCta ? (
        <CardFooter>
          <Button asChild size="lg">
            <a {...DONATE_LINK_PROPS}>Adopt this kiosk</a>
          </Button>
        </CardFooter>
      ) : null}
    </Card>
  );
}

/** Two-up kiosk lineup, or the 2.0 adopt card alone on Donate. */
export default function KioskGallery({ variant = "full", showAdoptCta = true }) {
  if (variant === "adopt") {
    return <AdoptCard showCta={showAdoptCta} />;
  }

  return (
    <div className="kiosk-gallery">
      <LiveCard />
      <AdoptCard showCta={showAdoptCta} />
    </div>
  );
}
