@echo off
title EEA-2026 DIGITAL EXOSKELETON [GUARDIAN MODE]
color 0A
echo ===================================================
echo    SISTEMA GUARDIAN INICIADO - MONITOREO ACTIVO
echo ===================================================
echo.

:loop
echo [GUARDIAN] Levantando el nucleo del Orquestador...
:: Forzamos el uso del entorno Python global para evitar problemas
python core/app_orchestrator.py

echo.
echo [GUARDIAN] 🚨 ALERTA: EL NUCLEO HA CAIDO O SE HA DETENIDO.
echo [GUARDIAN] Iniciando protocolo de resurreccion en 10 segundos...
timeout /t 10
echo [GUARDIAN] Reiniciando...
goto loop