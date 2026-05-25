/* conditions.js — Level 2: Conditions summary */

let l2Chart = null;

async function loadLevel2() {
  const dim      = document.getElementById('condType').value;
  const minCount = document.getElementById('minCount').value;

  const res  = await fetch(`/api/level2?dim=${dim}&min_count=${minCount}`);
  const rows = await res.json();

  renderL2Table(rows);
  renderL2Chart(rows, dim);
  renderL2Insight(rows, dim);
}

function renderL2Table(rows) {
  const tbody = document.getElementById('l2tbody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No results for this filter.</td></tr>';
    return;
  }
  const maxTotal = rows[0].total_accidents;
  tbody.innerHTML = rows.map(r => {
    const barPct = Math.round((r.total_accidents / maxTotal) * 100);
    const sv = severityLabel(r.avg_severity);
    return `<tr>
      <td>${r.condition}</td>
      <td>
        <div class="bar-wrap">
          <div class="inline-bar" style="width:${barPct}px; max-width:120px;"></div>
          <span>${fmtNum(r.total_accidents)}</span>
        </div>
      </td>
      <td>${fmtNum(r.fatal_count)}</td>
      <td>${r.fatal_pct}%</td>
      <td><span class="badge ${sv.cls}">${r.avg_severity.toFixed(2)}</span></td>
    </tr>`;
  }).join('');
}

function renderL2Chart(rows, dim) {
  const labels = rows.map(r => r.condition);
  const counts = rows.map(r => r.total_accidents);

  const canvas  = document.getElementById('l2chart');
  const wrapper = canvas.parentElement;
  wrapper.style.height = '260px';

  if (l2Chart) l2Chart.destroy();
  l2Chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Total accidents',
        data: counts,
        backgroundColor: '#378ADD',
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { font: { size: 11 }, maxRotation: 30 },
          grid: { display: false }
        },
        y: {
          ticks: {
            font: { size: 11 },
            callback: v => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v
          },
          grid: { color: 'rgba(0,0,0,0.06)' }
        }
      }
    }
  });
}

function renderL2Insight(rows, dim) {
  const box = document.getElementById('l2-insight');
  if (!rows.length) { box.classList.add('hidden'); return; }

  const total      = rows.reduce((s, r) => s + r.total_accidents, 0);
  const totalFatal = rows.reduce((s, r) => s + r.fatal_count, 0);
  const worst      = [...rows].sort((a, b) => a.avg_severity - b.avg_severity)[0];
  const dimLabel   = { road: 'road surface', atmos: 'atmospheric', light: 'light' }[dim];

  box.innerHTML = `<strong>Key finding:</strong> Under the selected ${dimLabel} filter,
    <strong>${fmtNum(total)}</strong> total accidents and
    <strong>${fmtNum(totalFatal)}</strong> fatal incidents are recorded.
    The highest-severity condition is <strong>${worst.condition}</strong>
    (avg severity index: ${worst.avg_severity.toFixed(2)}).`;
  box.classList.remove('hidden');
}

// Load on page ready
document.addEventListener('DOMContentLoaded', loadLevel2);
