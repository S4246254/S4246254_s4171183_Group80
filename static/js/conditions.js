/* conditions.js — Level 2: Conditions summary */

let l2Chart = null;

function handleL2Error(message) {
  const tbody = document.getElementById('l2tbody');
  const box   = document.getElementById('l2-insight');
  tbody.innerHTML = `<tr><td colspan="5" class="loading">${message}</td></tr>`;
  box.classList.add('hidden');
}

function renderL2Table(rows) {
  const tbody = document.getElementById('l2tbody');
  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No results for this filter.</td></tr>';
    return;
  }

  const maxTotal = rows[0].total_accidents || 1;
  tbody.innerHTML = rows.map(r => {
    const barPct = Math.round((r.total_accidents / maxTotal) * 100);
    const avg = r.avg_persons ?? 0;
    const sv = severityLabel(avg);
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
      <td><span class="badge ${sv.cls}">${avg.toFixed(2)}</span></td>
    </tr>`;
  }).join('');
}

function renderL2Chart(rows) {
  const canvas  = document.getElementById('l2chart');
  const wrapper = canvas.parentElement;
  wrapper.style.height = '260px';

  if (!window.Chart || !rows || !rows.length) {
    return;
  }

  const labels = rows.map(r => r.condition);
  const counts = rows.map(r => r.total_accidents);

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
  if (!rows || !rows.length) {
    box.classList.add('hidden');
    return;
  }

  const total      = rows.reduce((s, r) => s + r.total_accidents, 0);
  const totalFatal = rows.reduce((s, r) => s + r.fatal_count, 0);
  const worst      = [...rows].sort((a, b) => (a.avg_persons ?? 0) - (b.avg_persons ?? 0))[0];
  const dimLabel   = { road: 'road surface', atmos: 'atmospheric', light: 'light' }[dim];
  const avgWorst   = worst ? (worst.avg_persons ?? 0) : 0;

  box.innerHTML = `<strong>Key finding:</strong> Under the selected ${dimLabel} filter,
    <strong>${fmtNum(total)}</strong> total accidents and
    <strong>${fmtNum(totalFatal)}</strong> fatal incidents are recorded.
    The highest-average condition is <strong>${worst.condition}</strong>
    (avg persons per accident: ${avgWorst.toFixed(2)}).`;
  box.classList.remove('hidden');
}

async function loadLevel2() {
  try {
    const dim      = document.getElementById('condType').value;
    const minCount = document.getElementById('minCount').value;

    const res = await fetch(
      `/api/level2?dim=${encodeURIComponent(dim)}&min_count=${encodeURIComponent(minCount)}`
    );

    if (!res.ok) {
      const error = await res.json().catch(() => null);
      throw new Error(error?.error || 'Failed to load data from the server.');
    }

    const rows = await res.json();
    if (!Array.isArray(rows)) {
      throw new Error('Unexpected data format returned from the server.');
    }

    renderL2Table(rows);
    renderL2Chart(rows);
    renderL2Insight(rows, dim);
  } catch (err) {
    console.error(err);
    handleL2Error(err.message || 'Unable to load data.');
  }
}

function ready(fn) {
  if (document.readyState !== 'loading') {
    fn();
  } else {
    document.addEventListener('DOMContentLoaded', fn);
  }
}

ready(loadLevel2);
