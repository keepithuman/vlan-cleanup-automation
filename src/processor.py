"""
Main VLAN cleanup automation processor.
"""
import logging
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .models import DeviceInfo, ProcessingResult, BusinessMetrics
from .config import ConfigManager
from .device_handler import DeviceHandler

logger = logging.getLogger(__name__)


class VLANCleanupProcessor:
    """Main processor for VLAN cleanup automation."""
    
    def __init__(self, config_file: str = "config.yaml", dry_run: bool = True):
        """Initialize the VLAN cleanup processor."""
        self.config_manager = ConfigManager(config_file)
        self.device_handler = DeviceHandler(self.config_manager)
        self.dry_run = dry_run
        self.results = []
        
        # Validate configuration
        if not self.config_manager.validate_config():
            raise ValueError("Invalid configuration")
        
        processing_config = self.config_manager.get_processing_config()
        self.max_concurrent_devices = processing_config.get('max_concurrent_devices', 5)
        
        logger.info(f"Initialized VLAN Cleanup Processor (dry_run={dry_run})")
    
    def process_single_device(self, device_info: Dict[str, Any]) -> ProcessingResult:
        """Process a single device for VLAN cleanup."""
        start_time = time.time()
        device = DeviceInfo(**device_info)
        
        try:
            # Connect to device
            connection = self.device_handler.connect_to_device(device_info)
            if not connection:
                return ProcessingResult(
                    device=device,
                    total_vlans=0,
                    unused_vlans=[],
                    removal_commands=[],
                    rollback_commands=[],
                    processing_time=time.time() - start_time,
                    status="failed",
                    error_message="Failed to connect to device"
                )
            
            # Get device type
            device_type = self.device_handler.get_device_type(device_info)
            
            # Get VLAN information
            all_vlans = self.device_handler.get_vlan_info(connection, device_type)
            
            # Filter unused VLANs
            unused_vlans = [vlan for vlan in all_vlans if vlan.is_unused]
            
            # Generate removal commands
            removal_commands = [vlan.removal_command for vlan in unused_vlans if vlan.removal_command]
            
            # Generate rollback commands
            rollback_commands = self.device_handler.generate_rollback_commands(device_type, unused_vlans)
            
            # Close connection
            connection.disconnect()
            
            # Create result
            result = ProcessingResult(
                device=device,
                total_vlans=len(all_vlans),
                unused_vlans=unused_vlans,
                removal_commands=removal_commands,
                rollback_commands=rollback_commands,
                processing_time=time.time() - start_time,
                status="success"
            )
            
            # Add warnings for high-risk VLANs
            for vlan in unused_vlans:
                if vlan.risk_level in ['high', 'critical']:
                    result.warnings.append(f"VLAN {vlan.vlan_id} ({vlan.name}) is marked as {vlan.risk_level} risk")
            
            logger.info(f"Successfully processed {device.hostname}: {len(unused_vlans)} unused VLANs found")
            return result
            
        except Exception as e:
            logger.error(f"Error processing device {device.hostname}: {str(e)}")
            return ProcessingResult(
                device=device,
                total_vlans=0,
                unused_vlans=[],
                removal_commands=[],
                rollback_commands=[],
                processing_time=time.time() - start_time,
                status="failed",
                error_message=str(e)
            )
    
    def process_devices(self, device_list: Optional[List[Dict[str, Any]]] = None) -> List[ProcessingResult]:
        """Process multiple devices concurrently."""
        devices = device_list or self.config_manager.get_devices()
        
        if not devices:
            logger.error("No devices specified for processing")
            return []
        
        logger.info(f"Starting processing of {len(devices)} devices")
        results = []
        
        # Process devices concurrently
        with ThreadPoolExecutor(max_workers=self.max_concurrent_devices) as executor:
            # Submit all tasks
            future_to_device = {
                executor.submit(self.process_single_device, device): device 
                for device in devices
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing device {device.get('hostname', 'unknown')}: {str(e)}")
                    # Create failed result
                    results.append(ProcessingResult(
                        device=DeviceInfo(**device),
                        total_vlans=0,
                        unused_vlans=[],
                        removal_commands=[],
                        rollback_commands=[],
                        processing_time=0,
                        status="failed",
                        error_message=str(e)
                    ))
        
        self.results = results
        logger.info(f"Completed processing {len(results)} devices")
        return results
    
    def calculate_business_metrics(self) -> BusinessMetrics:
        """Calculate business impact metrics."""
        if not self.results:
            return BusinessMetrics(0, 0, 0, 0, 0, [])
        
        # Time savings calculation
        manual_time_per_device = 30  # minutes
        automated_time_per_device = 2  # minutes
        successful_devices = len([r for r in self.results if r.status == "success"])
        time_saved_minutes = (manual_time_per_device - automated_time_per_device) * successful_devices
        
        # Cost calculation ($2 per minute of engineer time)
        cost_savings = time_saved_minutes * 2
        
        # VLAN cleanup count
        total_vlans_cleaned = sum(len(r.unused_vlans) for r in self.results)
        
        operational_benefits = [
            "Reduced security attack surface through VLAN cleanup",
            "Improved network performance by removing unused broadcast domains",
            "Enhanced compliance posture with clean network configurations",
            "Simplified troubleshooting with cleaner VLAN database",
            "Reduced management overhead for network operations",
            "Better documentation accuracy for network inventory"
        ]
        
        return BusinessMetrics(
            time_saved_minutes=time_saved_minutes,
            time_saved_hours=round(time_saved_minutes / 60, 2),
            estimated_cost_savings_usd=cost_savings,
            devices_processed=successful_devices,
            vlans_cleaned=total_vlans_cleaned,
            operational_benefits=operational_benefits
        )
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis results."""
        recommendations = []
        
        if not self.results:
            return ["No processing results available for recommendations"]
        
        # Check for high-risk VLANs
        high_risk_count = sum(1 for result in self.results for vlan in result.unused_vlans 
                             if vlan.risk_level in ['high', 'critical'])
        
        if high_risk_count > 0:
            recommendations.append(f"Manual review required for {high_risk_count} high/critical risk VLANs before removal")
        
        # Check for failed devices
        failed_count = len([r for r in self.results if r.status == "failed"])
        if failed_count > 0:
            recommendations.append(f"Investigate connection issues for {failed_count} failed devices")
        
        # Calculate cleanup percentage
        total_vlans = sum(r.total_vlans for r in self.results)
        unused_vlans = sum(len(r.unused_vlans) for r in self.results)
        cleanup_percentage = (unused_vlans / total_vlans * 100) if total_vlans > 0 else 0
        
        if cleanup_percentage > 20:
            recommendations.append("High percentage of unused VLANs detected - consider implementing VLAN lifecycle management")
        
        # General operational recommendations
        recommendations.extend([
            "Implement regular VLAN cleanup cycles (monthly/quarterly)",
            "Establish VLAN naming conventions to improve identification",
            "Create approval workflows for VLAN changes",
            "Consider implementing automated VLAN provisioning with lifecycle management",
            "Document VLAN usage and ownership for better governance"
        ])
        
        return recommendations
    
    def execute_cleanup(self, approve_all: bool = False) -> bool:
        """Execute the actual VLAN cleanup (production mode only)."""
        if self.dry_run:
            logger.warning("Cannot execute cleanup in dry-run mode")
            return False
        
        if not self.results:
            logger.error("No results available for cleanup execution")
            return False
        
        logger.info("Starting VLAN cleanup execution")
        
        execution_results = []
        for result in self.results:
            if result.status != "success" or not result.unused_vlans:
                continue
            
            # Filter out high-risk VLANs unless approved
            vlans_to_remove = []
            for vlan in result.unused_vlans:
                if vlan.risk_level in ['high', 'critical'] and not approve_all:
                    logger.warning(f"Skipping high-risk VLAN {vlan.vlan_id} on {result.device.hostname}")
                    continue
                vlans_to_remove.append(vlan)
            
            if not vlans_to_remove:
                continue
            
            # Execute cleanup on device
            success = self._execute_device_cleanup(result.device, vlans_to_remove)
            execution_results.append(success)
        
        success_count = sum(execution_results)
        logger.info(f"VLAN cleanup execution completed: {success_count}/{len(execution_results)} devices successful")
        return all(execution_results)
    
    def _execute_device_cleanup(self, device: DeviceInfo, vlans_to_remove: List) -> bool:
        """Execute cleanup on a single device."""
        try:
            # Connect to device
            connection = self.device_handler.connect_to_device(device.to_dict())
            if not connection:
                logger.error(f"Failed to connect to {device.hostname} for cleanup")
                return False
            
            # Execute removal commands
            for vlan in vlans_to_remove:
                if vlan.removal_command:
                    logger.info(f"Removing VLAN {vlan.vlan_id} from {device.hostname}")
                    connection.send_config_set([vlan.removal_command])
            
            # Save configuration
            if device.vendor.lower() == 'cisco':
                connection.send_command("write memory")
            elif device.vendor.lower() == 'arista':
                connection.send_command("write memory")
            elif device.vendor.lower() == 'juniper':
                connection.send_command("commit")
            
            connection.disconnect()
            logger.info(f"Successfully cleaned up {len(vlans_to_remove)} VLANs on {device.hostname}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing cleanup on {device.hostname}: {str(e)}")
            return False
