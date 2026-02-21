export function fmt(n, suffix = '') {
  if (n == null || isNaN(n)) return 'N/A';
  return n.toFixed(2) + suffix;
}

export function fmtPct(n) {
  if (n == null || isNaN(n)) return 'N/A';
  return (n * 100).toFixed(2) + '%';
}

export function fmtNum(n, decimals = 3) {
  if (n == null || isNaN(n)) return 'N/A';
  return n.toFixed(decimals);
}

export function isPositive(n) {
  return n >= 0;
}

export function colorClass(n) {
  return n >= 0 ? 'text-green' : 'text-red';
}

export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
