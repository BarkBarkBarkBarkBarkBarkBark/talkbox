export const GOFUNDME_URL =
  "https://www.gofundme.com/f/help-someone-without-a-phone-find-their-way-into-shelter";

function isBlockedDonateUrl(url) {
  return /square\.site|squareup\.com/i.test(url);
}

/** Public fundraiser. Square checkout URLs are ignored if an env override still has one. */
export const DONATE_URL = (() => {
  const raw = String(import.meta.env.VITE_DONATE_URL || "").trim();
  if (!raw || isBlockedDonateUrl(raw)) return GOFUNDME_URL;
  return raw;
})();

export const DONATE_LINK_PROPS = {
  href: DONATE_URL,
  target: "_blank",
  rel: "noopener noreferrer",
};
