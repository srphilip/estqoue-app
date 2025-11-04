@echo off
title Sistema de Controle de Estoque (Flask)

REM =========================================================================
REM ATIVACAO DO AMBIENTE ANACONDA
REM AJUSTE O CAMINHO ABAIXO SE NECESSARIO!
REM Caminho padrao do Anaconda para o usuario atual:
REM Verifique se a pasta se chama 'Anaconda3' ou 'Miniconda3'
set ANACONDA_PATH=$$\text{C:\Users\pmagno\AppData\Local\anaconda3\Scripts}$$

REM Tenta ativar o ambiente (O activate.bat está dentro da pasta Scripts)
call "%ANACONDA_PATH%\Scripts\activate.bat"

REM Navega para a pasta do projeto (garante que ele execute de onde o .bat está)
cd /d "%~dp0"

REM Verifica se o ambiente foi ativado corretamente
if exist "%ANACONDA_PATH%\Scripts\conda.exe" (
    echo.
    echo ==========================================================
    echo SISTEMA DE ESTOQUE LOCAL (Pronto para Uso)
    echo ==========================================================
    echo O servidor esta sendo iniciado...
    echo Acesse no navegador: http://127.0.0.1:5000/
    echo Para outros PCs na rede: http://[IP_DO_SEU_PC]:5000/
    echo ==========================================================
    echo.
    
    REM Inicia o servidor Flask
    python app.py

) else (
    echo.
    echo ERRO CRITICO: O ambiente ANACONDA nao foi encontrado no caminho especificado.
    echo O caminho que esta falhando eh: %ANACONDA_PATH%
    echo ----------------------------------------------------------
    echo SOLUCAO: Encontre a pasta principal do Anaconda (ex: Anaconda3)
    echo          e ajuste a variavel ANACONDA_PATH no script iniciar_app.bat.
    echo ----------------------------------------------------------
)

REM Garante que a janela nao feche em caso de erro
pause