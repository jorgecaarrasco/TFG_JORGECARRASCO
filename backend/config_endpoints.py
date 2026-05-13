# =============================================================================
# ENDPOINTS API - CONFIGURACIONES (IT_ADMIN ONLY)
# =============================================================================

@app.route('/api/config/rfid/reboot-masivo', methods=['POST'])
@login_required
def reboot_rfid_masivo():
    """Reiniciar RFIDs masivamente (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        
        total = 0
        exitosos = 0
        fallidos = 0
        
        # Determinar qué departamentos procesar
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            if dept not in rfid_config:
                continue
                
            for puesto in range(desde, hasta + 1):
                if puesto in rfid_config[dept]:
                    total += 1
                    rfid_ip = rfid_config[dept][puesto]
                    success, mensaje = ejecutar_ssh_reboot(rfid_ip, RFID_SSH_PASSWORD)
                    
                    if success:
                        exitosos += 1
                        logging.info(f"✅ RFID reiniciado masivamente: {dept.upper()}-{puesto} ({rfid_ip})")
                    else:
                        fallidos += 1
                        logging.warning(f"⚠️ Fallo reinicio masivo: {dept.upper()}-{puesto} ({rfid_ip}): {mensaje}")
        
        logging.info(f"📊 Reinicio masivo RFID completado por {user['username']}: {exitosos}/{total} exitosos")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos,
            'fallidos': fallidos
        })
        
    except Exception as e:
        logging.error(f"❌ Error en reinicio masivo RFID: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/aplicar-masivo', methods=['POST'])
@login_required
def aplicar_config_zebra_masivo():
    """Aplicar configuración masiva a impresoras Zebra (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        darkness = data.get('darkness')
        left_position = data.get('left_position')
        top_position = data.get('top_position')
        locked = data.get('locked', False)
        
        total = 0
        exitosos = 0
        fallidos = 0
        
        # Determinar qué departamentos procesar
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            for puesto in range(desde, hasta + 1):
                total += 1
                
                # Actualizar en base de datos
                success = mysql_db.actualizar_configuracion_zebra(
                    departamento=dept,
                    puesto=puesto,
                    darkness_custom=darkness,
                    left_position=left_position,
                    top_position=top_position,
                    custom_locked=locked
                )
                
                if success:
                    exitosos += 1
                    logging.info(f"✅ Zebra configurada: {dept.upper()}-{puesto} (darkness={darkness}, left={left_position}, locked={locked})")
                else:
                    fallidos += 1
        
        logging.info(f"📊 Configuración masiva Zebra por {user['username']}: {exitosos}/{total} exitosos")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos,
            'fallidos': fallidos
        })
        
    except Exception as e:
        logging.error(f"❌ Error aplicando configuración masiva Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/restaurar-defaults', methods=['POST'])
@login_required
def restaurar_defaults_zebra():
    """Restaurar configuración predeterminada de Zebras (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        
        total = 0
        exitosos = 0
        
        # Determinar qué departamentos procesar
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            # Definir valores predeterminados según departamento
            left_default = 0 if dept == 'packing' else -215
            
            for puesto in range(desde, hasta + 1):
                total += 1
                
                # Restaurar a valores predeterminados y desbloquear
                success = mysql_db.actualizar_configuracion_zebra(
                    departamento=dept,
                    puesto=puesto,
                    darkness_custom=None,  # Usar default (5)
                    left_position=left_default,
                    top_position=0,
                    custom_locked=False  # Desbloquear
                )
                
                if success:
                    exitosos += 1
                    logging.info(f"✅ Zebra restaurada a defaults: {dept.upper()}-{puesto}")
        
        logging.info(f"📊 Restauración defaults Zebra por {user['username']}: {exitosos}/{total}")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos
        })
        
    except Exception as e:
        logging.error(f"❌ Error restaurando defaults Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/verificar', methods=['GET'])
@login_required
def verificar_config_zebra():
    """Verificar configuraciones de impresoras Zebra (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        departamento = request.args.get('departamento')
        desde = request.args.get('desde', type=int)
        hasta = request.args.get('hasta', type=int)
        
        # Obtener todas las impresoras o filtradas
        impresoras = mysql_db.get_zebras_configuracion(
            departamento=departamento,
            puesto_desde=desde,
            puesto_hasta=hasta
        )
        
        total = len(impresoras)
        correctas = 0
        modificadas = 0
        bloqueadas = 0
        issues = []
        
        for imp in impresoras:
            es_correcta = True
            dept = imp['departamento']
            puesto = imp['puesto']
            
            # Verificar contraste (debe ser 5 o null para usar default)
            darkness = imp.get('darkness_custom')
            if darkness and darkness != 5:
                modificadas += 1
                es_correcta = False
                issues.append({
                    'puesto': f"{dept.upper()}-{puesto}",
                    'problema': f"Contraste personalizado: {darkness}"
                })
            
            # Verificar posición izquierda
            left = imp.get('left_position')
            expected_left = 0 if dept == 'packing' else -215
            if left and left != expected_left:
                if es_correcta:
                    modificadas += 1
                    es_correcta = False
                issues.append({
                    'puesto': f"{dept.upper()}-{puesto}",
                    'problema': f"Posición izq.: {left} (esperado: {expected_left})"
                })
            
            # Contar bloqueadas
            if imp.get('custom_locked'):
                bloqueadas += 1
            
            if es_correcta:
                correctas += 1
        
        return jsonify({
            'success': True,
            'total': total,
            'correctas': correctas,
            'modificadas': modificadas,
            'bloqueadas': bloqueadas,
            'issues': issues
        })
        
    except Exception as e:
        logging.error(f"❌ Error verificando configuraciones Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
