import locale

import uvicorn
from fastapi import FastAPI, Request, Cookie
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from ausentesCCB.routes import front as front_ausentes
from datetime import datetime
import logging
import os
import sys

drive = 'C:'
if str(os.name) == 'posix':
    drive = ''

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f'{drive}/logs_server/app_{timestamp}.log'
# Configurar o logger
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Adicionar um manipulador de console para exibir mensagens no console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Adicionar o manipulador de console ao logger
logging.getLogger().addHandler(console_handler)

logging.info('Iniciando o servidor...')
locale.setlocale(locale.LC_TIME, 'pt_BR.utf8')

app = FastAPI()
favicon_path = 'favicon.ico'

app.mount("/static_ausentes", StaticFiles(directory="ausentesCCB/static"), name="static_ausentes")

# Define a dependência "access_token" para buscar o token de acesso do cookie
async def access_token(Authorization: str = Cookie(None)):
    if Authorization is None:
        raise HTTPException(status_code=401, detail="Token de acesso não fornecido")
    if "Bearer " not in Authorization:
        raise HTTPException(status_code=401, detail="Token de acesso mal formatado")
    token = Authorization.split("Bearer ")[1]
    return token


# Define o manipulador de exceções para RequestValidationError e HTTPException
@app.exception_handler(RequestValidationError)
@app.exception_handler(HTTPException)
async def validation_exception_handler(request: Request, exc: Exception):
    # Cria a página HTML personalizada com a mensagem de erro e um botão voltar
    error_html = """
    <html>
        <body style="display: flex; justify-content: center; align-items: center; height: 100vh;">
            <div style="text-align: center;">
                <h1>Erro: {}</h1>
                <button onclick="history.back()">Voltar</button>
            </div>
        </body>
    </html>
    """.format(exc.detail)

    # Retorna a página HTML personalizada como uma resposta HTTP
    return HTMLResponse(content=error_html, status_code=exc.status_code)


app.include_router(front_ausentes.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)
