import KioskGallery from "../components/marketing/KioskGallery.jsx";

export default function GalleryPage() {
  return (
    <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-20">
      <div className="marketing-rise marketing-rise-1 max-w-2xl">
        <p className="font-marketing text-sm font-semibold uppercase tracking-[0.2em] text-primary">
          Hardware
        </p>
        <h1 className="mt-3 font-marketing text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Get a Talk Box
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          The TalkBox in service today, and the next unit waiting for a home.
          Adopt TalkBox 2.0 to fund a kiosk placed where you choose.
        </p>
      </div>

      <div className="marketing-rise marketing-rise-2 mt-12">
        <KioskGallery />
      </div>
    </div>
  );
}
