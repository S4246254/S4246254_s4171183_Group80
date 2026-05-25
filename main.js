/* main.js — shared utilities */

function severityLabel(avg) {
  if (avg <= 1.5) return { label: 'Fatal risk', cls: 'badge-high' };
  if (avg <= 2.5) return { label: 'High risk',   cls: 'badge-high' };
  if (avg <= 3.2) return { label: 'Moderate',    cls: 'badge-med'  };
  return              { label: 'Lower risk',  cls: 'badge-low'  };
}

function fmtNum(n) {
  return Number(n).toLocaleString();
}
