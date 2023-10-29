import logging
import os
import time
import copy
import re
import jwt as jwtBarer

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from cryptography.fernet import Fernet
from dateutil.relativedelta import relativedelta
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

directoryTestes = 'C:/Testes'
if str(os.name) == 'posix':
    directoryTestes = '/root/Testes'

DIR = ""
PROJECT_NAME = "ATM"
PROJECT_NAME_DESC = "Agendamento de Testes Musicais"

# Configuração do MongoDB
DATABASE_NAME = "Musical"
COLLECTION_NAME = "membersFull"

# Conectar ao MongoDB
client = AsyncIOMotorClient(os.environ["MONGO_URI"])
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# Configuração de segurança
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Configuração de autenticação
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

f = Fernet(os.environ['CRYPTOGRAPHY'])

templatesAusentesManager = Jinja2Templates(directory="ausentesCCB/templates")

# Funções de autenticação
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(username: str, password: str):
    user = await db['access'].find_one({"username": username})
    if not user:
        return False
    if not user["hashed_password"] or not verify_password(password, user["hashed_password"]):
        return False

    return user


async def authenticate_user_praying_house(username: str, password: str):
    _id = await db['churches'].find_one({"praying_house": username})
    try:
        _id = _id['_id']
    except Exception as e:
        print(e)
        return False
    user = await db['access'].find_one({"id_ref": str(_id)})
    if not user:
        return False
    if not user["hashed_password"] or not verify_password(password, user["hashed_password"]):
        return False
    return user


# Funções de geração de token
async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    to_encode.update({"client_id": data.get("sub")})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_token_header(token: str = Header(...)):
    if token is None or not token.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Token inválido")
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token[7:])


