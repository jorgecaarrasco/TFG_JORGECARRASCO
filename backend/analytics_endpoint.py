# =============================================================================
# ENDPOINTS API - ANALYTICS DASHBOARD
# =============================================================================

@app.route('/api/analytics/dashboard', methods=['GET'])
@login_required
def get_analytics_dashboard():
    """
    Endpoint consolidado para el dashboard de analytics.
    Devuelve todos los datos necesarios para renderizar los gráficos detallados.
    """
    try:
        # Obtener filtros
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento', 'todos')
        
        if not mysql_db:
            return jsonify({'success': False, 'error': 'BD no disponible'}), 503
        
        # Obtener todas las incidencias con los filtros
        incidencias = mysql_db.exportar_incidencias_csv(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento if departamento != 'todos' else None
        )
        
        logging.info(f"📊 Dashboard Analytics: {len(incidencias)} incidencias encontradas para el rango {fecha_inicio} a {fecha_fin}")
        
        # Calcular métricas generales
        total_incidencias = len(incidencias)
        resueltas = sum(1 for i in incidencias if i.get('estado') == 'resuelta')
        en_proceso = sum(1 for i in incidencias if i.get('estado') == 'en_proceso')
        pendientes = sum(1 for i in incidencias if i.get('estado') == 'pendiente')
        pausadas = sum(1 for i in incidencias if i.get('estado') == 'pausada')
        
        # Tiempo promedio de resolución
        tiempos_resueltas = [i.get('minutos_total', 0) for i in incidencias if i.get('estado') == 'resuelta' and i.get('minutos_total')]
        tiempo_promedio_mins = sum(tiempos_resueltas) / len(tiempos_resueltas) if tiempos_resueltas else 0
        tiempo_promedio_horas = tiempo_promedio_mins / 60.0
        
        #TIMELINE - Incidencias por período (últimos 30 días)
        from datetime import datetime, timedelta
        timeline_data = {}
        for inc in incidencias:
            fecha_str = inc.get('fecha_creacion', '')[:10]  # Solo la fecha (YYYY-MM-DD)
            timeline_data[fecha_str] = timeline_data.get(fecha_str, 0) + 1
        
        timeline_labels = sorted(timeline_data.keys())[-30:]  # Últimos 30 días
        timeline_values = [timeline_data[fecha] for fecha in timeline_labels]
        
        # CATEGORÍAS - Distribución por tipo
        categorias_data = {}
        for inc in incidencias:
            cat = inc.get('categoria', 'Sin categoría')
            categorias_data[cat] = categorias_data.get(cat, 0) + 1
        
        categorias_labels = list(categorias_data.keys())
        categorias_values = list(categorias_data.values())
        
        # DEPARTAMENTOS - Distribución por departamento
        dept_data = {}
        for inc in incidencias:
            dept = inc.get('departamento', 'Sin dept').upper()
            dept_data[dept] = dept_data.get(dept, 0) + 1
        
        dept_labels = list(dept_data.keys())
        dept_values = list(dept_data.values())
        
        # TIEMPOS PROMEDIO - Por categoría
        tiempo_por_cat = {}
        count_por_cat = {}
        for inc in incidencias:
            cat = inc.get('categoria', 'Sin categoría')
            mins = inc.get('minutos_total', 0) or 0
            if mins > 0:
                tiempo_por_cat[cat] = tiempo_por_cat.get(cat, 0) + mins
                count_por_cat[cat] = count_por_cat.get(cat, 0) + 1
        
        tiempo_labels = []
        tiempo_values = []
        for cat, total_mins in tiempo_por_cat.items():
            count = count_por_cat[cat]
            promedio = total_mins / count if count > 0 else 0
            tiempo_labels.append(cat)
            tiempo_values.append(round(promedio, 1))
        
        # TOP REPORTAN - Usuarios que más reportan
        reportan_data = {}
        for inc in incidencias:
            usuario = inc.get('reportado_por', 'Desconocido')
            reportan_data[usuario] = reportan_data.get(usuario, 0) + 1
        
        top_reportan = sorted(reportan_data.items(), key=lambda x: x[1], reverse=True)[:5]
        reportan_labels = [u[0] for u in top_reportan]
        reportan_values = [u[1] for u in top_reportan]
        
        # TOP RESUELVEN - Técnicos que más resuelven
        resuelven_data = {}
        for inc in incidencias:
            if inc.get('estado') == 'resuelta':
                tecnico = inc.get('resuelto_por', 'Sin asignar')
                if tecnico:
                    resuelven_data[tecnico] = resuelven_data.get(tecnico, 0) + 1
        
        top_resuelven = sorted(resuelven_data.items(), key=lambda x: x[1], reverse=True)[:5]
        resuelven_labels = [t[0] for t in top_resuelven]
        resuelven_values = [t[1] for t in top_resuelven]
        
        # HORAS PICO - Distribución por hora del día
        horas_data = {h: 0 for h in range(24)}
        for inc in incidencias:
            fecha_str = inc.get('fecha_creacion', '')
            if len(fecha_str) >= 13:  # YYYY-MM-DD HH:MM
                try:
                    hora = int(fecha_str[11:13])
                    horas_data[hora] = horas_data.get(hora, 0) + 1
                except:
                    pass
        
        horas_labels = [f"{h}:00" for h in range(24)]
        horas_values = [horas_data[h] for h in range(24)]
        
        # PUESTOS PROBLEMÁTICOS - Top 5 puestos con más incidencias
        puestos_data = {}
        for inc in incidencias:
            dept = inc.get('departamento', '').upper()
            puesto = inc.get('puesto', '')
            puesto_completo = f"{dept}-{puesto}"
            puestos_data[puesto_completo] = puestos_data.get(puesto_completo, 0) + 1
        
        top_puestos = sorted(puestos_data.items(), key=lambda x: x[1], reverse=True)[:5]
        puestos_labels = [p[0] for p in top_puestos]
        puestos_values = [p[1] for p in top_puestos]
        
        # Construir respuesta compatible con el frontend
        stats = {
            'metricasGenerales': {
                'totalIncidencias': total_incidencias,
                'resueltas': resueltas,
                'enProceso': en_proceso,
                'pendientes': pendientes,
                'pausadas': pausadas,
                'tiempoPromedioResolucionHoras': round(tiempo_promedio_horas, 1)
            },
            'incidenciasPorPeriodo': {
                'labels': timeline_labels,
                'data': timeline_values
            },
            'distribucionCategorias': {
                'labels': categorias_labels,
                'data': categorias_values
            },
            'departamentos': {
                'labels': dept_labels,
                'data': dept_values
            },
            'tiempoResolucion': {
                'labels': tiempo_labels,
                'data': tiempo_values
            },
            'usuariosReportan': {
                'labels': reportan_labels,
                'data': reportan_values
            },
            'usuariosResuelven': {
                'labels': resuelven_labels,
                'data': resuelven_values
            },
            'horasPico': {
                'labels': horas_labels,
                'data': horas_values
            },
            'puestosProblematicos': {
                'labels': puestos_labels,
                'data': puestos_values
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'total_incidencias': total_incidencias
        })
        
    except Exception as e:
        logging.error(f"❌ Error en analytics dashboard: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
