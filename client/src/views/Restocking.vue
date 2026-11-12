<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <label class="budget-label" for="restocking-budget">{{ t('restocking.budget') }}</label>
        <div class="budget-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        <input
          id="restocking-budget"
          v-model.number="budget"
          class="budget-slider"
          type="range"
          :min="BUDGET_MIN"
          :max="BUDGET_MAX"
          :step="BUDGET_STEP"
        />
        <div class="budget-scale">
          <span>{{ currencySymbol }}{{ BUDGET_MIN.toLocaleString() }}</span>
          <span>{{ currencySymbol }}{{ BUDGET_MAX.toLocaleString() }}</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budgetUsed') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ formatMoney(budgetUsed) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.budgetRemaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ formatMoney(budgetRemaining) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header header-row">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ recommendations.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting || justOrdered"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="successMessage" class="notice notice-success" role="status">{{ successMessage }}</div>
        <div v-if="submitError" class="notice notice-error" role="alert">{{ submitError }}</div>

        <div v-if="recommendations.length === 0" class="empty-state">{{ t('restocking.noRecommendations') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.onHand') }}</th>
                <th>{{ t('restocking.table.forecast') }}</th>
                <th>{{ t('restocking.table.shortfall') }}</th>
                <th>{{ t('restocking.table.orderQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in recommendations" :key="line.sku">
                <td><strong>{{ line.sku }}</strong></td>
                <td>{{ translateProductName(line.name) }}</td>
                <td>
                  <span :class="['badge', line.trend]">{{ t(`trends.${line.trend}`) }}</span>
                </td>
                <td>{{ line.onHand.toLocaleString() }}</td>
                <td>{{ line.forecast.toLocaleString() }}</td>
                <td>{{ line.shortfall.toLocaleString() }}</td>
                <td><strong>{{ line.quantity.toLocaleString() }}</strong></td>
                <td>{{ currencySymbol }}{{ formatMoney(line.unitCost) }}</td>
                <td><strong>{{ currencySymbol }}{{ formatMoney(line.lineTotal) }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const BUDGET_MIN = 0
const BUDGET_MAX = 500000
const BUDGET_STEP = 5000

const { t, currentCurrency, translateProductName } = useI18n()

const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

const loading = ref(true)
const error = ref(null)
const forecasts = ref([])
const budget = ref(100000)

const submitting = ref(false)
const successMessage = ref('')
const submitError = ref('')
const justOrdered = ref(false)

const formatMoney = (value) =>
  value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Any slider move invalidates the previous order notice and re-enables ordering
watch(budget, () => {
  successMessage.value = ''
  submitError.value = ''
  justOrdered.value = false
})

const TREND_PRIORITY = { increasing: 0, stable: 1, decreasing: 2 }

// Greedy allocation: items are ordered by trend priority, then largest shortfall.
// Each item is funded up to its full shortfall, or partially with whatever budget
// remains. Items that cannot afford even one unit are skipped, but the walk
// continues because cheaper items further down the list may still fit.
// Money is tracked in integer cents to avoid floating-point drift.
const recommendations = computed(() => {
  const candidates = forecasts.value
    .map(f => ({
      sku: f.item_sku,
      name: f.item_name,
      trend: f.trend,
      onHand: f.quantity_on_hand,
      forecast: f.forecasted_demand,
      shortfall: f.forecasted_demand - f.quantity_on_hand,
      unitCost: f.unit_cost
    }))
    .filter(c => c.shortfall > 0 && c.unitCost > 0)
    .sort((a, b) => {
      const pa = TREND_PRIORITY[a.trend] ?? 3
      const pb = TREND_PRIORITY[b.trend] ?? 3
      return pa - pb || b.shortfall - a.shortfall
    })

  let remainingCents = Math.round(budget.value * 100)
  const lines = []
  for (const c of candidates) {
    const unitCents = Math.round(c.unitCost * 100)
    if (unitCents <= 0) continue
    const quantity = Math.min(c.shortfall, Math.floor(remainingCents / unitCents))
    if (quantity > 0) {
      const lineCents = quantity * unitCents
      lines.push({ ...c, quantity, lineCents, lineTotal: lineCents / 100 })
      remainingCents -= lineCents
    }
  }
  return lines
})

const budgetUsedCents = computed(() => recommendations.value.reduce((sum, l) => sum + l.lineCents, 0))
const budgetUsed = computed(() => budgetUsedCents.value / 100)
const budgetRemaining = computed(() => Math.max(0, Math.round(budget.value * 100) - budgetUsedCents.value) / 100)

const loadForecasts = async () => {
  try {
    loading.value = true
    error.value = null
    forecasts.value = await api.getDemandForecasts()
  } catch (err) {
    error.value = 'Failed to load demand forecasts: ' + err.message
    console.error('Load error:', err)
  } finally {
    loading.value = false
  }
}

const placeOrder = async () => {
  if (submitting.value || recommendations.value.length === 0) return
  submitting.value = true
  successMessage.value = ''
  submitError.value = ''
  try {
    const order = await api.createRestockingOrder({
      budget: budget.value,
      lines: recommendations.value.map(l => ({ sku: l.sku, quantity: l.quantity }))
    })
    successMessage.value = t('restocking.orderPlaced', {
      orderNumber: order.order_number,
      days: order.lead_time_days
    })
    justOrdered.value = true
  } catch (err) {
    const detail = err?.response?.data?.detail
    const detailText = typeof detail === 'string' ? detail : ''
    submitError.value = detailText
      ? `${t('restocking.orderFailed')} ${detailText}`
      : t('restocking.orderFailed')
    console.error('Order error:', err)
  } finally {
    submitting.value = false
  }
}

onMounted(loadForecasts)
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748b;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0.25rem 0 1rem;
}

.budget-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #cbd5e1;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.4);
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.4);
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #cbd5e1;
}

.budget-slider:focus-visible::-webkit-slider-thumb {
  box-shadow: 0 0 0 3px #ffffff, 0 0 0 5px #3b82f6;
}

.budget-slider:focus-visible::-moz-range-thumb {
  box-shadow: 0 0 0 3px #ffffff, 0 0 0 5px #3b82f6;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #ffffff;
  background: #0f172a;
  border: 1px solid #0f172a;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.place-order-btn:disabled {
  background: #94a3b8;
  border-color: #94a3b8;
  cursor: not-allowed;
}

.notice {
  margin: 1rem 1.5rem 0;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.notice-success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.notice-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}
</style>
