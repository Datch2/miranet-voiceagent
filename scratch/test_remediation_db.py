import asyncio
import sys
import pathlib

# Add project root to sys.path
sys.path.append("D:/miranet-voiceagent")

from backend.db.database import db
from backend.utils.remediation import RemediationController

async def test():
    print("Connecting to database...")
    await db.connect()
    
    # 1. Reset Diego Torres's Router SN: RT000001 (Norte Zone 1) to failure status first to simulate outage
    print("\n[Step 1] Seeding failure status for RT000001 (Zone 1) in database...")
    await db._execute("UPDATE equipos_red SET cpu_usage = 88.0, packet_loss = 4.5, interface_status = 'up' WHERE zona_id = 1;", ())
    await db._execute("UPDATE zonas SET estado = 'falla_individual' WHERE id = 1;", ())
        
    # Verify current state
    client = await db.get_client_by_identifier("RouterSN", "RT000001")
    net_status = await db.get_network_status_by_zone(1)
    print(f"Pre-Remediation State: Zone State = {net_status['estado']}, Router CPU = {net_status['cpu_usage']}%, Loss = {net_status['packet_loss']}%")
    
    # 2. Run apply_qos_profile simulation on RT000001
    print("\n[Step 2] Executing apply_qos_profile('RT000001') via RemediationController...")
    res = await RemediationController.apply_qos_profile("RT000001", profile_speed_mbps=150)
    print(f"Result: {res}")
    
    # Verify updated state
    net_status_post = await db.get_network_status_by_zone(1)
    print(f"Post-Remediation State: Zone State = {net_status_post['estado']}, Router CPU = {net_status_post['cpu_usage']}%, Loss = {net_status_post['packet_loss']}%")
    
    success = (net_status_post['estado'] == 'operativo' and net_status_post['packet_loss'] == 0.0)
    print(f"\nVerification Success: {success}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
