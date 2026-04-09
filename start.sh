#!/usr/bin/env bash
# VigIA - Iniciar servidor con auto-restart
cd "$(dirname "${BASH_SOURCE[0]}")"

# Liberar el puerto 8000 si está ocupado
PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PID" ]; then
  echo "Puerto 8000 ocupado (PID $PID) — cerrando..."
  kill "$PID" 2>/dev/null
  sleep 2
fi

source venv/bin/activate
export NNPACK_DISABLE=1  # Silencia advertencia de hardware no compatible
echo "Iniciando VigIA en http://localhost:8000/app ..."
echo "(Ctrl+C para detener)"
echo ""

# Auto-restart si el servidor se cae
while true; do
  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
  EXIT=$?
  if [ $EXIT -eq 0 ] || [ $EXIT -eq 130 ]; then
    # Salida normal (Ctrl+C) — no reiniciar
    break
  fi
  echo ""
  echo "Servidor caído (código $EXIT) — reiniciando en 3 segundos..."
  sleep 3
done
