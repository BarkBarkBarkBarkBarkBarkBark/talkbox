import { useEffect, useRef } from "react";

// Numbered resource results / flat directory. Tap a row or press N (1–9) to
// open detail; use – / + to move and Enter to open. Ask-tab search still
// echoes the last question above the title.
export default function KioskResourceList({
  category,
  items,
  cursor = 0,
  lastQuery,
  directory = false,
  onSelectItem,
  onKey,
}) {
  const rowRefs = useRef([]);

  useEffect(() => {
    const el = rowRefs.current[cursor];
    if (el) {
      el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [cursor, items.length]);

  const longList = items.length > 9;
  const title = category || (directory ? "All services" : "Results");
  const subtitle =
    directory || longList ? (
      <>
        Use <strong>–</strong> / <strong>+</strong> to move and{" "}
        <strong>Enter</strong> to open
        {items.length > 9 ? "; numbers 1–9 open the first nine" : ""}.
      </>
    ) : (
      <>
        Press a number, or use <strong>–</strong> / <strong>+</strong> to move and{" "}
        <strong>Enter</strong> to open.
      </>
    );

  return (
    <div className="kiosk-content">
      {lastQuery && !directory ? (
        <p className="kiosk-asked">
          You asked: <em>“{lastQuery}”</em>
        </p>
      ) : null}
      <h1 className="kiosk-title">{title}</h1>
      <p className="kiosk-subtitle">{subtitle}</p>
      <div className="kiosk-list">
        {items.map((item, i) => (
          <button
            key={item.number ?? i}
            type="button"
            ref={(el) => {
              rowRefs.current[i] = el;
            }}
            className={`kiosk-row ${i === cursor ? "is-selected" : ""}`}
            aria-current={i === cursor}
            onClick={() => {
              if (onSelectItem) {
                onSelectItem(item);
              } else if (item.number >= 1 && item.number <= 9) {
                onKey?.(String(item.number));
              } else {
                onKey?.("#");
              }
            }}
          >
            {item.number >= 1 && item.number <= 9 ? (
              <span className="kiosk-key-badge">{item.number}</span>
            ) : (
              <span className="kiosk-key-badge kiosk-key-badge-muted" aria-hidden>
                {item.number}
              </span>
            )}
            <span className="kiosk-row-body">
              <span className="kiosk-row-title">{item.name}</span>
              {item.description ? (
                <span className="kiosk-row-meta">{item.description}</span>
              ) : null}
            </span>
            {item.phone_display ? (
              <span className="kiosk-row-phone">{item.phone_display}</span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
