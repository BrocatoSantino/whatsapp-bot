import re

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/historial.html', 'r') as f:
    text = f.read()

# 1. Add IDs to elements we want to update
text = text.replace('{{ range_str }}</div>', '{{ range_str }}</div>', 1) # wait, easier to regex
text = re.sub(r'<div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.2rem;">\{\{ range_str \}\}</div>', 
              r'<div id="hist_range_str" style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.2rem;">{{ range_str }}</div>', text)

text = re.sub(r'<span class="badge"[^>]*>\{% if mode == \'week\' %\}ESTA SEMANA\{% else %\}ESTE MES\{% endif %\}</span>', 
              r'<span id="hist_badge" class="badge" style="background: var(--text-primary); color: var(--bg-primary);">{% if mode == "week" %}ESTA SEMANA{% else %}ESTE MES{% endif %}</span>', text)

text = re.sub(r'<h2 class="timeline-header" style="font-size: 1.25rem;">Resumen \{% if mode == \'week\' %\}Semanal\{% else %\}Mensual\{% endif %\}</h2>', 
              r'<h2 id="hist_title" class="timeline-header" style="font-size: 1.25rem;">Resumen {% if mode == "week" %}Semanal{% else %}Mensual{% endif %}</h2>', text)

text = re.sub(r'<span class="bento-value" style="font-size: 1.5rem;">\{\{ completed_cuts \}\}</span>', 
              r'<span id="hist_cuts" class="bento-value" style="font-size: 1.5rem;">{{ completed_cuts }}</span>', text)

text = re.sub(r'<span class="bento-value" style="font-size: 1.5rem;">\{\{ time_str \}\}</span>', 
              r'<span id="hist_time" class="bento-value" style="font-size: 1.5rem;">{{ time_str }}</span>', text)

text = re.sub(r'<span class="bento-value" style="font-size: 1.5rem; color: var\(--success\);">\$\{\{ "\{:,\.0f\}"\.format\(total_revenue\)\.replace\(",", "\."\) \}\}</span>', 
              r'<span id="hist_revenue" class="bento-value" style="font-size: 1.5rem; color: var(--success);">${{ "{:,.0f}".format(total_revenue).replace(",", ".") }}</span>', text)

# Give IDs to buttons to change styling easily or we can just update them using querySelector
# Also intercept clicks on a tags
# Add id to recent cuts container
text = text.replace('<div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem;">', '<div id="hist_recent_list" style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem;">')


