from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import asyncio
import platform
import subprocess
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logger_config import logger
import auth
from database import models, database
import schemas
import crud
from celery.result import AsyncResult
from celery_config import celery_app
from tasks import run_ssh_telnet_sync, run_snmp_sync

# --- Rate Limiter Initialization ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="OLT Manager SaaS API", openapi_tags=[
    {"name": "Auth & Signup", "description": "Endpoints for user authentication and signup."},
    {"name": "Users", "description": "Operations with users."},
    {"name": "Tenants", "description": "Operations with tenants."},
    {"name": "OLTs", "description": "Operations with OLTs."},
    {"name": "ONUs", "description": "Operations with ONUs."},
    {"name": "Vendors", "description": "Operations with vendors."},
    {"name": "OIDs", "description": "Operations with OIDs."},
    {"name": "Tasks", "description": "Operations with background tasks."},
    {"name": "Super Admin - Billing", "description": "Endpoints for super admins to manage billing."},
    {"name": "Billing", "description": "Endpoints for managing billing."},
])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

# --- Core Dependencies ---
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- App Events ---
@app.on_event("startup")
async def startup_event():
    db = database.SessionLocal()
    try:
        vendors = ["hsgq", "hioso", "zte"]
        for vendor_name in vendors:
            if not db.query(models.Vendor).filter(models.Vendor.name == vendor_name).first():
                db.add(models.Vendor(name=vendor_name))
        db.commit()
        if not crud.get_tenant_by_name(db, name="Default Tenant"):
            logger.info("Creating a default tenant.")
            crud.create_tenant(db, tenant=schemas.TenantCreate(name="Default Tenant"))
    finally:
        db.close()
    logger.info("Application startup complete. OLT status checking is handled by Celery Beat.")

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Welcome to OLT Manager SaaS API"}

