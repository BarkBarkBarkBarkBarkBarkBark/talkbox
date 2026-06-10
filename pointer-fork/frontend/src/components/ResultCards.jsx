import { MapPin, Phone, ShieldCheck, Stethoscope, Tag, Truck } from "lucide-react";
import { cn } from "../lib/utils.js";

function formatPhone(raw) {
  if (!raw) return null;
  const digits = String(raw).replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) {
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return raw;
}

function phoneHref(raw) {
  const digits = String(raw ?? "").replace(/\D/g, "");
  return digits ? `tel:${digits}` : undefined;
}

function MetaRow({ icon: Icon, children, href }) {
  const content = (
    <>
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="text-xs leading-snug">{children}</span>
    </>
  );
  return href ? (
    <a
      href={href}
      className="flex items-start gap-1.5 text-foreground/80 transition-colors hover:text-primary"
    >
      {content}
    </a>
  ) : (
    <div className="flex items-start gap-1.5 text-foreground/80">{content}</div>
  );
}

function Tags({ raw }) {
  if (!raw) return null;
  const chips = String(raw)
    .split(/[,;/]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 6);
  if (!chips.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {chips.map((t) => (
        <span
          key={t}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary/70 px-2 py-0.5 text-[10.5px] font-medium text-foreground/80"
        >
          <Tag className="h-2.5 w-2.5" />
          {t}
        </span>
      ))}
    </div>
  );
}

function AgencyCard({ item }) {
  return (
    <article className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/50">
      <header className="space-y-1">
        <h3 className="text-sm font-semibold leading-snug text-foreground">{item.name}</h3>
        {item.description ? (
          <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
            {item.description}
          </p>
        ) : null}
      </header>

      <div className="mt-auto space-y-1">
        {item.phone ? (
          <MetaRow icon={Phone} href={phoneHref(item.phone)}>
            {formatPhone(item.phone)}
          </MetaRow>
        ) : null}
        {item.address ? <MetaRow icon={MapPin}>{item.address}</MetaRow> : null}
        {item.insurance ? <MetaRow icon={ShieldCheck}>{item.insurance}</MetaRow> : null}
        <Tags raw={item.tags} />
      </div>
    </article>
  );
}

function DoctorCard({ item }) {
  const full = [item.first_name, item.last_name].filter(Boolean).join(" ").trim() || "Provider";
  return (
    <article className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/50">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Stethoscope className="h-3.5 w-3.5" />
          </span>
          <h3 className="text-sm font-semibold leading-snug text-foreground">Dr. {full}</h3>
        </div>
        {item.specialty ? (
          <p className="text-xs font-medium text-primary/90">{item.specialty}</p>
        ) : null}
      </header>

      <div className="mt-auto space-y-1">
        {item.phone ? (
          <MetaRow icon={Phone} href={phoneHref(item.phone)}>
            {formatPhone(item.phone)}
          </MetaRow>
        ) : null}
        {item.address ? <MetaRow icon={MapPin}>{item.address}</MetaRow> : null}
        {item.insurance ? <MetaRow icon={ShieldCheck}>{item.insurance}</MetaRow> : null}
        {item.transportation_provider || item.transportation_phone ? (
          <MetaRow
            icon={Truck}
            href={item.transportation_phone ? phoneHref(item.transportation_phone) : undefined}
          >
            {[item.transportation_provider, item.transportation_phone ? formatPhone(item.transportation_phone) : null]
              .filter(Boolean)
              .join(" · ")}
          </MetaRow>
        ) : null}
      </div>
    </article>
  );
}

export default function ResultCards({ results, className }) {
  if (!results) return null;

  const isAgencies = results.type === "agencies";
  const items = isAgencies ? results.items_agencies : results.items_doctors;

  if (!items?.length) return null;

  return (
    <div className={cn("space-y-3", className)}>
      {results.category ? (
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          {results.category}
          <span className="ml-auto text-muted-foreground/70">
            {items.length} {isAgencies ? "agencies" : "providers"}
          </span>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item, idx) =>
          isAgencies ? (
            <AgencyCard key={`${item.name}-${idx}`} item={item} />
          ) : (
            <DoctorCard key={`${item.last_name ?? "doc"}-${idx}`} item={item} />
          ),
        )}
      </div>
    </div>
  );
}