# 2. Rewrite the JS logic to support AJAX
new_js = """
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
let histChart = null;

function renderChart(dailyCounts, dailyDates, isMonth) {
    const ctx = document.getElementById('weeklyChart').getContext('2d');
    if (histChart) {
        histChart.destroy();
    }
    
    let labels = [];
    if (isMonth) {
        labels = dailyDates;
    } else {
        const days = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
        labels = days.map((day, index) => `${day}\\n${dailyDates[index]}`);
    }

    let gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(252, 76, 2, 0.5)');
    gradient.addColorStop(1, 'rgba(252, 76, 2, 0.0)');

    const isLight = document.documentElement.classList.contains('light-mode');
    const textColor = isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)';
    const gridColor = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.05)';

    histChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cortes completados',
                data: dailyCounts,
                borderColor: '#fc4c02',
                backgroundColor: gradient,
                borderWidth: 3,
                pointBackgroundColor: '#fff',
                pointBorderColor: '#fc4c02',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            layout: { padding: { left: 10, right: 10 } },
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: function(context) { return context.raw === 1 ? '1 corte' : context.raw + ' cortes'; }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, color: textColor, font: { size: 11 } },
                    grid: { color: gridColor, drawBorder: false }
                },
                x: {
                    ticks: { color: textColor, maxTicksLimit: 7, maxRotation: 0, minRotation: 0, font: { size: 10 } },
                    grid: { display: false, drawBorder: false }
                }
            },
            interaction: { intersect: false, mode: 'index' }
        }
    });
}

function loadHistoryData(url) {
    const container = document.querySelector('.fade-in');
    container.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    container.style.opacity = '0';
    container.style.transform = 'scale(0.98)';
    
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(res => res.json())
        .then(data => {
            document.getElementById('hist_range_str').innerText = data.range_str;
            
            const badge = document.getElementById('hist_badge');
            if(badge) badge.innerText = data.mode === 'week' ? 'ESTA SEMANA' : 'ESTE MES';
            
            document.getElementById('hist_title').innerText = data.mode === 'week' ? 'Resumen Semanal' : 'Resumen Mensual';
            document.getElementById('hist_cuts').innerText = data.completed_cuts;
            document.getElementById('hist_time').innerText = data.time_str;
            
            let revStr = data.total_revenue.toLocaleString('es-AR', {minimumFractionDigits:0, maximumFractionDigits:0});
            document.getElementById('hist_revenue').innerText = '$' + revStr;
            
            // Re-render chart
            renderChart(data.daily_counts, data.daily_dates, data.mode === 'month');
            
            // Update URL parameters without reloading
            window.history.pushState({}, '', url);
            
            // Update active state of Week/Month toggles
            const urlObj = new URL(url, window.location.origin);
            const newMode = urlObj.searchParams.get('mode') || 'week';
            const newOffset = parseInt(urlObj.searchParams.get('offset') || '0');
            
            document.querySelectorAll('.mode-toggle-btn').forEach(btn => {
                const btnMode = btn.getAttribute('data-mode');
                if (btnMode === newMode) {
                    btn.style.color = 'var(--bg-primary)';
                    btn.style.background = 'var(--text-primary)';
                } else {
                    btn.style.color = 'var(--text-secondary)';
                    btn.style.background = 'transparent';
                }
                btn.href = `?offset=${newOffset}&mode=${btnMode}`;
            });
            
            // Update arrows
            const prevArrow = document.getElementById('nav_prev');
            const nextArrow = document.getElementById('nav_next');
            if(prevArrow) prevArrow.href = `?offset=${newOffset - 1}&mode=${newMode}`;
            if(nextArrow) {
                nextArrow.href = `?offset=${newOffset + 1}&mode=${newMode}`;
                if (newOffset >= 0) {
                    nextArrow.style.opacity = '0.5';
                    nextArrow.style.pointerEvents = 'none';
                } else {
                    nextArrow.style.opacity = '1';
                    nextArrow.style.pointerEvents = 'auto';
                }
            }
            
            // Render recent list if it exists
            const recentList = document.getElementById('hist_recent_list');
            if(recentList) {
                recentList.innerHTML = '';
                data.recent_completed_cuts.forEach(appt => {
                    let priceStr = appt.price.toLocaleString('es-AR', {minimumFractionDigits:0, maximumFractionDigits:0});
                    recentList.innerHTML += `
                    <div class="stat-row">
                        <div>
                            <div style="font-weight: 600; margin-bottom: 0.2rem;">${appt.client} <span style="color: var(--text-secondary); font-weight: 400; font-size: 0.85rem;">- ${appt.service}</span></div>
                            <div style="color: var(--text-secondary); font-size: 0.85rem;">${appt.date}, ${appt.time}</div>
                        </div>
                        <div style="font-weight: 700; color: var(--success);">+$${priceStr}</div>
                    </div>`;
                });
            }
            
            setTimeout(() => {
                container.style.opacity = '1';
                container.style.transform = 'scale(1)';
            }, 50);
        });
}

document.addEventListener('DOMContentLoaded', function() {
    // Initial render
    const dailyCounts = {{ daily_counts | tojson }};
    const dailyDates = {{ daily_dates | safe }};
    const isMonth = "{{ mode }}" === "month";
    renderChart(dailyCounts, dailyDates, isMonth);
    
    // Intercept clicks
    document.querySelector('.fade-in').addEventListener('click', function(e) {
        const a = e.target.closest('a');
        if (a && a.href && a.href.includes('?offset=')) {
            e.preventDefault();
            loadHistoryData(a.href);
        }
    });
});
</script>
"""

# Remove old script block
text = re.sub(r'<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>.*</script>', new_js, text, flags=re.DOTALL)

# Add class to toggles and ids to arrows
text = re.sub(r'<a href="\?offset=\{\{ offset \}\}&mode=week".*?Semana</a>', 
              r'<a href="?offset={{ offset }}&mode=week" class="mode-toggle-btn" data-mode="week" style="padding: 6px 20px; border-radius: 16px; text-decoration: none; font-size: 0.85rem; font-weight: 600; color: {% if mode == \'week\' %}var(--bg-primary){% else %}var(--text-secondary){% endif %}; background: {% if mode == \'week\' %}var(--text-primary){% else %}transparent{% endif %}; transition: 0.2s;">Semana</a>', text)

text = re.sub(r'<a href="\?offset=\{\{ offset \}\}&mode=month".*?Mes</a>', 
              r'<a href="?offset={{ offset }}&mode=month" class="mode-toggle-btn" data-mode="month" style="padding: 6px 20px; border-radius: 16px; text-decoration: none; font-size: 0.85rem; font-weight: 600; color: {% if mode == \'month\' %}var(--bg-primary){% else %}var(--text-secondary){% endif %}; background: {% if mode == \'month\' %}var(--text-primary){% else %}transparent{% endif %}; transition: 0.2s;">Mes</a>', text)

text = text.replace('<a href="?offset={{ offset - 1 }}&mode={{ mode }}" class="week-nav-btn"', '<a id="nav_prev" href="?offset={{ offset - 1 }}&mode={{ mode }}" class="week-nav-btn"')
text = text.replace('<a href="?offset={{ offset + 1 }}&mode={{ mode }}" class="week-nav-btn"', '<a id="nav_next" href="?offset={{ offset + 1 }}&mode={{ mode }}" class="week-nav-btn"')

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/historial.html', 'w') as f:
    f.write(text)
