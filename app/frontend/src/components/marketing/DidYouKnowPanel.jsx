import { useState } from "react";
import { X } from "lucide-react";

const SESSION_KEY = "tb_dyk_dismissed";

export default function DidYouKnowPanel() {
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(SESSION_KEY) === "1",
  );

  if (dismissed) return null;

  function dismiss() {
    sessionStorage.setItem(SESSION_KEY, "1");
    setDismissed(true);
  }

  return (
    <aside
      className="dyk-panel"
      role="note"
      aria-label="Did You Know? — Why TalkBox exists"
    >
      <div className="dyk-panel__inner">
        <header className="dyk-panel__header">
          <span className="dyk-panel__eyebrow" aria-hidden>
            Did you know?
          </span>
          <button
            type="button"
            className="dyk-panel__close"
            aria-label="Dismiss this panel"
            onClick={dismiss}
            onKeyDown={(e) => e.key === "Escape" && dismiss()}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </header>

        <div className="dyk-panel__body">
          <p>
            For many people experiencing homelessness in Sacramento, getting
            connected to shelter starts with calling 211, completing a crisis
            assessment, and waiting for an available placement.
          </p>
          <p>
            That process can take days—and staying reachable can be difficult
            when you don't have a working phone.
          </p>
          <p className="dyk-panel__callout">TalkBox is designed to close that gap.</p>
          <p>It gives anyone free access to a phone to:</p>
          <ul>
            <li>Call 211 and connect with shelter services</li>
            <li>Call a doctor, family member, case manager, or support network</li>
            <li>
              Search for local services by voice using a database of community
              providers
            </li>
          </ul>
          <p className="dyk-panel__coda">
            Getting help shouldn't depend on having a phone.
          </p>
        </div>
      </div>
    </aside>
  );
}
