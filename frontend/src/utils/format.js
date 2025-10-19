export function formatNumber(num) {
  return new Intl.NumberFormat('en-US').format(num);
}

export function formatPercent(num) {
  return `${num.toFixed(1)}%`;
}
