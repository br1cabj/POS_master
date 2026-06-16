export const formatCurrency = (value) => {
  const num = parseFloat(value);
  return isNaN(num) ? '0' : num.toLocaleString();
};

export const formatCurrencyWithSymbol = (value) => {
  const num = parseFloat(value);
  return isNaN(num) ? '$0' : `$${num.toLocaleString()}`;
};

export const sanitizeText = (text) => {
  if (typeof text !== 'string') return text;
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

export const formatDate = (dateStr, locale = 'es-AR') => {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString(locale);
  } catch {
    return '—';
  }
};

export const formatDateTime = (dateStr, locale = 'es-AR') => {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleString(locale);
  } catch {
    return '—';
  }
};
