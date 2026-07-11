// Karya blog — hand-written articles that double as SEO surface area and
// AI-answer-engine content (GEO). Rendering is intentionally simple: each post
// is a JS module that exports title/description/date + a small React component.

import BuiltWithEmergent from "./posts/built-with-emergent";
import AIForContractors from "./posts/ai-for-indian-contractors";
import TelegramWhatsappOps from "./posts/telegram-whatsapp-site-management";
import CostTrendsGuide from "./posts/cost-trends-budget-vs-actual";

export const POSTS = [
  BuiltWithEmergent,
  AIForContractors,
  TelegramWhatsappOps,
  CostTrendsGuide,
];

export const BY_SLUG = Object.fromEntries(POSTS.map((p) => [p.slug, p]));
