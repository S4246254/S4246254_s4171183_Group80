/* deepdive.js — Level 3: Deep dive nested query */

let l3Chart = null;

async function loadLevel3() {
  const dim      = document.getElementById('l3dim').value;
  const highOnly = document.getElementById('l3sev').value;

  const res  = await fetch(`/api/level3?dim=${dim}&high_only=${highOnly}`);
  const data = await res.json();

  renderL3Table(data.rows);
  renderL3Chart(data.rows, data.statewide_avg);
  renderL3Insight(data.rows, data.statewide_avg, dim);
  updateSQL(dim);
}

function renderL3Table(rows) {
  const tbody = document.getElementById('l3tbody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">No conditions exceed the statewide average for this filter.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((r, i) => {
    const sv = severityLabel(r.avg_severity);
    return `<tr>
      <td><span class="rank-circle">${i + 1}</span></td>
      <td>${r.condition}</td>
      <td>${fmtNum(r.total_accidents)}</td>
      <td>${fmtNum(r.fatal_count)}</td>
      <td>${r.fatal_pct}%</td>
      <td>${r.avg_severity.toFixed(2)}</td>
      <td><span class="badge ${sv.cls}">${sv.label}</span></td>
    </tr>`;
  }).join('');
}

function renderL3Chart(rows, avgCount) {
  const labels   = rows.map(r => r.condition);
  const sevScores = rows.map(r => r.avg_severity);
  const colors   = rows.map(r => r.avg_severity <= 2.5 ? '#E24B4A' : '#378ADD');
  const avgLine  = rows.map(() => parseFloat((avgCount / 1000).toFixed(2)));

  const canvas  = document.getElementById('l3chart');
  const wrapper = canvas.parentElement;
  const h = Math.max(220, rows.length * 52 + 60);
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
          data: rows.map(() => rows.reduce((s, r) => s + r.avg_severity, 0) / rows.length),
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
  if (!rows.length) { box.classList.add('hidden'); return; }
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

document.addEventListener('DOMContentLoaded', loadLevel3);
