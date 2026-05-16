@echo off
echo ============================================
echo  Compilando Despacho Breña - Gestor EXE
echo ============================================

echo.
echo [1/3] Instalando dependencias...
pip install flask pyinstaller --quiet

echo.
echo [2/3] Compilando ejecutable...
pyinstaller --onefile --noconsole --name "DespachoBrena" --icon NONE app.py

echo.
echo [3/3] Listo!
echo El ejecutable esta en: dist\DespachoBrena.exe
echo.
pause
