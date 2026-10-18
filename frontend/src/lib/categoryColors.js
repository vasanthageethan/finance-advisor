// The dataviz skill's categorical palette caps at 8 fixed hues, and more
// than ~7 color classes blur together anyway -- so the 7 biggest categories
// (by total spend across the loaded statements) get a real hue each, and
// everything else folds into a single "Other" bucket using a de-emphasis
// gray, never a generated 8th+ hue.
export const MAX_CATEGORIES = 7;

export function rankCategoriesBySpend(summary) {
  const totals = new Map();
  for (const month of summary) {
    for (const c of month.by_category) {
      totals.set(c.category, (totals.get(c.category) || 0) + c.total);
    }
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([category]) => category);
}

export function buildCategoryColorMap(summary) {
  const ranked = rankCategoriesBySpend(summary);
  const topCategories = ranked.slice(0, MAX_CATEGORIES);
  const colorMap = new Map();
  topCategories.forEach((category, i) => colorMap.set(category, `var(--series-${i + 1})`));
  if (ranked.length > MAX_CATEGORIES) colorMap.set("Other", "var(--series-other)");
  return { colorMap, topCategories };
}

// Reshape monthly summaries into one row per month, with the top categories
// as columns and everything past the cap summed into "Other".
export function toChartRows(summary, topCategories) {
  const topSet = new Set(topCategories);
  return summary.map((month) => {
    const row = { month: month.month, total: month.total_spend };
    let otherTotal = 0;
    for (const c of month.by_category) {
      if (topSet.has(c.category)) {
        row[c.category] = c.total;
      } else {
        otherTotal += c.total;
      }
    }
    if (otherTotal > 0) row.Other = Math.round(otherTotal * 100) / 100;
    return row;
  });
}
