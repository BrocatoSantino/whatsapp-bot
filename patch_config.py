import re

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/configuracion.html', 'r') as f:
    content = f.read()

# 1. Insert the UI block before business_shifts_input
ui_block = """
            <div style="margin-top: 3rem; margin-bottom: 1.5rem; border-top: 1px solid var(--border); padding-top: 2rem;">
                <h3 class="config-header" style="font-size: 1.1rem; margin-bottom: 1rem; border: none; padding: 0;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                    Horarios Específicos por Día
                </h3>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.5rem;">Definí horarios excepcionales. Lo que configures acá pisará al "Horario Habitual" para ese día.</p>
                
                <div class="form-group">
                    <select id="override_day_selector" class="form-input" style="max-width: 250px; margin-bottom: 1rem;" onchange="loadDayOverrides()">
                        <option value="">-- Seleccionar Día --</option>
                        <option value="0">Lunes</option>
                        <option value="1">Martes</option>
                        <option value="2">Miércoles</option>
                        <option value="3">Jueves</option>
                        <option value="4">Viernes</option>
                        <option value="5">Sábado</option>
                        <option value="6">Domingo</option>
                    </select>
                </div>

                <div id="overrideShiftsContainer" style="display: none; background: rgba(255,255,255,0.02); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border);">
                    <div id="day_shifts_list"></div>
                    <button type="button" class="btn-dashed" onclick="addOverrideShift()">+ Agregar Franja Horaria para este día</button>
                    <button type="button" class="btn-dashed" style="margin-top: 1rem; color: var(--danger); border-color: rgba(239, 68, 68, 0.3);" onclick="clearOverrideDay()">Eliminar excepciones de este día</button>
                </div>
            </div>
            
            <input type="hidden" name="day_overrides" id="day_overrides_input">
            <input type="hidden" name="business_shifts" id="business_shifts_input">
"""

content = content.replace('<input type="hidden" name="business_shifts" id="business_shifts_input">', ui_block)

# 2. Add Javascript logic
js_block = """
    // Day Overrides Logic
    let dayOverrides = {{ day_overrides | tojson | safe }};
    
    function loadDayOverrides() {
        const dayStr = document.getElementById('override_day_selector').value;
        const container = document.getElementById('overrideShiftsContainer');
        const list = document.getElementById('day_shifts_list');
        
        if (!dayStr) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        list.innerHTML = ''; // Clear current
        
        const shifts = dayOverrides[dayStr] || [];
        shifts.forEach(shift => {
            const div = document.createElement('div');
            div.className = 'shift-row override-shift-row';
            div.innerHTML = `
                <div style="flex: 1;">
                    <label class="form-label form-label-sm">Inicio</label>
                    <input type="time" class="shift-start form-input" value="${shift.start}" required onchange="saveCurrentOverrides()">
                </div>
                <div style="flex: 1;">
                    <label class="form-label form-label-sm">Fin</label>
                    <input type="time" class="shift-end form-input" value="${shift.end}" required onchange="saveCurrentOverrides()">
                </div>
                <button type="button" class="shift-delete-btn" onclick="this.parentElement.remove(); saveCurrentOverrides()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            `;
            list.appendChild(div);
        });
    }

    function addOverrideShift() {
        const list = document.getElementById('day_shifts_list');
        const div = document.createElement('div');
        div.className = 'shift-row override-shift-row';
        div.innerHTML = `
            <div style="flex: 1;">
                <label class="form-label form-label-sm">Inicio</label>
                <input type="time" class="shift-start form-input" value="09:00" required onchange="saveCurrentOverrides()">
            </div>
            <div style="flex: 1;">
                <label class="form-label form-label-sm">Fin</label>
                <input type="time" class="shift-end form-input" value="13:00" required onchange="saveCurrentOverrides()">
            </div>
            <button type="button" class="shift-delete-btn" onclick="this.parentElement.remove(); saveCurrentOverrides()">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;
        list.appendChild(div);
        saveCurrentOverrides();
    }
    
    function clearOverrideDay() {
        const dayStr = document.getElementById('override_day_selector').value;
        if(dayStr) {
            delete dayOverrides[dayStr];
            loadDayOverrides();
        }
    }

    function saveCurrentOverrides() {
        const dayStr = document.getElementById('override_day_selector').value;
        if (!dayStr) return;
        
        const shifts = [];
        document.querySelectorAll('#day_shifts_list .override-shift-row').forEach(row => {
            const start = row.querySelector('.shift-start').value;
            const end = row.querySelector('.shift-end').value;
            if (start && end) {
                shifts.push({ start, end });
            }
        });
        dayOverrides[dayStr] = shifts;
    }

    function submitHorarios() {
        // Collect working days
        const days = [];
        document.querySelectorAll('.working-day-cb:checked').forEach(cb => {
            days.push(parseInt(cb.value));
        });
        document.getElementById('working_days_input').value = JSON.stringify(days);
        
        // Collect regular shifts
        const shifts = [];
        // Only get the normal shift rows, not the override ones
        document.querySelectorAll('#shiftsContainer .shift-row').forEach(row => {
            const start = row.querySelector('.shift-start').value;
            const end = row.querySelector('.shift-end').value;
            if (start && end) {
                shifts.push({ start, end });
            }
        });
        document.getElementById('business_shifts_input').value = JSON.stringify(shifts);
        
        // Ensure overrides are saved
        if(document.getElementById('override_day_selector').value) {
            saveCurrentOverrides();
        }
        document.getElementById('day_overrides_input').value = JSON.stringify(dayOverrides);
        
        document.getElementById('horariosForm').submit();
    }
"""

content = re.sub(r'function submitHorarios\(\) \{.*\}', js_block, content, flags=re.DOTALL)

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/templates/configuracion.html', 'w') as f:
    f.write(content)

