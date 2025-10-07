from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=True)

    users = relationship("User", back_populates="tenant")
    olts = relationship("OLT", back_populates="tenant")
    subscription = relationship("Subscription", back_populates="tenant", uselist=False)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    phone_number = Column(String, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="admin", nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))

    tenant = relationship("Tenant", back_populates="users")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    plan_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    
    max_olts = Column(Integer, default=1)
    max_onus = Column(Integer, default=100)
    
    current_period_end = Column(DateTime, nullable=False)
    
    tenant = relationship("Tenant", back_populates="subscription")

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    olts = relationship("OLT", back_populates="vendor")
    oids = relationship("OID", back_populates="vendor")

class OLT(Base):
    __tablename__ = "olts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    ip = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    ssh_port = Column(Integer, default=22)
    telnet_port = Column(Integer, default=23)
    snmp_port = Column(Integer, default=161)
    community = Column(String, default="public")
    olt_type = Column(String)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    status = Column(String, default="unknown")
    last_checked = Column(DateTime)
    ssh_delay = Column(Integer, default=10)
    ssh_timeout = Column(Integer, default=10)

    vendor = relationship("Vendor", back_populates="olts")
    tenant = relationship("Tenant", back_populates="olts")
    onus = relationship("Onu", back_populates="olt", cascade="all, delete-orphan")

class OID(Base):
    __tablename__ = "oids"

    id = Column(Integer, primary_key=True, index=True)
    oid = Column(String, nullable=False)
    fungsi = Column(String, nullable=False)
    type = Column(String, nullable=False)
    model = Column(String, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))

    vendor = relationship("Vendor", back_populates="oids")

class Onu(Base):
    __tablename__ = "onus"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    
    identifier = Column(String, index=True, nullable=False)
    pon_interface = Column(String, index=True)
    vendor_name = Column(String, index=True)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    details = Column(JSON)
    details_snmp = Column(JSON)

    olt = relationship("OLT", back_populates="onus")