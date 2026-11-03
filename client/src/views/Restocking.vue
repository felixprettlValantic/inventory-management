<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget.title') }}</h3>
        </div>
        <div class="budget-body">
          <div class="budget-value">{{ money(budget) }}</div>
          <input
            v-model.number="budget"
            type="range"
            class="budget-slider"
            min="0"
            :max="maxBudget"
            :step="BUDGET_STEP"
            :aria-label="t('restocking.budget.title')"
          />
          <div class="budget-scale">
            <span>{{ money(0) }}</span>
            <span>{{ money(maxBudget) }}</span>
          </div>
          <p class="budget-hint">{{ t('restocking.budget.hint') }}</p>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.budget') }}</div>
          <div class="stat-value">{{ money(budget) }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.stats.allocated') }}</div>
          <div class="stat-value">{{ money(recommendation.allocated) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.stats.remaining') }}</div>
          <div class="stat-value">{{ money(recommendation.remaining) }}</div>
        </div>
      </div>

      <div v-if="placedOrder" class="notice notice-success" role="status">
        <div>
          <strong>{{ t('restocking.success.title', { number: placedOrder.order_number }) }}</strong>
          <span>
            {{ t('restocking.success.summary', {
              total: money(placedOrder.total_value),
              days: placedOrder.lead_time_days,
              date: formatDate(placedOrder.expected_delivery)
            }) }}
          </span>
        </div>
        <router-link to="/orders" class="notice-link">{{ t('restocking.success.viewOrders') }}</router-link>
      </div>
      <div v-if="orderError" class="notice notice-error" role="alert">{{ orderError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommended') }} ({{ recommendation.funded.length }})</h3>
        </div>

        <div v-if="recommendation.funded.length === 0" class="empty-state">
          {{ t('restocking.nothingRecommended') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.rank') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(line, index) in recommendation.funded" :key="line.item_sku">
                <td>{{ index + 1 }}</td>
                <td><strong>{{ line.item_sku }}</strong></td>
                <td>{{ translateProductName(line.item_name) }}</td>
                <td>
                  <span :class="['badge', line.trend]">{{ t(`trends.${line.trend}`) }}</span>
                </td>
                <td>
                  <strong>{{ line.quantity }}</strong>
                  <span v-if="line.quantity < line.uplift" class="muted">
                    {{ t('restocking.needed', { count: line.uplift }) }}
                  </span>
                </td>
                <td>{{ moneyExact(line.unit_cost) }}</td>
                <td><strong>{{ moneyExact(line.lineTotal) }}</strong></td>
                <td>{{ t('restocking.days', { count: line.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card-footer">
          <button
            type="button"
            class="place-order"
            :disabled="recommendation.funded.length === 0 || placing"
            @click="placeOrder"
          >
            {{ placing ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>

      <div v-if="recommendation.unfunded.length > 0" class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.notFunded') }} ({{ recommendation.unfunded.length }})</h3>
        </div>
        <ul class="unfunded-list">
          <li v-for="item in recommendation.unfunded" :key="item.item_sku">
            <strong>{{ item.item_sku }}</strong>
            <span>{{ translateProductName(item.item_name) }}</span>
            <span class="muted">
              {{ t('restocking.unitsNeeded', { count: item.uplift }) }} @ {{ moneyExact(item.unit_cost) }}
            </span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'
import { recommendRestock, getBudgetCeiling } from '../utils/restocking'

// Budget is kept in USD, the currency the API prices in; money() converts for display.
const BUDGET_STEP = 100

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    // This view deliberately ignores the global filter bar: a restocking order is placed
    // against the whole demand forecast, not a warehouse or category slice of it.
    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)

    const placing = ref(false)
    const placedOrder = ref(null)
    const orderError = ref(null)

    const maxBudget = computed(() => getBudgetCeiling(forecasts.value))
    const recommendation = computed(() => recommendRestock(forecasts.value, budget.value))

    const money = (amount) => formatCurrency(amount, currentCurrency.value)
    const moneyExact = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

    const formatDate = (dateString) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        forecasts.value = await api.getDemandForecasts()
        // Start mid-range so the first view already shows a mix of funded and unfunded items.
        budget.value = Math.round(maxBudget.value / 2 / BUDGET_STEP) * BUDGET_STEP
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // A confirmation or error describes the budget it was made with, so drop it once that changes.
    watch(budget, () => {
      placedOrder.value = null
      orderError.value = null
    })

    const placeOrder = async () => {
      if (placing.value || recommendation.value.funded.length === 0) return

      placing.value = true
      orderError.value = null
      placedOrder.value = null
      try {
        placedOrder.value = await api.createRestockingOrder({
          items: recommendation.value.funded.map(line => ({
            sku: line.item_sku,
            quantity: line.quantity
          })),
          budget: budget.value
        })
      } catch (err) {
        // FastAPI validation errors arrive as a list in `detail`, business-rule errors as a string.
        const detail = err.response?.data?.detail
        const message = typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : err.message)
        orderError.value = t('restocking.error', { message })
      } finally {
        placing.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      BUDGET_STEP,
      loading,
      error,
      budget,
      maxBudget,
      recommendation,
      placing,
      placedOrder,
      orderError,
      money,
      moneyExact,
      formatDate,
      placeOrder,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-body {
  padding: 0.5rem 0 0.25rem;
}

.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  margin-bottom: 0.75rem;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
  cursor: pointer;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  color: #64748b;
  font-size: 0.875rem;
}

.budget-hint {
  margin: 0.75rem 0 0;
  color: #64748b;
  font-size: 0.875rem;
}

.muted {
  display: block;
  color: #64748b;
  font-size: 0.813rem;
}

.empty-state {
  padding: 2rem 1rem;
  text-align: center;
  color: #64748b;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
  margin-top: 1rem;
}

.place-order {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order:hover:not(:disabled) {
  background: #1e293b;
}

.place-order:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-radius: 10px;
  margin-bottom: 1.5rem;
  border: 1px solid;
}

.notice div {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.notice-success {
  background: #f0fdf4;
  border-color: #86efac;
  color: #166534;
}

.notice-error {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}

.notice-link {
  color: inherit;
  font-weight: 600;
  white-space: nowrap;
}

.unfunded-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.unfunded-list li {
  display: flex;
  gap: 1rem;
  align-items: baseline;
  padding: 0.625rem 0;
  border-bottom: 1px solid #f1f5f9;
}

.unfunded-list li:last-child {
  border-bottom: none;
}

.unfunded-list .muted {
  display: inline;
  margin-left: auto;
}
</style>
