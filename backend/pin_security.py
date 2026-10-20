"""PIN hashing and database-persisted throttling; no PIN values in errors or logs."""
import hashlib, hmac, secrets, re
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import update, func
from .models import User

def validate_new_pin(pin, confirmation):
    if not isinstance(pin,str) or not re.fullmatch(r'[0-9]{6}',pin):
        raise HTTPException(400,'PIN must contain exactly six numeric digits')
    if pin != confirmation: raise HTTPException(400,'PIN confirmation does not match')

def hash_pin(pin):
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',pin.encode(),salt.encode(),600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def check_lock(db,user):
    db.refresh(user)
    if user.pin_locked_until and user.pin_locked_until > datetime.utcnow():
        raise HTTPException(429,'PIN actions temporarily locked. Try again after 15 minutes.')
    if user.pin_locked_until:
        user.pin_failures=0;user.pin_locked_until=None
        db.commit()

def failed(db,user):
    # Atomic increment prevents concurrent wrong attempts from losing updates.
    db.execute(update(User).where(User.id==user.id).values(pin_failures=func.coalesce(User.pin_failures,0)+1))
    db.flush();db.refresh(user)
    if user.pin_failures>=5:
        user.pin_locked_until=datetime.utcnow()+timedelta(minutes=15)
    db.commit()
    raise HTTPException(429 if user.pin_failures>=5 else 403,'PIN actions temporarily locked for 15 minutes' if user.pin_failures>=5 else 'Verification failed')

def verify_pin(db,user,pin):
    check_lock(db,user)
    if not user.pin_hash: raise HTTPException(409,'Set up your PIN in account security first')
    try:
        _, rounds,salt,digest=user.pin_hash.split('$')
        valid=isinstance(pin,str) and bool(re.fullmatch(r'[0-9]{6}',pin)) and hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',pin.encode(),salt.encode(),int(rounds)).hex(),digest)
    except (ValueError,TypeError): valid=False
    if not valid: failed(db,user)
    user.pin_failures=0;user.pin_locked_until=None
