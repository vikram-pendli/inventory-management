import { useI18n } from '../composables/useI18n'

// Date styles. Each maps to Intl.DateTimeFormat options; callers pick by intent:
//  - medium:  Jan 2, 2025  (default; tables and lists)
//  - short:   Jan 2        (compact labels where the year is implied)
//  - long:    January 2, 2025 (detail modals)
//  - numeric: MM/DD/YY     (dense transaction tables; built manually, see below)
const DATE_STYLES = {
  medium: { month: 'short', day: 'numeric', year: 'numeric' },
  short: { month: 'short', day: 'numeric' },
  long: { month: 'long', day: 'numeric', year: 'numeric' }
}

export function formatDate(value, style = 'medium') {
  if (!value) return '-'
  const date = new Date(value)
  // Invalid dates would otherwise render as "Invalid Date"
  if (isNaN(date.getTime())) return '-'

  if (style === 'numeric') {
    // Fixed MM/DD/YY layout regardless of locale (matches the previous Spending format)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const year = String(date.getFullYear()).slice(-2)
    return `${month}/${day}/${year}`
  }

  const { currentLocale } = useI18n()
  const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
  return date.toLocaleDateString(locale, DATE_STYLES[style] || DATE_STYLES.medium)
}
