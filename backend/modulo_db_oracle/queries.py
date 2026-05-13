"""
=============================================================================
QUERIES ORACLE - SISTEMA DE CONTROL DE MESAS
=============================================================================
Archivo centralizado con todas las queries SQL para Oracle Database.
Este archivo NO contiene credenciales ni datos sensibles.
=============================================================================
"""

# =============================================================================
# QUERIES PARA PACKING
# =============================================================================

QUERY_PACKING_CON_NOMBRE = """
    SELECT 
        emliem as "puesto", 
        utluti as "nombre", 
        ptcdor as "usuario", 
        to_char(PTSTRT, 'HH24:MI') as "fecha_inicio"
    FROM (
        SELECT 
            utluti, 
            hlemplp.emliem, 
            mhpactp.ptcdor, 
            mhpactp.ptstrt,
            row_number() over (partition by mhpactp.ptcdor order by mhpactp.ptstrt desc) as rn
        FROM mhpactp 
        JOIN mhbdelp ON BDRDOO = PTRORD
        JOIN hlemplp ON EMNEMP = PTPKLO
        JOIN hlutilp ON UTCUTI = PTCDOR 
        WHERE mhpactp.ptstrt >= SYSDATE - (5/1440) 
        AND (UTCGPG NOT LIKE 'IMBALLO%' AND UTCGPG NOT LIKE 'RIC_TEMP' AND SUBSTR(UTCUTI, 1, 1) NOT IN ('1','2','3','4'))
    ) sub
    WHERE rn = 1
"""

QUERY_PACKING_SIN_NOMBRE = """
    SELECT 
        emliem as "puesto",  
        ptcdor as "usuario", 
        to_char(PTSTRT, 'HH24:MI:SS') as "fecha_inicio"
    FROM (
        SELECT 
            hlemplp.emliem, 
            mhpactp.ptcdor, 
            mhpactp.ptstrt,
            row_number() over (partition by mhpactp.ptcdor order by mhpactp.ptstrt desc) as rn
        FROM mhpactp 
        JOIN mhbdelp ON BDRDOO = PTRORD
        JOIN hlemplp ON EMNEMP = PTPKLO
        WHERE mhpactp.ptstrt >= SYSDATE - (5/1440)
    ) sub
    WHERE rn = 1
"""

# =============================================================================
# QUERIES PARA RETURN
# =============================================================================

QUERY_RETURN_CON_NOMBRE = """
    SELECT 
        rn.puesto as PUESTO, 
        rn.nombre as NOMBRE,
        rn.usuario as USUARIO,
        substr(max(rn.hora_raw),0,2) || ':' || substr(max(rn.hora_raw),3,2) as "FECHA_INICIO" 
    FROM (  
        SELECT 
            MROREC AS usuario,
            MRHCRR AS hora_raw,
            DRNEMP,
            RENEMP, 
            UTLUTI as nombre,
            NVL(
                (SELECT EMLIEM FROM HLEMPLP WHERE EMCDPO = 008 AND DRNEMP = EMNEMP),
                (SELECT EMLIEM FROM HLEMPLP WHERE EMCDPO = 008 AND RENEMP = EMNEMP)
            ) AS puesto
        FROM MHRECDP 
        LEFT OUTER JOIN HLRECDP ON DRNANN || DRNREC = MRNANN || MRNREC AND DRNSUP = MRCNUR
        JOIN HLRECPP ON RENANN || RENREC = MRNANN || MRNREC AND RERREC = MRPO
        JOIN hlutilp ON UTCUTI = MROREC
        WHERE (UTCGPG NOT LIKE 'IMBALLO%' AND UTCGPG NOT LIKE 'RIC_TEMP' AND SUBSTR(UTCUTI, 1, 1) NOT IN ('1','2','3','4'))
        AND substr(MRHCRR+1000000,2,6) > TO_CHAR(sysdate - (5/1440),'HH24miss') 
        AND mrdrec LIKE TO_CHAR(sysdate,'yyyymmdd')                
    ) rn
    GROUP BY rn.puesto, rn.usuario, rn.nombre
    ORDER BY 1
"""

