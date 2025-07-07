"""
Data models for VLAN cleanup automation.
"""
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class VLANInfo:
    """Data class to store VLAN information."""
    vlan_id: int
    name: str
    status: str
    ports: List[str]
    is_unused: bool = False
    removal_command: str = ""
    risk_level: str = "low"  # low, medium, high, critical
    last_seen: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DeviceInfo:
    """Data class to store device information."""
    hostname: str
    ip_address: str
    device_type: str
    vendor: str
    model: str = ""
    version: str = ""
    management_ip: str = ""
    ssh_key_file: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ProcessingResult:
    """Data class to store processing results."""
    device: DeviceInfo
    total_vlans: int
    unused_vlans: List[VLANInfo]
    removal_commands: List[str]
    rollback_commands: List[str]
    processing_time: float
    status: str
    error_message: str = ""
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['device'] = self.device.to_dict()
        result['unused_vlans'] = [vlan.to_dict() for vlan in self.unused_vlans]
        return result


@dataclass
class BusinessMetrics:
    """Data class for business impact metrics."""
    time_saved_minutes: float
    time_saved_hours: float
    estimated_cost_savings_usd: float
    devices_processed: int
    vlans_cleaned: int
    operational_benefits: List[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