@app.post("/login", response_model=schemas.Token, tags=["Auth & Signup"])
@limiter.limit("5/minute")
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username}, role=user.role)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/signup", response_model=schemas.SignUpResponse, tags=["Auth & Signup"], summary="Sign up a new user and create their tenant")
@limiter.limit("5/minute")
def signup(request: Request, user_data: schemas.UserSignUp, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, email=user_data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if crud.get_user_by_username(db, username=user_data.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    result = crud.create_user_and_tenant(db=db, user=user_data)
    return result

@app.get("/users/me", response_model=schemas.User, tags=["Users"], summary="Get details for the current logged-in user")
@limiter.limit("100/minute")
def read_users_me(request: Request, current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    return current_user

@app.get("/tenant/me", response_model=schemas.Tenant, tags=["Tenants"], summary="Get details for the current tenant")
@limiter.limit("100/minute")
def read_tenant_me(request: Request, current_tenant: models.Tenant = Depends(auth.get_current_tenant)):
    return current_tenant

@app.post("/users/", response_model=schemas.User, tags=["Users"], summary="Create a new user for the current tenant")
@limiter.limit("30/minute")
def create_user_for_current_tenant(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), current_user: models.User = Depends(auth.is_super_admin)):
    if crud.get_user_by_email(db, email=user.email) or crud.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Email or username already registered")
    return crud.create_user(db=db, user=user, tenant_id=current_tenant.id)

@app.get("/users/", response_model=List[schemas.User], tags=["Users"], summary="List all users for the current tenant")
@limiter.limit("100/minute")
def read_users_for_current_tenant(request: Request, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    return db.query(models.User).filter(models.User.tenant_id == current_tenant.id).all()

@app.get("/users/{user_id}", response_model=schemas.User, tags=["Users"], summary="Get a specific user by ID")
@limiter.limit("100/minute")
def read_user(request: Request, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Super admin can access any user, admin can only access users in their own tenant
    if current_user.role != schemas.Role.super_admin and db_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions to access this user")
    return db_user

@app.put("/users/{user_id}", response_model=schemas.User, tags=["Users"], summary="Update a user")
@limiter.limit("30/minute")
def update_user(request: Request, user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_super_admin)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Super admin can update any user, admin can only update users in their own tenant
    if current_user.role != schemas.Role.super_admin and db_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions to update this user")
    return crud.update_user(db=db, user_id=user_id, user_update=user_update)

@app.delete("/users/{user_id}", response_model=schemas.User, tags=["Users"], summary="Delete a user")
@limiter.limit("30/minute")
def delete__user(request: Request, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_super_admin)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Prevent users from deleting themselves
    if db_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    # Super admin can delete any user, admin can only delete users in their own tenant
    if current_user.role != schemas.Role.super_admin and db_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions to delete this user")
    return crud.delete_user(db=db, user_id=user_id)

@app.post("/olts/", response_model=schemas.OLT, tags=["OLTs"], summary="Create an OLT for the current tenant")
@limiter.limit("30/minute")
def create_olt(
    request: Request, 
    olt: schemas.OLTCreate, 
    db: Session = Depends(get_db), 
    current_tenant: models.Tenant = Depends(auth.get_current_tenant), 
    subscription: models.Subscription = Depends(auth.require_active_subscription)
):  
    # Check OLT limit
    current_olt_count = db.query(models.OLT).filter(models.OLT.tenant_id == current_tenant.id).count()
    if current_olt_count >= subscription.max_olts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"OLT limit of {subscription.max_olts} for your current plan has been reached."
        )
        
    # Check ONU limit
    current_onu_count = crud.count_all_onus_for_tenant(db, tenant_id=current_tenant.id)
    if current_onu_count >= subscription.max_onus:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"ONU limit of {subscription.max_onus} for your current plan has been reached."
        )

    if crud.get_olt_by_ip_and_tenant(db, ip=olt.ip, tenant_id=current_tenant.id):
        raise HTTPException(status_code=400, detail=f"OLT with IP {olt.ip} already registered for this tenant")
    if not db.query(models.Vendor).filter(models.Vendor.id == olt.vendor_id).first():
        raise HTTPException(status_code=404, detail=f"Vendor with id {olt.vendor_id} not found")
    
    return crud.create_olt(db=db, olt=olt, tenant_id=current_tenant.id)

@app.get("/olts/", response_model=List[schemas.OLT], tags=["OLTs"], summary="List OLTs for the current tenant")
@limiter.limit("100/minute")
def read_olts(request: Request, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), skip: int = 0, limit: int = 100, current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    return crud.get_olts_by_tenant(db=db, tenant_id=current_tenant.id, skip=skip, limit=limit)

@app.get("/olts/{olt_id}", response_model=schemas.OLT, tags=["OLTs"], summary="Get a specific OLT")
@limiter.limit("100/minute")
def read_olt(request: Request, olt_id: int, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    db_olt = crud.get_olt(db, olt_id=olt_id)
    if db_olt is None or db_olt.tenant_id != current_tenant.id:
        raise HTTPException(status_code=404, detail="OLT not found")
    return db_olt

@app.put("/olts/{olt_id}", response_model=schemas.OLT, tags=["OLTs"], summary="Update an OLT")
@limiter.limit("30/minute")
def update_olt(
    request: Request, 
    olt_id: int, 
    olt_update: schemas.OLTUpdate, 
    db: Session = Depends(get_db), 
    current_tenant: models.Tenant = Depends(auth.get_current_tenant), 
    current_user: models.User = Depends(auth.is_admin_or_super_admin)
):
    db_olt = crud.get_olt(db, olt_id=olt_id)
    if db_olt is None or db_olt.tenant_id != current_tenant.id:
        raise HTTPException(status_code=404, detail="OLT not found")
    return crud.update_olt(db=db, olt_id=olt_id, olt_update=olt_update)

@app.delete("/olts/{olt_id}", response_model=schemas.OLT, tags=["OLTs"], summary="Delete an OLT")
@limiter.limit("30/minute")
def delete_olt(
    request: Request, 
    olt_id: int, 
    db: Session = Depends(get_db), 
    current_tenant: models.Tenant = Depends(auth.get_current_tenant), 
    current_user: models.User = Depends(auth.is_admin_or_super_admin)
):
    db_olt = crud.get_olt(db, olt_id=olt_id)
    if db_olt is None or db_olt.tenant_id != current_tenant.id:
        raise HTTPException(status_code=404, detail="OLT not found")
    return crud.delete_olt(db=db, olt_id=olt_id)

@app.post("/olts/{olt_id}/sync-onus", tags=["ONUs"], summary="Sync ONUs via Telnet/SSH")
@limiter.limit("5/5minutes")
async def sync_olt_onus(request: Request, olt_id: int, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), current_user: models.User = Depends(auth.is_super_admin)):
    db_olt = read_olt(request, olt_id, db, current_tenant, current_user)
    if db_olt.status != "online":
        raise HTTPException(status_code=400, detail=f"OLT {db_olt.ip} is offline")
    task = run_ssh_telnet_sync.delay(olt_id)
    return {"message": "Telnet/SSH sync job started", "task_id": task.id}

@app.post("/olts/{olt_id}/onus/snmp-sync", tags=["ONUs"], summary="Sync ONUs via SNMP")
@limiter.limit("5/5minutes")
async def sync_onus_snmp(request: Request, olt_id: int, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), current_user: models.User = Depends(auth.is_super_admin)):
    db_olt = read_olt(request, olt_id, db, current_tenant, current_user)
    if db_olt.status != "online":
        raise HTTPException(status_code=400, detail=f"OLT {db_olt.ip} is offline")
    task = run_snmp_sync.delay(olt_id)
    return {"message": "SNMP sync job started", "task_id": task.id}

@app.get("/tasks/{task_id}", tags=["Tasks"], summary="Check the status of a background task")
@limiter.limit("120/minute")
def get_task_status(request: Request, task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result
    }

@app.get("/olts/{olt_id}/onus", response_model=List[schemas.Onu], tags=["ONUs"], summary="Get stored ONUs for a specific OLT")
@limiter.limit("100/minute")
def get_stored_onus(request: Request, olt_id: int, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), skip: int = 0, limit: int = 100, current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    db_olt = read_olt(request, olt_id, db, current_tenant, current_user)
    return crud.get_onus_by_olt(db=db, olt_id=db_olt.id, skip=skip, limit=limit)

@app.get("/onus/", response_model=schemas.OnuListResponse, tags=["ONUs"], summary="List all ONUs for the current tenant")
@limiter.limit("100/minute")
def read_all_onus_for_tenant(request: Request, db: Session = Depends(get_db), current_tenant: models.Tenant = Depends(auth.get_current_tenant), skip: int = 0, limit: int = 100, current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    onus = crud.get_all_onus_for_tenant(db=db, tenant_id=current_tenant.id, skip=skip, limit=limit)
    total = crud.count_all_onus_for_tenant(db=db, tenant_id=current_tenant.id)
    return {"total": total, "onus": onus}


@app.get("/vendors/", response_model=List[schemas.Vendor], tags=["Vendors"], summary="List all supported Vendors")
@limiter.limit("100/minute")
def read_vendors(request: Request, skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    return db.query(models.Vendor).offset(skip).limit(limit).all()

@app.get("/oids/", response_model=List[schemas.OID], tags=["OIDs"], summary="List all OIDs")
@limiter.limit("100/minute")
def read_oids(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    return crud.get_oids(db, skip=skip, limit=limit)

@app.post("/oids/", response_model=schemas.OID, tags=["OIDs"], summary="Create a new OID")
@limiter.limit("30/minute")
def create_oid(request: Request, oid: schemas.OIDCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_super_admin)):
    # In a real app, you might want to check for duplicates before creating
    return crud.create_oid(db=db, oid=oid)

@app.get("/oids/{oid_id}", response_model=schemas.OID, tags=["OIDs"], summary="Get a specific OID")
@limiter.limit("100/minute")
def read_oid(request: Request, oid_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_admin_or_super_admin)):
    db_oid = crud.get_oid(db, oid_id=oid_id)
    if db_oid is None:
        raise HTTPException(status_code=404, detail="OID not found")
    return db_oid

@app.put("/oids/{oid_id}", response_model=schemas.OID, tags=["OIDs"], summary="Update an OID")
@limiter.limit("30/minute")
def update_oid(request: Request, oid_id: int, oid: schemas.OIDUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_super_admin)):
    db_oid = crud.update_oid(db, oid_id=oid_id, oid=oid)
    if db_oid is None:
        raise HTTPException(status_code=404, detail="OID not found")
    return db_oid

@app.delete("/oids/{oid_id}", response_model=schemas.OID, tags=["OIDs"], summary="Delete an OID")
@limiter.limit("30/minute")
def delete_oid(request: Request, oid_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.is_super_admin)):
    db_oid = crud.delete_oid(db, oid_id=oid_id)
    if db_oid is None:
        raise HTTPException(status_code=404, detail="OID not found")
    return db_oid

