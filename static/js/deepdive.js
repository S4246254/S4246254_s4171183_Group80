/* deepdive.js — Level 3: Deep dive nested query */

let l3Chart = null;

function handleL3Error(message) {
  const tbody = document.getElementById('l3tbody');
  const box   = document.getElementById('l3-insight');
  tbody.innerHTML = `<tr><td colspan="7" class="loading">${message}</td></tr>`;
  box.classList.add('hidden');
}

function renderL3Table(rows) {
  const tbody = document.getElementById('l3tbody');
  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">No conditions exceed the statewide average for this filter.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((r, i) => {
    const avg = r.avg_persons ?? 0;
    const sv = severityLabel(avg);
    return `<tr>
      <td><span class="rank-circle">${i + 1}</span></td>
      <td>${r.condition}</td>
      <td>${fmtNum(r.total_accidents)}</td>
      <td>${fmtNum(r.fatal_count)}</td>
      <td>${r.fatal_pct}%</td>
      <td>${avg.toFixed(2)}</td>
      <td><span class="badge ${sv.cls}">${sv.label}</span></td>
    </tr>`;
  }).join('');
}

function renderL3Chart(rows, avgCount) {
  if (!window.Chart || !rows || !rows.length) {
    return;
  }

  const labels    = rows.map(r => r.condition);
  const sevScores = rows.map(r => r.avg_persons ?? 0);
  const colors    = rows.map(r => (r.avg_persons ?? 0) <= 2.5 ? '#E24B4A' : '#378ADD');
  const canvas    = document.getElementById('l3chart');
  const wrapper   = canvas.parentElement;
  const h         = Math.max(220, rows.length * 52 + 60);
  wrapper.style.height = h + 'px';

  if (l3Chart) l3Chart.destroy();
  l3Chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Avg severity index',
          data: sevScores,
          backgroundColor: colors,
          borderRadius: 4,
        },
        {
          label: 'Statewide avg severity',
          data: rows.map(() => avgCount),
          type: 'line',
          borderColor: '#888780',
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        }
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          min: 0,
          max: 5,
          ticks: { font: { size: 11 } },
          title: { display: true, text: 'Avg severity (1=Fatal → 4=PDO)', font: { size: 11 } }
        },
        y: { ticks: { font: { size: 11 } } }
      }
    }
  });
}

function renderL3Insight(rows, avgCount, dim) {
  const box = document.getElementById('l3-insight');
  if (!rows || !rows.length) {
    box.classList.add('hidden');
    return;
  }
  const dimLabel = { road: 'road surface', atmos: 'atmospheric', light: 'light' }[dim];
  box.innerHTML = `<strong>Nested query result:</strong> The statewide average is
    <strong>${fmtNum(Math.round(avgCount))}</strong> accidents per ${dimLabel} condition.
    <strong>${rows.length}</strong> condition(s) exceed this threshold and are shown below,
    ranked by severity. These represent the highest-risk conditions for your persona to investigate.`;
  box.classList.remove('hidden');
}

function updateSQL(dim) {
  const colMap = { road: 'ROAD_SURFACE', atmos: 'ATMOSPHERIC', light: 'LIGHT_COND' };
  const col = colMap[dim] || 'ROAD_SURFACE';
  document.getElementById('sqlDisplay').textContent =
`SELECT condition, total_accidents, avg_severity
FROM (
    SELECT ${col} AS condition,
           COUNT(*) AS total_accidents,
           AVG(SEVERITY) AS avg_severity
    FROM ACCIDENT
    GROUP BY ${col}
) inner_summary
WHERE total_accidents > (
    SELECT AVG(cond_count)
    FROM (SELECT COUNT(*) AS cond_count
          FROM ACCIDENT GROUP BY ${col})
)
ORDER BY avg_severity ASC`;
}

async function loadLevel3() {
  try {
    const dim      = document.getElementById('l3dim').value;
    const highOnly = document.getElementById('l3sev').value;

    const res = await fetch(
      `/api/level3?dim=${encodeURIComponent(dim)}&high_only=${encodeURIComponent(highOnly)}`
    );

    if (!res.ok) {
      const error = await res.json().catch(() => null);
      throw new Error(error?.error || 'Failed to load data from the server.');
    }

    const data = await res.json();
    if (!data || !Array.isArray(data.rows)) {
      throw new Error('Unexpected data format returned from the server.');
    }

    renderL3Table(data.rows);
    renderL3Chart(data.rows, data.statewide_avg);
    renderL3Insight(data.rows, data.statewide_avg, dim);
    updateSQL(dim);
  } catch (err) {
    console.error(err);
    handleL3Error(err.message || 'Unable to load data.');
  }
}

function ready(fn) {
  if (document.readyState !== 'loading') {
    fn();
  } else {
    document.addEventListener('DOMContentLoaded', fn);
  }
}

ready(loadLevel3);
