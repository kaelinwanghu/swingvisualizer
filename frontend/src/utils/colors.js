function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: Number.parseInt(result[1], 16),
    g: Number.parseInt(result[2], 16),
    b: Number.parseInt(result[3], 16)
  } : { r: 0, g: 0, b: 0 };
}

function interpolateColor(color1, color2, factor) {
  const c1 = hexToRgb(color1);
  const c2 = hexToRgb(color2);
  const r = Math.round(c1.r + factor * (c2.r - c1.r));
  const g = Math.round(c1.g + factor * (c2.g - c1.g));
  const b = Math.round(c1.b + factor * (c2.b - c1.b));
  return `rgb(${r}, ${g}, ${b})`;
}

export function getCountyColor(value, mode, partyColors) {
  if (mode === 'absolute') {
    // Value is dem_share (0-100)
    if (value > 50) {
      const intensity = Math.min((value - 50) / 50, 1);
      return interpolateColor(partyColors.NEUTRAL, partyColors.DEMOCRAT, intensity);
    } else {
      const intensity = Math.min((50 - value) / 50, 1);
      return interpolateColor(partyColors.NEUTRAL, partyColors.REPUBLICAN, intensity);
    }
  } else {
    // Swing mode: value is change in dem_share
    const maxSwing = 20;
    if (value > 0) {
      const intensity = Math.min(Math.abs(value) / maxSwing, 1);
      return interpolateColor(partyColors.NEUTRAL, partyColors.SWING_DEM, intensity);
    } else {
      const intensity = Math.min(Math.abs(value) / maxSwing, 1);
      return interpolateColor(partyColors.NEUTRAL, partyColors.SWING_REP, intensity);
    }
  }
}
