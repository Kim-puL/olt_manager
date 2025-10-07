import asyncio
from celery_config import celery_app
from database import models, database
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

# Import vendor services
from vendors.hioso.telnet_service import HiosoTelnetService
from vendors.hsgq.ssh_service import HsgqSshService
from vendors.hioso.snmp_service import HiosoSnmpService
from vendors.hsgq.snmp_service import HsgqSnmpService
from vendors.hsgq.epon_snmp_service import HsgqEponSnmpService
from vendors.hsgq.epon_ssh_service import HsgqEponSshService
from logger_config import logger

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@celery_app.task
def run_ssh_telnet_sync(olt_id: int):
    db: Session = next(get_db())
    olt = db.query(models.OLT).filter(models.OLT.id == olt_id).first()
    if not olt:
        logger.error(f"[Task] OLT with id {olt_id} not found.")
        return {"error": f"OLT with id {olt_id} not found."}

    vendor_name = olt.vendor.name.lower()
    service = None
    onu_data = None
    logger.info(f"[Task] Starting Telnet/SSH sync for OLT: {olt.ip} (Tenant: {olt.tenant_id})")
    try:
        if vendor_name == 'hsgq':
            if olt.olt_type == 'epon':
                service = HsgqEponSshService(host=olt.ip, port=olt.ssh_port, username=olt.username, password=olt.password, delay=olt.ssh_delay, timeout=olt.ssh_timeout)
            else:
                service = HsgqSshService(host=olt.ip, port=olt.ssh_port, username=olt.username, password=olt.password)
            onu_data = asyncio.run(service.get_onus())
        elif vendor_name == 'hioso':
            service = HiosoTelnetService(host=olt.ip, port=olt.telnet_port, username=olt.username, password=olt.password)
            onu_data = asyncio.run(service.get_onus())
        else:
            return {"error": f"Sync not implemented for vendor: '{olt.vendor.name}'"}

        if not onu_data or "error" in onu_data:
            error_msg = onu_data.get("error", "Unknown error during sync")
            logger.error(f"[Task] Telnet/SSH sync failed for {olt.ip}: {error_msg}")
            return {"error": error_msg}

        onus_from_olt = onu_data.get("onus", [])
        wib_timezone = timezone(timedelta(hours=7))
        synced_count = 0
        for onu_item in onus_from_olt:
            identifier = onu_item["identifier"]
            db_onu = db.query(models.Onu).filter(models.Onu.identifier == identifier, models.Onu.olt_id == olt.id).first()
            current_time_wib = datetime.now(wib_timezone)
            if db_onu:
                db_onu.details = onu_item["details"]
                db_onu.last_seen = current_time_wib
            else:
                db_onu = models.Onu(olt_id=olt.id, identifier=identifier, pon_interface=onu_item["pon_interface"], vendor_name=onu_item["vendor_name"], details=onu_item["details"], last_seen=current_time_wib)
                db.add(db_onu)
            synced_count += 1
        db.commit()
        logger.info(f"[Task] Telnet/SSH sync successful for {olt.ip}. Synced {synced_count} ONUs.")
        return {"message": f"Successfully synced {synced_count} ONUs for OLT {olt.ip}"}
    except Exception as e:
        logger.error(f"[Task] Exception during Telnet/SSH sync for {olt.ip}: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()

@celery_app.task
def run_snmp_sync(olt_id: int):
    db: Session = next(get_db())
    olt = db.query(models.OLT).filter(models.OLT.id == olt_id).first()
    if not olt:
        logger.error(f"[Task] OLT with id {olt_id} not found.")
        return {"error": f"OLT with id {olt_id} not found."}

    vendor_name = olt.vendor.name.lower()
    logger.info(f"[Task] Starting SNMP sync for OLT: {olt.ip} (Tenant: {olt.tenant_id})")
    try:
        db_oids = db.query(models.OID).filter(models.OID.vendor_id == olt.vendor_id, models.OID.model == olt.olt_type).all()
        if not db_oids and olt.olt_type != 'epon':
            return {"error": f"SNMP OIDs not found for vendor: {vendor_name} and model: {olt.olt_type}"}
        oids_dict = {oid.fungsi: oid.oid for oid in db_oids}
        onus_from_snmp = []
        if vendor_name == 'hioso':
            service = HiosoSnmpService(host=olt.ip, port=olt.snmp_port, community=olt.community, oids=oids_dict)
            onus_from_snmp = asyncio.run(service.get_onus_snmp())
        elif vendor_name == 'hsgq':
            if olt.olt_type == 'epon':
                service = HsgqEponSnmpService(host=olt.ip, port=olt.snmp_port, community=olt.community, db=db)
                onu_data = asyncio.run(service.get_onus())
                if "error" in onu_data:
                    return {"error": onu_data["error"]}
                onus_from_snmp = onu_data.get("onus", [])
            else:
                service = HsgqSnmpService(host=olt.ip, port=olt.snmp_port, community=olt.community, oids=oids_dict)
                onus_from_snmp = asyncio.run(service.get_onus_snmp())
        else:
            return {"error": f"SNMP sync not implemented for vendor: '{vendor_name}'"}

        if not onus_from_snmp:
            return {"message": "No ONUs found via SNMP or error in communication."}

        wib_timezone = timezone(timedelta(hours=7))
        updated_count = 0
        for onu_item in onus_from_snmp:
            identifier = onu_item["identifier"]
            db_onu = db.query(models.Onu).filter(models.Onu.identifier == identifier, models.Onu.olt_id == olt.id).first()
            if db_onu:
                current_time_wib = datetime.now(wib_timezone)
                snmp_details = onu_item["details"]
                db_onu.details_snmp = snmp_details
                db_onu.last_seen = current_time_wib
                updated_count += 1
            else:
                logger.warning(f"[Task] SNMP sync found ONU '{identifier}' but it does not exist in DB. Skipping.")

        db.commit()
        logger.info(f"[Task] SNMP sync successful for {olt.ip}. Updated {updated_count} ONUs.")
        return {"message": f"Sync complete for OLT {olt.ip} via SNMP. Updated {updated_count} ONUs."}
    except Exception as e:
        logger.error(f"[Task] Exception during SNMP sync for {olt.ip}: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()

import platform
import subprocess

@celery_app.task
def sync_all_olts_data():
    """
    Triggers Telnet/SSH and SNMP sync for all active OLTs.
    This task is intended to be run periodically by Celery Beat.
    """
    db: Session = next(get_db())
    try:
        logger.info("[Task] Starting periodic data sync for all OLTs.")
        # Fetch all OLTs that are online
        olts = db.query(models.OLT).filter(models.OLT.status == 'online').all()
        
        if not olts:
            logger.info("[Task] No online OLTs found to sync.")
            return {"message": "No online OLTs found to sync."}

        for olt in olts:
            logger.info(f"[Task] Queuing data sync for OLT: {olt.name} ({olt.ip})")
            # Queue the individual sync tasks
            run_ssh_telnet_sync.delay(olt.id)
            run_snmp_sync.delay(olt.id)
        
        logger.info(f"[Task] Finished queuing data sync for {len(olts)} OLTs.")
        return {"message": f"Queued data sync for {len(olts)} OLTs."}
    except Exception as e:
        logger.error(f"[Task] Error in sync_all_olts_data task: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()

@celery_app.task
def check_expired_subscriptions():
    """
    Checks for and deactivates expired subscriptions.
    """
    db: Session = next(get_db())
    try:
        now = datetime.utcnow()
        expired_subscriptions = db.query(models.Subscription).filter(
            models.Subscription.current_period_end < now,
            models.Subscription.status == 'active'
        ).all()

        if not expired_subscriptions:
            logger.info("[Task] No expired subscriptions found.")
            return {"message": "No expired subscriptions found."}

        for sub in expired_subscriptions:
            sub.status = 'expired'
            logger.info(f"[Task] Subscription for tenant {sub.tenant_id} has expired. Status set to 'expired'.")

        db.commit()
        logger.info(f"[Task] Deactivated {len(expired_subscriptions)} expired subscriptions.")
        return {"message": f"Deactivated {len(expired_subscriptions)} expired subscriptions."}
    except Exception as e:
        logger.error(f"[Task] Exception during subscription check: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task
def check_all_olts_status():
    """
    Periodically checks the status of all OLTs and updates the database.
    This task is scheduled to run via Celery Beat.
    """
    db: Session = next(get_db())
    try:
        logger.info("[Task] Running periodic OLT status check via ping...")
        olts = db.query(models.OLT).all()
        
        for olt in olts:
            ip = olt.ip
            status = "offline" # Default status
            try:
                # OS-specific ping parameters
                if platform.system().lower() == 'windows':
                    command = ['ping', '-n', '5', '-w', '2000', ip]
                else:
                    command = ['ping', '-c', '5', '-W', '2', ip]

                result = subprocess.run(command, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    status = "online"
                else:
                    logger.warning(f"[Task] Ping failed for {ip}. Return code: {result.returncode}, Stderr: {result.stderr}")
            
            except subprocess.TimeoutExpired:
                logger.error(f"[Task] Ping command timed out for OLT {ip}")
            except Exception as ping_exc:
                logger.error(f"[Task] An exception occurred during ping check for {ip}: {ping_exc}", exc_info=True)

            if olt.status != status:
                logger.info(f"[Task] OLT {olt.name} ({olt.ip}) status changed from '{olt.status}' to '{status}'.")
                olt.status = status
            
            olt.last_checked = datetime.utcnow()
            db.add(olt)
        
        db.commit()
        logger.info(f"[Task] Finished OLT status check. Checked {len(olts)} OLTs.")
        return {"message": f"Checked {len(olts)} OLTs."}
        
    except Exception as e:
        logger.error(f"[Task] Error in OLT status checker task: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
