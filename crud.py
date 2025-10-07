from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database import models
import schemas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# --- Tenant CRUD ---
def get_tenant(db: Session, tenant_id: int):
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()


def get_tenant_by_name(db: Session, name: str):
    return db.query(models.Tenant).filter(models.Tenant.name == name).first()


def get_tenants(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Tenant).offset(skip).limit(limit).all()


def get_subscription_by_tenant(db: Session, tenant_id: int):
    return db.query(models.Subscription).filter(models.Subscription.tenant_id == tenant_id).first()


def create_tenant(db: Session, tenant: schemas.TenantCreate):
    db_tenant = models.Tenant(name=tenant.name)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant


# --- User CRUD ---
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate, tenant_id: int):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email, 
        username=user.username, 
        hashed_password=hashed_password, 
        tenant_id=tenant_id,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    db_user = get_user(db, user_id=user_id)
    if not db_user:
        return None
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id=user_id)
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user


# --- SaaS Signup Flow ---
def create_user_and_tenant(db: Session, user: schemas.UserSignUp):
    """
    Creates a new Tenant and a new User (the first admin) in a single transaction.
    """
    # Create the tenant first
    tenant_name = f"{user.username}'s Team"
    db_tenant = models.Tenant(name=tenant_name)
    db.add(db_tenant)
    db.flush()  # Use flush to get the tenant ID before committing the transaction

    # Then create the user associated with the new tenant
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        tenant_id=db_tenant.id,
        role=schemas.Role.super_admin,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_tenant)
    db.refresh(db_user)
    return {"user": db_user, "tenant": db_tenant}


# --- OLT CRUD ---
def get_olt(db: Session, olt_id: int):
    return db.query(models.OLT).filter(models.OLT.id == olt_id).first()


def get_olt_by_ip_and_tenant(db: Session, ip: str, tenant_id: int):
    return db.query(models.OLT).filter(models.OLT.ip == ip, models.OLT.tenant_id == tenant_id).first()


def get_olts_by_tenant(db: Session, tenant_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.OLT).filter(models.OLT.tenant_id == tenant_id).offset(skip).limit(limit).all()


def create_olt(db: Session, olt: schemas.OLTCreate, tenant_id: int):
    db_olt = models.OLT(**olt.dict(), tenant_id=tenant_id)
    db.add(db_olt)
    db.commit()
    db.refresh(db_olt)
    return db_olt


def update_olt(db: Session, olt_id: int, olt_update: schemas.OLTUpdate):
    db_olt = get_olt(db, olt_id=olt_id)
    if not db_olt:
        return None
    update_data = olt_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_olt, key, value)
    db.add(db_olt)
    db.commit()
    db.refresh(db_olt)
    return db_olt


def delete_olt(db: Session, olt_id: int):
    db_olt = get_olt(db, olt_id=olt_id)
    if not db_olt:
        return None
    db.delete(db_olt)
    db.commit()
    return db_olt


# OID CRUD
def get_oid(db: Session, oid_id: int):
    return db.query(models.OID).filter(models.OID.id == oid_id).first()


def get_oids(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.OID).offset(skip).limit(limit).all()


def create_oid(db: Session, oid: schemas.OIDCreate):
    db_oid = models.OID(**oid.model_dump())
    db.add(db_oid)
    db.commit()
    db.refresh(db_oid)
    return db_oid


def update_oid(db: Session, oid_id: int, oid: schemas.OIDUpdate):
    db_oid = db.query(models.OID).filter(models.OID.id == oid_id).first()
    if db_oid:
        update_data = oid.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_oid, key, value)
        db.commit()
        db.refresh(db_oid)
    return db_oid


def delete_oid(db: Session, oid_id: int):
    db_oid = db.query(models.OID).filter(models.OID.id == oid_id).first()
    if db_oid:
        db.delete(db_oid)
        db.commit()
    return db_oid


def get_oids_by_vendor_and_model(db: Session, vendor_name: str, model: str):
    """
    Fetches OIDs for a specific vendor and model.
    """
    vendor = db.query(models.Vendor).filter(models.Vendor.name == vendor_name).first()
    if not vendor:
        return []
    return db.query(models.OID).filter(
        models.OID.vendor_id == vendor.id,
        models.OID.model == model
    ).all()


# ONU CRUD
def get_onus_by_olt(db: Session, olt_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Onu).filter(models.Onu.olt_id == olt_id).offset(skip).limit(limit).all()


def get_all_onus(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Onu).offset(skip).limit(limit).all()


def count_all_onus(db: Session):
    return db.query(models.Onu).count()


def get_all_onus_for_tenant(db: Session, tenant_id: int, skip: int = 0, limit: int = 100):
    """
    Gets all ONUs for a given tenant by joining Onu with OLT.
    """
    return db.query(models.Onu).join(models.OLT).filter(models.OLT.tenant_id == tenant_id).offset(skip).limit(limit).all()


def count_all_onus_for_tenant(db: Session, tenant_id: int):
    """
    Counts all ONUs for a given tenant.
    """
    return db.query(models.Onu).join(models.OLT).filter(models.OLT.tenant_id == tenant_id).count()

def get_subscription_quota(db: Session, tenant_id: int) -> schemas.SubscriptionQuota:
    subscription = get_subscription_by_tenant(db, tenant_id=tenant_id)
    if not subscription:
        return schemas.SubscriptionQuota(olts_used=0, olts_limit=0, onus_used=0, onus_limit=0)

    olts_used = db.query(models.OLT).filter(models.OLT.tenant_id == tenant_id).count()
    onus_used = count_all_onus_for_tenant(db, tenant_id=tenant_id)

    return schemas.SubscriptionQuota(
        olts_used=olts_used,
        olts_limit=subscription.max_olts,
        onus_used=onus_used,
        onus_limit=subscription.max_onus,
    )