QUERY_RETURN_SIN_NOMBRE = """
    SELECT 
        rn.puesto as PUESTO,
        rn.usuario as USUARIO,
        substr(max(rn.hora_raw),0,2) || ':' || substr(max(rn.hora_raw),3,2) as "FECHA_INICIO"  
    FROM (  
        SELECT 
            MROREC AS usuario,
            MRHCRR AS hora_raw,
            DRNEMP,
            RENEMP,
            NVL(
                (SELECT EMLIEM FROM HLEMPLP WHERE EMCDPO = 008 AND DRNEMP = EMNEMP),
                (SELECT EMLIEM FROM HLEMPLP WHERE EMCDPO = 008 AND RENEMP = EMNEMP)
            ) AS puesto
        FROM MHRECDP 
        LEFT OUTER JOIN HLRECDP ON DRNANN || DRNREC = MRNANN || MRNREC AND DRNSUP = MRCNUR
        JOIN HLRECPP ON RENANN || RENREC = MRNANN || MRNREC AND RERREC = MRPO
        WHERE substr(MRHCRR+1000000,2,6) > TO_CHAR(sysdate - (5/1440),'HH24miss') 
        AND mrdrec LIKE TO_CHAR(sysdate,'yyyymmdd')
    ) rn
    GROUP BY rn.usuario, rn.puesto
    ORDER BY 3
"""

# =============================================================================
# QUERIES PARA VAS
# =============================================================================

QUERY_VAS_CON_NOMBRE = """
    select EMLIEM "PUESTO",vaoper "CODIGO",UTLUTI "NOMBRE",to_char(max(vatime),'HH24:MI:SS') "FECHA"
from mhvasep
JOIN HLMVTGP ON (VGNSUP=VAHDSP AND VGCART=VANSKU)
JOIN HLUTILP ON (VAOPER=UTCUTI)
JOIN HLSUPPP ON (SUNSUP=VGNSUP)
JOIN HLEMPLP ON (EMNEMP=SUNEMP)
WHERE VATIME >= SYSDATE - (3/1440)
group by vaoper,EMLIEM,UTLUTI
ORDER BY 3 DESC
"""

QUERY_VAS_SIN_NOMBRE = """
    select EMLIEM "PUESTO",vaoper "USUARIO",to_char(max(vatime),'HH24:MI:SS') "FECHA INICIO"
from mhvasep
JOIN HLMVTGP ON (VGNSUP=VAHDSP AND VGCART=VANSKU)
JOIN HLUTILP ON (VAOPER=UTCUTI)
JOIN HLSUPPP ON (SUNSUP=VGNSUP)
JOIN HLEMPLP ON (EMNEMP=SUNEMP)
WHERE VATIME >= SYSDATE - (30/1440)
group by vaoper,EMLIEM
ORDER BY 3 DESC
"""

# =============================================================================
# DICCIONARIO DE QUERIES POR MÓDULO
# =============================================================================

QUERIES = {
    'packing': {
        'con_nombre': QUERY_PACKING_CON_NOMBRE,
        'sin_nombre': QUERY_PACKING_SIN_NOMBRE
    },
    'return': {
        'con_nombre': QUERY_RETURN_CON_NOMBRE,
        'sin_nombre': QUERY_RETURN_SIN_NOMBRE
    },
    'vas': {
        'con_nombre': QUERY_VAS_CON_NOMBRE,
        'sin_nombre': QUERY_VAS_SIN_NOMBRE
    }
}


def get_query(modulo: str, con_nombre: bool = True) -> str:
    """
    Obtiene la query correspondiente para un módulo.
    
    Args:
        modulo (str): 'packing', 'return' o 'vas'
        con_nombre (bool): Si True, devuelve la query que incluye el nombre del operario
        
    Returns:
        str: La query SQL correspondiente
    """
    tipo = 'con_nombre' if con_nombre else 'sin_nombre'
    
    if modulo not in QUERIES:
        raise ValueError(f"Módulo desconocido: {modulo}. Debe ser 'packing', 'return' o 'vas'")
    
    return QUERIES[modulo][tipo]
