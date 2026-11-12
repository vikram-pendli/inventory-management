<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="isEmpty" class="card empty-state">{{ t('reports.empty') }}</div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterlyPerformance') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.table.quarter') }}</th>
                <th>{{ t('reports.table.totalOrders') }}</th>
                <th>{{ t('reports.table.totalRevenue') }}</th>
                <th>{{ t('reports.table.avgOrderValue') }}</th>
                <th>{{ t('reports.table.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ formatQuarter(q.quarter) }}</strong></td>
                <td>{{ q.total_orders }}</td>
                <td>{{ formatMoney(q.total_revenue) }}</td>
                <td>{{ formatMoney(q.avg_order_value) }}</td>
                <td>
                  <span :class="['badge', getFulfillmentClass(q.fulfillment_rate)]">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyRevenueTrend') }}</h3>
        </div>
        <div class="chart-container">
          <div class="bar-chart">
            <div v-for="row in monthlyRows" :key="row.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  role="img"
                  :aria-label="row.label + ': ' + row.revenueText"
                  :style="{ height: getBarHeight(row.revenue) + 'px' }"
                  :title="row.label + ': ' + row.revenueText"
                ></div>
              </div>
              <div class="bar-label">{{ row.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthOverMonth') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.table.month') }}</th>
                <th>{{ t('reports.table.orders') }}</th>
                <th>{{ t('reports.table.revenue') }}</th>
                <th>{{ t('reports.table.change') }}</th>
                <th>{{ t('reports.table.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthlyRows" :key="row.month">
                <td><strong>{{ row.label }}</strong></td>
                <td>{{ row.order_count }}</td>
                <td>{{ row.revenueText }}</td>
                <td>
                  <span v-if="row.changeText" :class="row.changeClass">{{ row.changeText }}</span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="row.growthText" :class="row.changeClass">{{ row.growthText }}</span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats (totals over whatever the active filters select) -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalOrders') }}</div>
          <div class="stat-value">{{ totalOrders }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

const MONTH_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
const MAX_BAR_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentCurrency } = useI18n()
    const { selectedPeriod, selectedLocation, selectedCategory, selectedStatus, getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Only the latest request may update state, so quick filter changes cannot show stale data
    let requestId = 0
    const loadData = async () => {
      const currentRequest = ++requestId
      loading.value = true
      error.value = null
      try {
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReport(filters),
          api.getMonthlyTrends(filters)
        ])
        if (currentRequest !== requestId) return
        quarterlyData.value = Array.isArray(quarterly) ? quarterly : []
        monthlyData.value = Array.isArray(monthly) ? monthly : []
      } catch (err) {
        if (currentRequest !== requestId) return
        error.value = t('reports.loadFailed') + ': ' + err.message
      } finally {
        if (currentRequest === requestId) loading.value = false
      }
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadData()
    })

    onMounted(() => {
      loadData()
    })

    const isEmpty = computed(() => quarterlyData.value.length === 0 && monthlyData.value.length === 0)

    const totalRevenue = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (Number(m.revenue) || 0), 0)
    )
    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )
    const totalOrders = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (Number(m.order_count) || 0), 0)
    )
    const maxRevenue = computed(() =>
      Math.max(0, ...monthlyData.value.map(m => Number(m.revenue) || 0))
    )

    const formatQuarter = (quarterStr) => {
      // Server sends 'Q1-2025'; fall back to the raw string if the shape is unexpected
      const match = /^Q([1-4])-(\d{4})$/.exec(String(quarterStr))
      if (!match) return quarterStr
      return t('reports.quarterLabel', { quarter: match[1], year: match[2] })
    }

    const bestQuarter = computed(() => {
      let best = null
      for (const q of quarterlyData.value) {
        if (!best || q.total_revenue > best.total_revenue) best = q
      }
      return best && best.total_revenue > 0 ? formatQuarter(best.quarter) : '-'
    })

    const formatMoney = (amount) =>
      formatCurrencyWithDecimals(Number(amount) || 0, currentCurrency.value, 2)

    const formatMonth = (monthStr) => {
      // Convert YYYY-MM to a localized label; validate before indexing the month names
      const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(String(monthStr))
      if (!match) return monthStr
      return t('reports.monthLabel', {
        month: t(`months.${MONTH_KEYS[parseInt(match[2], 10) - 1]}`),
        year: match[1]
      })
    }

    const getBarHeight = (revenue) => {
      if (maxRevenue.value === 0) return 0
      return ((Number(revenue) || 0) / maxRevenue.value) * MAX_BAR_HEIGHT
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    const formatChange = (change) => {
      if (change === 0) return formatMoney(0)
      return (change > 0 ? '+' : '-') + formatMoney(Math.abs(change))
    }

    const formatGrowth = (current, previous) => {
      if (previous === 0) return t('reports.notAvailable')
      const rate = ((current - previous) / previous) * 100
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    // Each row is compared with the previous *listed* month. Under filters (e.g. a status
    // filter) months can be missing, so the previous row is not always the adjacent calendar month.
    const monthlyRows = computed(() =>
      monthlyData.value.map((m, index) => {
        const revenue = Number(m.revenue) || 0
        const label = formatMonth(m.month)
        const row = {
          month: m.month,
          order_count: m.order_count,
          revenue,
          label,
          revenueText: formatMoney(revenue),
          changeText: '',
          growthText: '',
          changeClass: ''
        }
        if (index > 0) {
          const previous = Number(monthlyData.value[index - 1].revenue) || 0
          const change = revenue - previous
          row.changeText = formatChange(change)
          row.growthText = formatGrowth(revenue, previous)
          row.changeClass = change > 0 ? 'positive-change' : change < 0 ? 'negative-change' : ''
        }
        return row
      })
    )

    return {
      t,
      loading,
      error,
      isEmpty,
      quarterlyData,
      monthlyRows,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      formatQuarter,
      formatMoney,
      getBarHeight,
      getFulfillmentClass
    }
  }
}
</script>

<style scoped>
/* Cards, tables, badges, stat tiles, loading and error styles come from App.vue */
.stat-card {
  border-left: 4px solid #2563eb;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #64748b;
}

.chart-container {
  padding: 2rem 1rem;
  min-height: 300px;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #2563eb, #3b82f6);
  border-radius: 4px 4px 0 0;
  transition: all 0.3s;
  cursor: pointer;
}

.bar:hover {
  background: linear-gradient(to top, #1d4ed8, #2563eb);
}

.bar-label {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.positive-change {
  color: #059669;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>
