# Diagnóstico puntual de saturación de conexiones en appsheet_db (solo lectura).
# Uso: python _diag_mysql.py — borrar después de usar.
import tomllib
from datetime import datetime
from zoneinfo import ZoneInfo

import pymysql

with open(".streamlit/secrets.toml", "rb") as f:
    cfg = tomllib.load(f)["mysql"]

try:
    conn = pymysql.connect(
        host=cfg["host"], port=int(cfg.get("port", 3306)),
        database=cfg["database"], user=cfg["user"], password=cfg["password"],
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
    )
except pymysql.MySQLError as e:
    print(f"NO CONECTA: {e}")
    raise SystemExit(1)

with conn.cursor() as cur:
    cur.execute("SHOW STATUS LIKE 'Threads_connected'")
    print("Conexiones actuales:", cur.fetchone()["Value"])
    cur.execute("SHOW VARIABLES LIKE 'max_connections'")
    print("Límite max_connections:", cur.fetchone()["Value"])
    hoy = datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) AS n FROM VistaMonitor WHERE Fecha = %s", (hoy,))
    print(f"Filas VistaMonitor hoy ({hoy}):", cur.fetchone()["n"])
    # Quién ocupa los slots (agrupado por usuario y host, sin queries)
    try:
        cur.execute(
            "SELECT USER AS usuario, SUBSTRING_INDEX(HOST, ':', 1) AS host_origen, "
            "COUNT(*) AS conexiones, SUM(COMMAND = 'Sleep') AS dormidas, "
            "MAX(TIME) AS seg_max "
            "FROM information_schema.PROCESSLIST "
            "GROUP BY usuario, host_origen ORDER BY conexiones DESC"
        )
        print("\nConexiones por usuario/host (dormidas = idle):")
        for r in cur.fetchall():
            print(f"  {r['usuario']:<22} {r['host_origen']:<18} "
                  f"{r['conexiones']:>3} conexiones · {r['dormidas']} dormidas · "
                  f"max {r['seg_max']}s")
    except pymysql.MySQLError as e:
        print(f"(sin permiso PROCESS para ver el processlist: {e})")

conn.close()