async def get_current_user(auth: HTTPAuthorizationCredentials = Depends(security)):
    credentials = "Acesso não permitido, entre em contato com o administrador do sistema."
    try:
        payload = jwt.decode(auth.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail=("%s" % credentials))
        token_data = {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail=credentials)

    user = await db['access'].find_one({"username": token_data["username"]})
    if not user:
        user = await db['access'].find_one({"id_ref": token_data["username"]})
    if user is None:
        raise HTTPException(status_code=401, detail=credentials)
    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    if current_user["disabled"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def validate_token(access_token):
    if not access_token:
        access_token = ''
    if "BEARER" not in access_token.upper():
        access_token = "Bearer " + access_token
    credentials = await get_token_header(access_token)
    current_user = await get_current_user(credentials)
    current_active_user = await get_current_active_user(current_user)
    exp = await get_token_exp(access_token)
    timestamp = int(time.time())
    if 'BEARER' in access_token.upper():
        access_token = access_token.split(' ')[-1]
    decoded_token = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    # Obtenha os dados necessários para renovar o token
    username = decoded_token["sub"]
    expiration = decoded_token["exp"]

    access_token = await create_access_token(data={"sub": username},
                                             expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return current_active_user.get("disabled"), current_active_user.get("nivel"), exp, access_token


async def get_month_days(year, month, filter_church):
    start_date = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc) + relativedelta(months=1) - relativedelta(days=1)
    if filter_church:
        find_data = {'date_test': {'$gte': start_date, '$lte': end_date}}
        events = await db['schedules'].find(find_data | filter_church,
                                            {'date_test': 1, '_id': 0}).to_list(length=100)
    else:
        events = await db['schedules'].find({'date_test': {'$gte': start_date, '$lte': end_date}},
                                            {'date_test': 1, '_id': 0}).to_list(length=100)

    # Get the first day of the week and the number of days in the month
    first_weekday, num_days = monthrange(year, month)

    days = []
    # Add blank days until the first day of the month
    for _ in range(first_weekday + 1):
        days.append(None)

    # Iterate through each day in the month
    current_date = start_date
    while current_date <= end_date:
        day = current_date.day
        day_info = {
            'day': day,
            'info': current_date.strftime('%Y-%m-%d'),  # add date in "yyyy-mm-dd" format
            'events': [],
        }

        # Check the day of the week and the week of the month for color coding
        weekday = current_date.weekday()
        week_of_month = (day - 1) // 7 + 1

        if weekday == 2:  # Wednesday
            if week_of_month in [1, 3]:  # First or third Wednesday
                day_info['color'] = 'yellow'
        elif weekday == 5:  # Saturday
            if week_of_month == 2:  # Second Saturday
                day_info['color'] = 'yellow'
            elif week_of_month == 3:  # Third Saturday
                day_info['color'] = 'red'

        # Check each event to see if it occurs on this day
        for event in events:
            event_date = datetime.fromisoformat(event['date_test'].strftime('%Y-%m-%d'))
            if event_date.year == year and event_date.month == month and event_date.day == day:
                day_info['events'].append(event)

        days.append(day_info)

        # Move to the next day
        current_date += timedelta(days=1)

    return days


async def get_token_exp(access_token):
    if 'BEARER' in access_token.upper():
        access_token = access_token.split(' ')[-1]
    decoded_token = jwtBarer.decode(access_token, options={"verify_signature": False})
    exp_timestamp = decoded_token.get('exp')

    return exp_timestamp


async def generate_image_ensaio(data_db):
    hoje = datetime.now().date()
    type = 'local'
    church = data_db.get('praying_house', 'error')
    hour = data_db.get('hour', 'error').replace('h', ':').replace('m', '')
    if church == 'error' or hour == 'error' or hour == '***' or hour == '****':
        raise ValueError("Não pode seguir")
    date = data_db.get('date', 'error')
    desc = copy.deepcopy(date)
    dias_semana = {
        'segunda': 0,
        'terça': 1,
        'terca': 1,
        'quarta': 2,
        'quinta': 3,
        'sexta': 4,
        'sábado': 5,
        'sabado': 5,
        'domingo': 6
    }
    dia_semana = 'error'
    for dia, valor in dias_semana.items():
        if dia in date.lower():
            dia_semana = valor
            break
    if dia_semana == 'error':
        raise ValueError("Não pode seguir")
    ano = hoje.year
    mes = hoje.month
    date, into, diferenca = await encontrar_dia_ordem_semana(ano, mes, dia_semana, desc)
    if '-' in str(date):
        date = datetime.strptime(str(date), '%Y-%m-%d').date()
        date = date.strftime("%d/%m/%Y")
    # Lista de caracteres não permitidos
    illegal_chars = r'[<>:"/\\|?*\'-]'
    city = data_db.get('city')
    timestamp = datetime.now().strftime("%H%M%S")
    if city.lower() not in church.lower():
        church = f'{city} - {church}'
    # Remove caracteres não permitidos e substitui por um caractere vazio
    sanitized_filename = re.sub(illegal_chars, '', church).replace(" ", "_").replace("__", "_")
    return church, date, hour, into, sanitized_filename, timestamp, type


async def encontrar_dia_ordem_semana(ano, mes, dia_semana, desc):
    hoje = datetime.now().date()

    date_ordem = desc[0]
    if str(date_ordem) in ['1', '2', '3', '4', '5']:
        ordem = int(date_ordem)
    elif str(desc.split(" ")[0]).lower() in ['ultimo', 'último', 'última', 'ultima']:
        ordem = -1
    else:
        return None

    # Encontre o primeiro dia do mês
    primeiro_dia_mes = datetime(ano, mes, 1).date()

    # Calcule o deslocamento necessário para chegar ao dia da semana desejado
    deslocamento = (dia_semana - primeiro_dia_mes.weekday() + 7) % 7

    # Calcule o dia correspondente à ordem da semana
    if ordem == -1:
        ultimo_dia_mes = datetime(ano, mes + 1, 1) - timedelta(days=1)
        deslocamento = (dia_semana - ultimo_dia_mes.weekday() + 7) % 7
        sem = 7
        if not deslocamento:
            sem = 0
        dia_ordem_semana = ultimo_dia_mes.day + deslocamento - sem
    else:
        dia_ordem_semana = 1 + deslocamento + (7 * (ordem - 1))

    # Verifique se o dia está dentro do mês
    ultimo_dia_mes = datetime(ano, mes + 1, 1) - timedelta(days=1)
    if dia_ordem_semana > ultimo_dia_mes.day:
        return None

    data = datetime(ano, mes, dia_ordem_semana).date()

    into = 'No próximo dia'

    diferenca = (data - hoje).days
    data_ = copy.deepcopy(data)
    if diferenca == 0:
        into = ''
        data = 'Hoje'
    elif diferenca == 1:
        into = ''
        data = 'Amanhã'
    elif diferenca < 0:
        mes_que_vem = hoje + relativedelta(months=1)
        data, into, diferenca = await encontrar_dia_ordem_semana(mes_que_vem.year, mes_que_vem.month, dia_semana, desc)

    if 'impar' in desc.lower() or 'impares' in desc.lower():
        if int(data_.month) % 2 == 0:
            mes_que_vem = data_ + relativedelta(months=1)
            data, into, diferenca = await encontrar_dia_ordem_semana(mes_que_vem.year, mes_que_vem.month, dia_semana,
                                                                     desc)
    elif 'par' in desc.lower() or 'pares' in desc.lower():
        if int(data_.month) % 2 != 0:
            mes_que_vem = data_ + relativedelta(months=1)
            data, into, diferenca = await encontrar_dia_ordem_semana(mes_que_vem.year, mes_que_vem.month, dia_semana,
                                                                     desc)

    meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    if "-" in desc.lower():
        split_ = desc.lower().split(" ")[-1].split("-")
        mes_descricao = [mes.lower() for mes in split_]
        if any(mes in meses for mes in mes_descricao) and data_.month in [meses.index(mes) + 1 for mes in
                                                                          mes_descricao]:
            return data, into, diferenca

        mes_que_vem = data_ + relativedelta(months=1)
        data, into, diferenca = await encontrar_dia_ordem_semana(mes_que_vem.year, mes_que_vem.month, dia_semana, desc)

    return data, into, diferenca