# --- Manual Subscription Management (Super Admin Only) ---

# Define plans to avoid magic strings
PLANS = {
    "free": {"max_olts": 1, "max_onus": 50},
    "pro": {"max_olts": 10, "max_onus": 1000},
    "enterprise": {"max_olts": 100, "max_onus": 10000}
}

@app.put("/tenants/{tenant_id}/subscription", response_model=schemas.Tenant, tags=["Super Admin - Billing"], summary="Manually set or update a tenant's subscription plan")
def set_tenant_subscription(
    tenant_id: int,
    sub_update: schemas.SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.is_super_admin)
):
    db_tenant = crud.get_tenant(db, tenant_id=tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    plan_name = sub_update.plan_name.lower()
    if plan_name not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan name. Available plans: {list(PLANS.keys())}")

    plan_limits = PLANS[plan_name]
    end_date = datetime.utcnow() + timedelta(days=sub_update.duration_days)

    # Check if subscription already exists
    db_subscription = db.query(models.Subscription).filter(models.Subscription.tenant_id == tenant_id).first()

    if db_subscription:
        # Update existing subscription
        db_subscription.plan_name = plan_name
        db_subscription.status = "active"
        db_subscription.current_period_end = end_date
        db_subscription.max_olts = plan_limits["max_olts"]
        db_subscription.max_onus = plan_limits["max_onus"]
        # Update placeholder ID, ensuring it's unique
        db_subscription.stripe_subscription_id = f"manual_{datetime.utcnow().timestamp()}" 
    else:
        # Create new subscription
        db_subscription = models.Subscription(
            tenant_id=tenant_id,
            plan_name=plan_name,
            status="active",
            current_period_end=end_date,
            max_olts=plan_limits["max_olts"],
            max_onus=plan_limits["max_onus"],
            stripe_subscription_id=f"manual_{datetime.utcnow().timestamp()}" # Placeholder
        )
        db.add(db_subscription)
    
    db.commit()
    db.refresh(db_tenant) # Refresh to show updated subscription relationship
    return db_tenant

@app.get("/tenants/{tenant_id}/subscription", response_model=schemas.Subscription, tags=["Billing"], summary="Get subscription details for a tenant")
def get_tenant_subscription(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.is_admin_or_super_admin)
):
    # Ensure the current user is a super_admin or an admin of the requested tenant
    if current_user.role != schemas.Role.super_admin and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this tenant's subscription")

    subscription = crud.get_subscription_by_tenant(db, tenant_id=tenant_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found for this tenant")
    
    return subscription

@app.get("/subscription/quota", response_model=schemas.SubscriptionQuota, tags=["Billing"], summary="Get current subscription quota usage")
@limiter.limit("100/minute")
def get_subscription_quota(
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: models.Tenant = Depends(auth.get_current_tenant)
):
    return crud.get_subscription_quota(db=db, tenant_id=current_tenant.id)
