import logging
import secrets
import string
from unidecode import unidecode
from zoneinfo import ZoneInfo

from calendar import monthrange
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from ausentesCCB.dependencies import db, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, \
    collection

templatesAusentesManager = Jinja2Templates(directory="ausentesCCB/templates")

router = APIRouter(
    prefix="",
    tags=["Front"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


def generate_password(length):
    alphabet = string.ascii_lowercase + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def return_default(request, error):
    options = last_five_fourth_saturdays()
    return templatesAusentesManager.TemplateResponse("login/login.html",
                                                     {
                                                         "request": request,
                                                         "options": options,
                                                         "error": error
                                                     })


@router.post("/insert_ausentes", response_class=HTMLResponse, include_in_schema=False)
async def insert(request: Request):
    access_token = request.cookies.get("Authorization").replace("Bearer ", "")

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        print("Token expirado!")
    except JWTError:
        print("Token inválido!")

    sub = payload.get("sub")
    client_id = payload.get("client_id")
    if sub == client_id:
        form = await request.form()
        justificativa = form.get('justificativa', None)
        outraJustificativa = form.get('outraJustificativa', None)

        date = form.get('date', None)
        day, month, year = map(int, date.split('-'))

        # Defina o fuso horário para São Paulo
        brazil_tz = ZoneInfo('America/Sao_Paulo')
        date_hour_test = datetime(year, month, day, 15, 0, 0, tzinfo=brazil_tz)

        # Obtenha a data e hora atual
        current_datetime = datetime.now(brazil_tz)

        if ("-admin" in sub and "-admin" in client_id) or (current_datetime <= date_hour_test):
            date_test = datetime(year, month, day, 0, 0, 0, tzinfo=brazil_tz)

            cargo = form.get('cargo', None)
            church = form.get('church', None)
            church_db = await db['churches'].find_one({"praying_house": church})

            if cargo == 'Encarregado Local':
                name = church_db['maestro']
            elif cargo == 'Encarregado Regional':
                name = church_db['maestro_master']
            elif cargo == 'Examinadora':
                name = church_db.get('examinadora', None)
            else:
                name = None

            if name in (None, '***', '-'):
                response = await justificativa_page(date, request, "", "Não foi possível encontrar o nome e ministério nesta comum!")
            else:
                document = {
                    "name": name,
                    "justificativa": justificativa,
                    "outraJustificativa": outraJustificativa,
                    "date": date_test,
                    "nameFind": unidecode(name).lower(),
                    "dateFind": date_test.strftime('%d-%m-%Y'),
                }

                # Verifique se já existe um documento com os campos 'nameFind' e 'dateFind'
                existing_doc = await collection.find_one({"nameFind": document["nameFind"], "dateFind": document["dateFind"]})

                if existing_doc:
                    # Se o documento já existe, atualize-o
                    collection.update_one(
                        {"_id": existing_doc["_id"]},  # Use o _id para identificar o documento existente
                        {"$set": document}  # Use $set para atualizar os campos
                    )
                    success = f"O nome {name} foi atualizado com sucesso no dia {date}!"
                else:
                    # Se o documento não existe, insira-o
                    collection.insert_one(document)
                    success = f"O nome {name} foi inserido com sucesso no dia {date}!"

                response = await justificativa_page(date, request, success)
                if 'BEARER' in access_token.upper():
                    access_token = access_token.split(' ')[-1]
                response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=1800)
        else:
            error = "Só é possível justificar até as 15:00h do sábado!"
            response = return_default(request, error)
        return response
    raise HTTPException(status_code=400, detail="ACESSO INVÁLIDO.")


async def justificativa_page(date, request, success, error=''):
    projection = {'_id': 1, 'praying_house': 1}

    churches = []
    async for document in db['churches'].find({}, projection).sort('praying_house', 1):
        if document['praying_house'] != '***':
            churches.append(document)

    response = templatesAusentesManager.TemplateResponse("/justificativa/justificativa.html",
                                                         {
                                                             "request": request,
                                                             "title": f"Ausentes CCB",
                                                             "date": date,
                                                             "success": success,
                                                             "churches": churches,
                                                             "error": error
                                                         })
    return response


@router.post("/login_ausentes", response_class=HTMLResponse, include_in_schema=False)
async def login_for_access_token(request: Request):
    form = await request.form()
    username = form.get('username', None)
    password = form.get('password_2', None)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    brazil_tz = ZoneInfo('America/Sao_Paulo')
    day, month, year = map(int, username.split('-'))
    date_hour_test = datetime(year, month, day, 15, 0, 0, tzinfo=brazil_tz)

    current_datetime = datetime.now(brazil_tz)

    if password.lower() == 'ccb':
        lower_limit = date_hour_test - timedelta(days=7)
        if lower_limit <= current_datetime <= date_hour_test:
            generate_uuid = generate_password(8)
            access_token = await create_access_token(data={"sub": generate_uuid}, expires_delta=access_token_expires)
            response = await justificativa_page(username, request, "")

            if 'BEARER' in access_token.upper():
                access_token = access_token.split(' ')[-1]
            response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=1800)
        else:
            error = f"""O intervalo para justificativa de ausência da reunão do mês {month} de {year} é a partir do dia {lower_limit.strftime('%d-%m-%Y')} até dia {date_hour_test.strftime('%d-%m-%Y')} às {date_hour_test.strftime('%H:%M')}h!"""
            response = return_default(request, error)
    elif password.lower() == 'admin':
        generate_uuid = f'{generate_password(8)}-admin'
        access_token = await create_access_token(data={"sub": generate_uuid}, expires_delta=access_token_expires)
        response = await justificativa_page(username, request, "")

        if 'BEARER' in access_token.upper():
            access_token = access_token.split(' ')[-1]
        response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=1800)
    else:
        error = f"Informações de acesso inválidas!"
        response = return_default(request, error)
    return response


def last_five_fourth_saturdays():
    now = datetime.now()
    months = []
    for i in range(14):
        month = now - relativedelta(months=i)
        days = monthrange(month.year, month.month)[1]
        for day in range(1, days + 1):
            date = datetime(month.year, month.month, day)
            if date.weekday() == 5:
                date = date + timedelta(days=21)
                months.append(date.strftime('%d-%m-%Y'))
                break
    return months


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def login_init(request: Request):
    access_token = None
    options = last_five_fourth_saturdays()
    response = templatesAusentesManager.TemplateResponse("login/login.html",
                                                         {
                                                             "request": request,
                                                             "options": options,
                                                         })
    response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=0)
    return response


@router.get("/autocomplete/ausentes", include_in_schema=False)
async def autocomplete_ausentes(request: Request, prefix: str):
    try:
        access_token = request.cookies.get("Authorization").replace("Bearer ", "")
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        logging.warning("Token expirado!")
    except JWTError:
        logging.warning("Token inválido!")
    except Exception as e:
        payload = {"sub": None, "client_id": "Error"}
        logging.warning(e)

    if payload.get("sub") == payload.get("client_id"):
        normalized_prefix = unidecode(prefix)
        data_db = await collection.find({"nameFind": {"$regex": f"^{normalized_prefix}", "$options": "i"}}).to_list(
            length=100)
        names = [doc['name'] for doc in data_db]
        return names
    logging.error(request.headers)
    raise HTTPException(status_code=400, detail="ACESSO INVÁLIDO.")
