// Restocking recommendation logic. Kept free of Vue so it can be reasoned about on its own.
//
// Amounts are handled in whole cents internally: summing floats such as 24.99 * 150 can land a
// fraction of a cent above the budget, and the server rejects any order whose total exceeds it.

const toCents = (amount) => Math.round(amount * 100)

// Units still to be restocked: the growth the forecast expects over current demand.
const getUplift = (forecast) => forecast.forecasted_demand - forecast.current_demand

/**
 * Recommend what to restock for a budget.
 *
 * Items whose demand is not growing are skipped. The rest are ranked by uplift (largest first)
 * and funded in that order: each gets as many units as the remaining budget allows, up to its
 * uplift. An item that only partly fits is still funded for what fits, so a large item near the
 * top of the ranking cannot starve cheaper ones further down.
 */
export function recommendRestock(forecasts, budget) {
  const candidates = forecasts
    .filter(forecast => getUplift(forecast) > 0)
    .sort((a, b) => getUplift(b) - getUplift(a))

  let remainingCents = toCents(budget)
  const funded = []
  const unfunded = []

  for (const forecast of candidates) {
    const uplift = getUplift(forecast)
    const unitCents = toCents(forecast.unit_cost)
    const quantity = Math.min(uplift, Math.floor(remainingCents / unitCents))

    if (quantity <= 0) {
      unfunded.push({ ...forecast, uplift })
      continue
    }

    const lineCents = quantity * unitCents
    remainingCents -= lineCents
    funded.push({ ...forecast, uplift, quantity, lineTotal: lineCents / 100 })
  }

  const allocated = funded.reduce((sum, line) => sum + line.lineTotal, 0)

  return {
    funded,
    unfunded,
    allocated: Math.round(allocated * 100) / 100,
    remaining: remainingCents / 100
  }
}

/**
 * Upper bound for the budget slider: what it costs to fully fund every growing item,
 * rounded up to the next `step` so the slider can reach "everything funded".
 */
export function getBudgetCeiling(forecasts, step = 1000) {
  const fullCostCents = forecasts
    .filter(forecast => getUplift(forecast) > 0)
    .reduce((sum, forecast) => sum + getUplift(forecast) * toCents(forecast.unit_cost), 0)

  return Math.max(step, Math.ceil(fullCostCents / 100 / step) * step)
}
