"""
Example usage of the Update Client

Demonstrates how to integrate update checking into the application.
"""
import asyncio
import logging
from client.core.update_client import UpdateClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_and_apply_updates_example():
    """
    Example: Check for updates and apply them.
    
    This would typically be called:
    - On app startup (background check)
    - From a "Check for Updates" menu item
    - Periodically in the background
    """
    
    # Initialize update client
    server_url = "https://your-server.com"  # Replace with actual server URL
    license_key = "IW-123456-ABCD1234"  # Replace with actual license key
    
    client = UpdateClient(server_url, license_key)
    
    # Check for updates
    logger.info("Checking for updates...")
    manifest = await client.check_for_updates()
    
    if not manifest:
        logger.error("Failed to check for updates")
        return
    
    # Check if there are any updates
    if manifest.has_updates(client.local_manifest):
        logger.info(f"Updates available: {len(manifest.presets)} presets, {len(manifest.estimators)} estimators")
        
        # Apply all updates
        results = await client.apply_all_updates(manifest)
        
        logger.info(f"Update complete:")
        logger.info(f"  - Presets updated: {results['presets_updated']}")
        logger.info(f"  - Estimators updated: {results['estimators_updated']}")
        
        if results['errors']:
            logger.warning(f"  - Errors: {len(results['errors'])}")
            for error in results['errors']:
                logger.warning(f"    - {error}")
        
        # After updates, reload managers
        # preset_manager.reload()  # Reload presets
        # estimator_registry.reload()  # Reload estimators
        
        return results
    else:
        logger.info("No updates available")
        return None


async def check_updates_only_example():
    """
    Example: Just check if updates are available without applying.
    
    Useful for showing a notification to the user.
    """
    server_url = "https://your-server.com"
    license_key = "IW-123456-ABCD1234"
    
    client = UpdateClient(server_url, license_key)
    manifest = await client.check_for_updates()
    
    if manifest and manifest.has_updates(client.local_manifest):
        # Count updates
        preset_updates = sum(
            1 for p in manifest.presets
            if client.local_manifest.get_preset_version(p['id']) != p['version']
        )
        estimator_updates = sum(
            1 for e in manifest.estimators
            if client.local_manifest.get_estimator_version(e['id']) != e['version']
        )
        
        logger.info(f"Updates available: {preset_updates} presets, {estimator_updates} estimators")
        return True
    else:
        logger.info("No updates available")
        return False


async def apply_specific_update_example():
    """
    Example: Apply only a specific preset or estimator update.
    
    Useful for selective updates or manual update management.
    """
    server_url = "https://your-server.com"
    license_key = "IW-123456-ABCD1234"
    
    client = UpdateClient(server_url, license_key)
    
    # Download and apply specific preset
    preset_id = "example_update_preset"
    content = await client.download_preset(preset_id)
    
    if content:
        success = await client.apply_preset_update(preset_id, content, subdir="utilities")
        if success:
            client.local_manifest.update_preset_version(preset_id, "1.1")
            logger.info(f"Successfully updated preset: {preset_id}")
        else:
            logger.error(f"Failed to apply preset: {preset_id}")


if __name__ == "__main__":
    # Run the example
    asyncio.run(check_and_apply_updates_example())
