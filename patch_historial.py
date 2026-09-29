import re

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/router.py', 'r') as f:
    content = f.read()

# Define the new function
new_function = """@router.get("/admin/historial", response_class=HTMLResponse)
async def historial(
    request: Request,
    offset: int = 0,
    mode: str = 'week',
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)

    ar_tz = timezone(timedelta(hours=-3))
    now = datetime.now(ar_tz).date()

    import calendar
    if mode == 'month':
        target_month = now.month + offset
        target_year = now.year
        while target_month > 12:
            target_month -= 12
            target_year += 1
        while target_month < 1:
            target_month += 12
            target_year -= 1

        start_date = date(target_year, target_month, 1)
        _, last_day = calendar.monthrange(target_year, target_month)
        end_date = date(target_year, target_month, last_day)

        daily_counts = [0] * last_day
        daily_dates = [str(i) for i in range(1, last_day + 1)]
        range_str = f"{MESES[target_month-1]} {target_year}"
    else:
        start_date = now - timedelta(days=now.weekday()) + timedelta(weeks=offset)
        end_date = start_date + timedelta(days=6)

        daily_counts = [0] * 7
        daily_dates = [(start_date + timedelta(days=i)).strftime('%d/%m') for i in range(7)]
        range_str = f"{start_date.day} {MESES[start_date.month-1][:3]} - {end_date.day} {MESES[end_date.month-1][:3]}"

    if os.getenv("MOCK_DATA") == "True":
        appointments = get_mock_appointments(tenant.id, start_date=start_date, end_date=end_date)
    else:
        appointments = db.query(Appointment).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.date >= start_date,
            Appointment.date <= end_date
        ).all()

    total_revenue = 0
    total_minutes = 0
    completed_cuts = 0
    recent_completed_cuts = []

    for app in appointments:
        if app.status == 'completed':
            completed_cuts += 1
            recent_completed_cuts.append(app)
            if app.service:
                total_revenue += app.service.price
                total_minutes += app.service.duration_minutes

            day_index = (app.date - start_date).days
            if mode == 'month':
                if 0 <= day_index < last_day:
                    daily_counts[day_index] += 1
            else:
                if 0 <= day_index <= 6:
                    daily_counts[day_index] += 1

    recent_completed_cuts.sort(key=lambda x: (x.date, x.time), reverse=True)
    recent_completed_cuts = recent_completed_cuts[:5]

    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0 and mins > 0:
        time_str = f"{hours}h {mins}m"
    elif hours > 0:
        time_str = f"{hours}h"
    else:
        time_str = f"{mins}m"

    return templates.TemplateResponse(
        request=request,
        name="historial.html",
        context={
            "business_name": tenant.name,
            "appointments": appointments,
            "total_revenue": total_revenue,
            "completed_cuts": completed_cuts,
            "time_str": time_str,
            "daily_counts": json.dumps(daily_counts),
            "daily_dates": json.dumps(daily_dates),
            "range_str": range_str,
            "offset": offset,
            "mode": mode,
            "disable_next": offset >= 0,
            "recent_completed_cuts": recent_completed_cuts
        }
    )"""

pattern = re.compile(r'@router\.get\("/admin/historial", response_class=HTMLResponse\).*?return templates\.TemplateResponse\([^)]+\)', re.DOTALL)
new_content = pattern.sub(new_function, content)

with open('/home/arkadain/proyectos/whatsapp-peluqueria/app/admin/router.py', 'w') as f:
    f.write(new_content)
