import MarketingLayout from "../components/marketing/MarketingLayout.jsx";
import { isLocalHost } from "../lib/isLocalHost.js";
import KioskPage from "./KioskPage.jsx";
import MarketingHomePage from "./MarketingHomePage.jsx";

/**
 * Appliance (localhost) keeps the production kiosk on `/` — no marketing chrome.
 * Public hosts (e.g. Vercel) get the marketing site shell + home.
 */
export default function RootPage() {
  if (isLocalHost()) {
    return <KioskPage />;
  }
  return (
    <MarketingLayout>
      <MarketingHomePage />
    </MarketingLayout>
  );
}
