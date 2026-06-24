export const getTodayStr = () => new Date().toISOString().split('T')[0];

export const getDaysAgoStr = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split('T')[0];
};

export const formatToLocal = (isoString) => {
  if (!isoString) return '';
  return new Date(isoString).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

export const getHourFromIso = (isoString) => {
  if (!isoString) return '';
  return isoString.split('T')[1]?.substring(0, 2) || '';
};
