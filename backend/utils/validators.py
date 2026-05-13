"""
Módulo de validación de entrada para endpoints API
"""

import re
from typing import Dict, List, Optional, Tuple


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Valida un nombre de usuario.
    
    Args:
        username: Nombre de usuario a validar
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    if not username:
        return False, "El nombre de usuario es requerido"
    
    if len(username) < 3:
        return False, "El nombre de usuario debe tener al menos 3 caracteres"
    
    if len(username) > 50:
        return False, "El nombre de usuario no puede exceder 50 caracteres"
    
    # Solo letras, números, guiones y guiones bajos
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "El nombre de usuario solo puede contener letras, números, guiones y guiones bajos"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Valida una contraseña.
    
    Args:
        password: Contraseña a validar
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    if not password:
        return False, "La contraseña es requerida"
    
    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres"
    
    if len(password) > 128:
        return False, "La contraseña no puede exceder 128 caracteres"
    
    return True, None


def validate_ip(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Valida una dirección IP.
    
    Args:
        ip: Dirección IP a validar
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    if not ip:
        return False, "La dirección IP es requerida"
    
    # Patrón básico de IPv4
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False, "Formato de IP inválido"
    
    # Verificar que cada octeto esté en rango válido
    parts = ip.split('.')
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False, "Cada octeto de la IP debe estar entre 0 y 255"
        except ValueError:
            return False, "La IP contiene valores no numéricos"
    
    return True, None


def validate_departamento(departamento: str) -> Tuple[bool, Optional[str]]:
    """
    Valida un nombre de departamento.
    
    Args:
        departamento: Nombre del departamento
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    if not departamento:
        return False, "El departamento es requerido"
    
    departamentos_validos = ['packing', 'return', 'vas', 'todos']
    if departamento.lower() not in departamentos_validos:
        return False, f"Departamento inválido. Debe ser uno de: {', '.join(departamentos_validos)}"
    
    return True, None


def validate_puesto(puesto: int, min_val: int = 1, max_val: int = 200) -> Tuple[bool, Optional[str]]:
    """
    Valida un número de puesto.
    
    Args:
        puesto: Número de puesto
        min_val: Valor mínimo permitido
        max_val: Valor máximo permitido
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    if puesto is None:
        return False, "El puesto es requerido"
    
    try:
        puesto_int = int(puesto)
        if puesto_int < min_val or puesto_int > max_val:
            return False, f"El puesto debe estar entre {min_val} y {max_val}"
        return True, None
    except (ValueError, TypeError):
        return False, "El puesto debe ser un número válido"


def validate_incidencia_data(data: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Valida los datos de una incidencia.
    
    Args:
        data: Diccionario con datos de la incidencia
        
    Returns:
        Tuple[bool, Optional[str], Optional[Dict]]: (es_válido, mensaje_error, datos_validados)
    """
    # Limpiar puesto si viene como string (ej: PACK-12 -> 12)
    if 'puesto' in data and isinstance(data['puesto'], str):
        import re
        # Extraer solo dígitos
        digits = re.findall(r'\d+', data['puesto'])
        if digits:
            data['puesto'] = int(digits[-1])  # Usar el último grupo de dígitos (ej: RET-12 -> 12)

    # Campos requeridos
    required_fields = ['departamento', 'puesto', 'categoria']
    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"El campo '{field}' es requerido", None
    
    # Validar departamento
    dept_valid, dept_error = validate_departamento(data['departamento'])
    if not dept_valid:
        return False, dept_error, None
    
    # Validar puesto
    puesto_valid, puesto_error = validate_puesto(data['puesto'])
    if not puesto_valid:
        return False, puesto_error, None
    
    # Validar categoría
    if not isinstance(data['categoria'], str) or len(data['categoria']) < 1:
        return False, "La categoría es requerida", None
    
    # ✅ Normalizar prioridad (hacerla más flexible para evitar errores)
    prioridades_validas = ['alta', 'media', 'baja']
    # Obtener prioridad, limpiar espacios y pasar a minúsculas
    prioridad_raw = str(data.get('prioridad', 'media')).strip().lower()
    
    # Si la prioridad está vacía o no es válida, usar 'media' por defecto
    if not prioridad_raw or prioridad_raw not in prioridades_validas:
        import logging
        logging.warning(f"⚠️ Prioridad recibida '{prioridad_raw}' no válida. Usando 'media' por defecto.")
        prioridad_final = 'media'
    else:
        prioridad_final = prioridad_raw
    
    # Validar descripción (opcional pero si está presente debe tener límite)
    if 'descripcion' in data and data['descripcion']:
        if len(data['descripcion']) > 2000:
            return False, "La descripción no puede exceder 2000 caracteres", None
    
    # Preparar datos validados
    validated_data = {
        'departamento': data['departamento'].lower(),
        'puesto': int(data['puesto']),
        'categoria': data['categoria'].strip(),
        'prioridad': prioridad_final,
        'descripcion': data.get('descripcion', '').strip()[:2000]
    }
    
    return True, None, validated_data


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Sanitiza una cadena de texto removiendo caracteres peligrosos.
    
    Args:
        value: Cadena a sanitizar
        max_length: Longitud máxima permitida
        
    Returns:
        str: Cadena sanitizada
    """
    if not isinstance(value, str):
        return str(value)[:max_length]
    
    # Remover caracteres de control y espacios al inicio/final
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    sanitized = sanitized.strip()[:max_length]
    
    return sanitized


def validate_range(desde: int, hasta: int, min_val: int = 1, max_val: int = 200) -> Tuple[bool, Optional[str]]:
    """
    Valida un rango de valores.
    
    Args:
        desde: Valor inicial del rango
        hasta: Valor final del rango
        min_val: Valor mínimo permitido
        max_val: Valor máximo permitido
        
    Returns:
        Tuple[bool, Optional[str]]: (es_válido, mensaje_error)
    """
    try:
        desde_int = int(desde)
        hasta_int = int(hasta)
        
        if desde_int < min_val or hasta_int > max_val:
            return False, f"Los valores deben estar entre {min_val} y {max_val}"
        
        if desde_int > hasta_int:
            return False, "El valor 'desde' no puede ser mayor que 'hasta'"
        
        if hasta_int - desde_int > 100:
            return False, "El rango no puede exceder 100 puestos"
        
        return True, None
    except (ValueError, TypeError):
        return False, "Los valores deben ser números válidos"




