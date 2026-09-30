import re

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/historial.html', 'r') as f:
    content = f.read()

new_script = """
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('weeklyChart').getContext('2d');
    
    const dailyCounts = {{ daily_counts | tojson }};
    const dailyDates = {{ daily_dates | safe }};
    const isMonth = "{{ mode }}" === "month";
    
    let labels = [];
    if (isMonth) {
        labels = dailyDates;
    } else {
        const days = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
        // Strava just shows the day or date. We can show both or just the day to make it clean.
        labels = days; 
    }

    const isLight = document.documentElement.classList.contains('light-mode');
    const textColor = isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)';
    const gridColor = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.05)';
    const brandColor = '#fc4c02'; // Naranja Turnoflow

    // Gradient below the line
    let gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(252, 76, 2, 0.4)'); // Transparente arriba
    gradient.addColorStop(1, 'rgba(252, 76, 2, 0.0)'); // Transparente abajo

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cortes',
                data: dailyCounts,
                backgroundColor: gradient,
                borderColor: brandColor,
                borderWidth: 2,
                pointBackgroundColor: '#fff',
                pointBorderColor: brandColor,
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.1 // Ligeramente curvo pero bastante recto como strava
            }]
        },
        options: {
            layout: {
                padding: { left: 10, right: 10, top: 20, bottom: 0 }
            },
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
                        label: function(context) {
                            return context.raw === 1 ? '1 corte' : context.raw + ' cortes';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1, 
                        color: textColor,
                        font: { size: 11, family: "'Inter', sans-serif" }
                    },
                    grid: {
                        color: gridColor,
                        drawBorder: false
                    }
                },
                x: {
                    ticks: {
                        color: textColor,
                        autoSkip: false,
                        maxRotation: 0,
                        font: { size: 10, family: "'Inter', sans-serif", weight: '500' },
                        padding: 10
                    },
                    grid: {
                        display: true,
                        color: gridColor,
                        drawBorder: false,
                        tickLength: 0
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index',
            },
        }
    });
});
</script>
"""

content = re.sub(r'<script src="https://cdn\.jsdelivr\.net/npm/chart\.js"></script>.*?</script>', new_script, content, flags=re.DOTALL)

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/historial.html', 'w') as f:
    f.write(content)
