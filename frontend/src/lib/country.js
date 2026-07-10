/**
 * Country-aware formatting helpers.
 * The user's country is stored on the auth `user` object as `user.country` ("IN" | "AE").
 * When no user (or no country), defaults to India.
 */

export const COUNTRIES = {
  IN: {
    code: "IN",
    name: "India",
    flag: "🇮🇳",
    currency: "INR",
    symbol: "₹",
    locale: "en-IN",
    dial: "+91",
    dateOrder: "DD-MM-YYYY",
    complianceCategories: [
      "permit", "license", "insurance", "registration", "safety",
      "tender", "labour", "gst", "municipal", "environment",
    ],
    rateTypes: ["daily", "weekly", "monthly", "contract", "sqft", "task", "milestone", "piece"],
    officeLabel: "Office address (India)",
    phoneHint: "+91 98xxxxxxxx",
  },
  AE: {
    code: "AE",
    name: "United Arab Emirates",
    flag: "🇦🇪",
    currency: "AED",
    symbol: "AED",
    locale: "en-AE",
    dial: "+971",
    dateOrder: "DD-MM-YYYY",
    complianceCategories: [
      "trade_license", "labour_card", "emirates_id", "visa",
      "wps", "civil_defense", "municipality_noc", "tasheel",
      "insurance", "safety", "environment", "tender",
    ],
    rateTypes: ["hourly", "daily", "weekly", "monthly", "contract", "sqm", "task", "milestone", "piece"],
    officeLabel: "Office address (Emirates)",
    phoneHint: "+971 5x xxx xxxx",
  },
};

export const getCountry = (user) => COUNTRIES[user?.country] || COUNTRIES.IN;

/** Format an amount using the user's country. */
export function formatMoney(amount, user, options = {}) {
  const c = getCountry(user);
  const n = Number(amount) || 0;
  const { compact = false, decimals = 0 } = options;
  if (compact && Math.abs(n) >= 100000) {
    if (c.code === "IN") {
      // Indian numeric grouping
      if (Math.abs(n) >= 10000000) return `${c.symbol}${(n / 10000000).toFixed(1)}Cr`;
      return `${c.symbol}${(n / 100000).toFixed(1)}L`;
    }
    if (Math.abs(n) >= 1000000) return `${c.symbol} ${(n / 1000000).toFixed(1)}M`;
    return `${c.symbol} ${(n / 1000).toFixed(0)}k`;
  }
  const formatted = n.toLocaleString(c.locale, { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
  return c.code === "IN" ? `${c.symbol}${formatted}` : `${c.symbol} ${formatted}`;
}

/** For date-only strings ("YYYY-MM-DD" or ISO). */
export function formatDate(iso, user) {
  if (!iso) return "";
  const c = getCountry(user);
  try {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString(c.locale, { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}
