import { useI18n } from './useI18n'

export function useTranslators() {
  const { t } = useI18n()

  // Covers both product categories and Spending's spending categories.
  // Spending categories are checked first (no key overlap today); unknown values pass through.
  const translateCategory = (category) => {
    const categoryMap = {
      'Raw Materials': t('spendingCategories.rawMaterials'),
      'Components': t('spendingCategories.components'),
      'Equipment': t('spendingCategories.equipment'),
      'Consumables': t('spendingCategories.consumables'),
      'Circuit Boards': t('categories.circuitBoards'),
      'Sensors': t('categories.sensors'),
      'Actuators': t('categories.actuators'),
      'Controllers': t('categories.controllers'),
      'Power Supplies': t('categories.powerSupplies')
    }
    return categoryMap[category] || category
  }

  // Accepts both lower-case (API) and capitalized priorities
  const translatePriority = (priority) => {
    const priorityMap = {
      'high': t('priority.high'),
      'medium': t('priority.medium'),
      'low': t('priority.low'),
      'High': t('priority.high'),
      'Medium': t('priority.medium'),
      'Low': t('priority.low')
    }
    return priorityMap[priority] || priority
  }

  // t() returns the key itself when missing; fall back to the raw status
  // (covers statuses such as 'Submitted' via status.submitted)
  const translateStatus = (status) => {
    if (!status) return '-'
    const key = `status.${String(status).toLowerCase()}`
    const label = t(key)
    return label && label !== key ? label : status
  }

  return { translateCategory, translatePriority, translateStatus }
}
