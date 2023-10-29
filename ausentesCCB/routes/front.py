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


@router.post("/insert_ausentes", response_class=HTMLResponse, include_in_schema=False)
async def insert(request: Request):
    access_token = request.cookies.get("Authorization").replace("Bearer ", "")

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        print("Token expirado!")
    except JWTError:
        print("Token inválido!")

    if payload.get("sub") == payload.get("client_id"):
        form = await request.form()
        name = form.get('name', None)
        justificativa = form.get('justificativa', None)
        outraJustificativa = form.get('outraJustificativa', None)

        date = form.get('date', None)
        day, month, year = map(int, date.split('-'))

        # Defina o fuso horário para São Paulo
        brazil_tz = ZoneInfo('America/Sao_Paulo')

        date_test = datetime(year, month, day, 0, 0, 0, tzinfo=brazil_tz)

        db['absent'].insert_one({
            "name": name,
            "justificativa": justificativa,
            "outraJustificativa": outraJustificativa,
            "date": date_test,
            "nameFind": unidecode(name).lower(),
            "dateFind": date_test.strftime('%d-%m-%Y'),
        })
        response = templatesAusentesManager.TemplateResponse("/justificativa/justificativa.html",
                                                               {
                                                                   "request": request,
                                                                   "title": f"Ausentes CCB",
                                                                   "date": date,
                                                                   "success": f"{name} Inserido com sucesso!"
                                                               })
        if 'BEARER' in access_token.upper():
            access_token = access_token.split(' ')[-1]
        response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=1800)
        return response
    raise HTTPException(status_code=400, detail="ACESSO INVÁLIDO.")


@router.post("/login_ausentes", response_class=HTMLResponse, include_in_schema=False)
async def login_for_access_token(request: Request):
    form = await request.form()
    username = form.get('username', None)
    password = form.get('password_2', None)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    if password.lower() == 'ccb':
        generate_uuid = generate_password(8)
        access_token = await create_access_token(data={"sub": generate_uuid}, expires_delta=access_token_expires)
    else:
        raise HTTPException(status_code=400, detail="ACESSO INVÁLIDO.")

    response = templatesAusentesManager.TemplateResponse("/justificativa/justificativa.html",
                                                           {
                                                               "request": request,
                                                               "title": f"Ausentes CCB",
                                                               "date": username
                                                           })
    if 'BEARER' in access_token.upper():
        access_token = access_token.split(' ')[-1]
    response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, max_age=1800)
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
                logging.info(date.strftime('%d-%m-%Y'))
                months.append(date.strftime('%d-%m-%Y'))
                break
    return months


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def login_init(request: Request):
    access_token = None
    options = last_five_fourth_saturdays()
    logging.info(options)
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
