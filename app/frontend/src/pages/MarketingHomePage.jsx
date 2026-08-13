import { Link } from "react-router-dom";
import { Phone, MapPin, Shield } from "lucide-react";
import TalkBoxLogo from "../components/marketing/TalkBoxLogo.jsx";
import { Button } from "../components/ui/Button.jsx";
import kioskPhoto from "../assets/kiosk-photo.png";

export default function MarketingHomePage() {
  return (
    <div className="marketing-home">
      <section className="marketing-hero relative isolate overflow-hidden">
        <div className="marketing-hero-backdrop" aria-hidden />
        <div className="relative mx-auto grid min-h-[calc(100dvh-4rem)] max-w-6xl items-center gap-8 px-5 py-14 sm:px-8 md:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)] md:gap-10 md:py-20">
          <div className="relative z-10">
            <p className="marketing-rise marketing-rise-1 font-marketing text-sm font-semibold uppercase tracking-[0.2em] text-white/80">
              Community infrastructure
            </p>
            <h1 className="marketing-rise marketing-rise-2 mt-4">
              <TalkBoxLogo className="talkbox-logo--hero" />
            </h1>
            <p className="marketing-rise marketing-rise-3 mt-6 max-w-xl text-lg leading-relaxed text-white/90 sm:text-xl">
              A payphone for the 21st century — a public kiosk that connects people
              without phones to 211 and local help, with one big button.
            </p>
            <div className="marketing-rise marketing-rise-4 mt-10 flex flex-wrap gap-3">
              <Button asChild size="lg" variant="secondary" className="min-w-[9.5rem] shadow-sm">
                <Link to="/demo">Try the demo</Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="min-w-[9.5rem] border-primary-foreground/40 bg-transparent text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground"
              >
                <Link to="/donate">Donate</Link>
              </Button>
            </div>
          </div>
          <figure className="marketing-kiosk-photo marketing-rise marketing-rise-3">
            <img
              src={kioskPhoto}
              alt="Talk Box community assistance kiosk"
              className="marketing-kiosk-photo__image"
            />
          </figure>
        </div>
      </section>

      <section className="border-t border-border bg-background py-16 sm:py-20">
        <div className="mx-auto max-w-5xl px-5 sm:px-8">
          <h2 className="font-marketing text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            How it works
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            No account. No app. Walk up, say what you need — or press a number —
            and Talk Box routes you to a real person or service that can help.
          </p>

          <ul className="mt-12 grid gap-10 sm:grid-cols-3">
            <li className="marketing-step">
              <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <MapPin className="h-5 w-5" aria-hidden />
              </div>
              <h3 className="mt-4 font-marketing text-lg font-semibold text-foreground">
                Walk up
              </h3>
              <p className="mt-2 text-base leading-relaxed text-muted-foreground">
                Placed where people already are — shelters, hubs, and public
                spaces. Hardware keys, big text, calm voice prompts.
              </p>
            </li>
            <li className="marketing-step">
              <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Phone className="h-5 w-5" aria-hidden />
              </div>
              <h3 className="mt-4 font-marketing text-lg font-semibold text-foreground">
                Call for help
              </h3>
              <p className="mt-2 text-base leading-relaxed text-muted-foreground">
                Reach 211 and allowlisted local agencies for shelter, food,
                medical care, and mental health — straight from the kiosk.
              </p>
            </li>
            <li className="marketing-step">
              <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Shield className="h-5 w-5" aria-hidden />
              </div>
              <h3 className="mt-4 font-marketing text-lg font-semibold text-foreground">
                Built for dignity
              </h3>
              <p className="mt-2 text-base leading-relaxed text-muted-foreground">
                No phone required. Calls only go to approved contacts. Designed
                for crisis use, not forms and logins.
              </p>
            </li>
          </ul>

          <div className="mt-14 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link to="/demo">Explore the product</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/donate">Support the work</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
