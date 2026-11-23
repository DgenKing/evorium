"""Open-Meteo reading cache. Only the background loop fetches; reads and routines never do."""
import json
import logging
import math
from datetime import datetime,timezone
import httpx
from evorium import world
from evorium.db import connect,DEFAULT_DB_PATH
from evorium.configuration import load

INTERVAL=30*60
MAX_AGE=6*60*60
URL='https://api.open-meteo.com/v1/forecast'
ATTRIBUTION='Weather: Open-Meteo (CC BY 4.0)'
logger=logging.getLogger(__name__)


def condition(code):
    if code==0:return 'clear'
    if code in (1,2,3):return 'cloudy'
    if code in (45,48):return 'fog'
    if code in (51,53,55,56,57):return 'drizzle'
    if code in (61,63,66,80,81):return 'rain'
    if code in (65,67,82):return 'heavy_rain'
    if code in (71,73,75,77,85,86):return 'snow'
    if code in (95,96,99):return 'thunder'
    return 'unknown'


def parse(payload):
    current=payload['current']
    def number(key,low,high):
        value=current[key]
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Invalid weather '+key)
        return value
    temp=number('temperature_2m',-80,65)
    wind=number('wind_speed_10m',0,500)
    precipitation=number('precipitation',0,500)
    code=number('weather_code',0,99)
    stamp=number('time',0,10**11)
    label=condition(code)
    return {'time':stamp,'temperature':temp,'wind':wind,'condition':label,
            'raining':label in ('drizzle','rain','heavy_rain','thunder') or (precipitation>0 and label!='snow')}


def _real(real_at=None):
    return real_at or datetime.now(timezone.utc)


def aligned(settings,sim_now,real_at):
    local=real_at.astimezone(world.TZ).replace(tzinfo=None)
    return float(settings.get('speed','1'))==1 and abs((local-sim_now).total_seconds())<300


def from_settings(settings,sim_now,real_at=None):
    real_at=_real(real_at)
    unknown={'condition':'unknown','raining':False,'temperature':None,'wind':None,'source':'unknown','label':'Weather unavailable'}
    try:
        reading=json.loads(settings.get('weather_reading','null'))
        if not reading or not -300<=real_at.timestamp()-reading['time']<=MAX_AGE:return unknown
        if condition({'clear':0,'cloudy':3,'fog':45,'drizzle':51,'rain':61,'heavy_rain':65,'snow':71,'thunder':95}.get(reading['condition'],-1))=='unknown':return unknown
        live=aligned(settings,sim_now,real_at)
        label=reading['condition'].replace('_',' ')+f", {reading['temperature']:g}°C"
        return {**reading,'source':'real' if live else 'cached','label':label if live else 'Last reading: '+label}
    except (ValueError,TypeError,KeyError):return unknown


def read(c,sim_now,real_at=None):
    return from_settings(dict(c.execute('SELECT key,value FROM world')),sim_now,real_at)


def prompt_line(reading):
    return 'Weather in Ancoats: '+reading['label']+'.'


def refresh(sim_now,db_path=DEFAULT_DB_PATH,*,real_at=None):
    """Bound failures too. Never make a weather outage an outage for the simulation."""
    real_at=_real(real_at)
    try:
        if not getattr(load(),'WEATHER_ENABLED',True):return False
        with connect(db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            settings=dict(c.execute('SELECT key,value FROM world'))
            if not aligned(settings,sim_now,real_at):return False
            last=float(settings.get('weather_attempt_at','0'))
            if real_at.timestamp()-last<INTERVAL:return False
            world._set(c,'weather_attempt_at',real_at.timestamp())
        response=httpx.get(URL,params={'latitude':53.485,'longitude':-2.226,
            'current':'temperature_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m',
            'timezone':'Europe/London','timeformat':'unixtime'},timeout=3)
        response.raise_for_status()
        reading=parse(response.json())
        if not -300<=real_at.timestamp()-reading['time']<=MAX_AGE:raise ValueError('Stale weather response')
        with connect(db_path) as c:world._set(c,'weather_reading',json.dumps(reading))
        return True
    except Exception as exc:
        logger.warning('Weather refresh unavailable (%s); keeping last reading.',type(exc).__name__)
        return False
