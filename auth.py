from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from database import models, database
import crud
import schemas

load_dotenv()

# --- Configuration ---
# Load secret key from environment variable
SECRET_KEY = os.getenv("SECRET_KEY")
if SECRET_KEY is None:
    raise ValueError("SECRET_KEY environment variable not set. Please create a .env file and set it.")
    
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Token Creation ---
def create_access_token(data: dict, role: schemas.Role):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "role": role})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Token Verification and User Retrieval ---
def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: schemas.Role = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    return token_data

# --- Dependency to get current user ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_access_token(token, credentials_exception)
    user = crud.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    # Attach the role from the token to the user object for easy access in dependencies
    user.role = token_data.role
    return user

def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_tenant(current_user: models.User = Depends(get_current_active_user)) -> models.Tenant:
    if not current_user.tenant:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
    return current_user.tenant

# --- Subscription & Role Dependencies ---
def require_active_subscription(current_tenant: models.Tenant = Depends(get_current_tenant)) -> models.Subscription:
    subscription = current_tenant.subscription
    if not subscription or subscription.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription is required to perform this action."
        )
    return subscription

def is_super_admin(current_user: models.User = Depends(get_current_active_user)):
    if current_user.role != schemas.Role.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges"
        )
    return current_user

def is_admin_or_super_admin(current_user: models.User = Depends(get_current_active_user)):
    if current_user.role not in [schemas.Role.admin, schemas.Role.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges"
        )
    return current_user