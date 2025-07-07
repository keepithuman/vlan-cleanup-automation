"""
Device connection and communication handlers.
"""
import logging
import time
from typing import Dict, Any, Optional, List
from netmiko import ConnectHandler
from .models import DeviceInfo, VLANInfo

logger = logging.getLogger(__name__)


class DeviceHandler:
    """Base class for device handlers."""
    
    DEVICE_TYPE_MAPPING = {
        'cisco_ios': ['cisco', 'ios'],
        'cisco_xe': ['cisco_xe', 'iosxe'],
        'cisco_nxos': ['cisco_nxos', 'nxos', 'nexus'],
        'arista_eos': ['arista', 'eos'],
        'juniper_junos': ['juniper', 'junos']
    }
    
    def __init__(self, config_manager):
        """Initialize device handler."""
        self.config_manager = config_manager
        self.processing_config = config_manager.get_processing_config()
        self.auth_config = config_manager.get_authentication()
    
    def get_device_type(self, device_info: Dict[str, Any]) -> str:
        """Determine netmiko device type from device information."""
        vendor = device_info.get('vendor', '').lower()
        model = device_info.get('model', '').lower()
        device_type = device_info.get('device_type', '').lower()
        
        for netmiko_type, keywords in self.DEVICE_TYPE_MAPPING.items():
            if any(keyword in vendor or keyword in model or keyword in device_type 
                   for keyword in keywords):
                return netmiko_type
        
        # Default fallback based on vendor
        if 'cisco' in vendor:
            return 'cisco_ios'
        elif 'arista' in vendor:
            return 'arista_eos'
        elif 'juniper' in vendor:
            return 'juniper_junos'
        
        logger.warning(f"Unknown device type for {device_info.get('hostname', 'unknown')}")
        return 'cisco_ios'  # Conservative fallback
    
    def connect_to_device(self, device_info: Dict[str, Any]) -> Optional[ConnectHandler]:
        """Establish connection to network device with retry logic."""
        retries = self.processing_config.get('connection_retries', 3)
        retry_delay = self.processing_config.get('retry_delay', 5)
        
        for attempt in range(retries):
            try:
                device_params = {
                    'device_type': self.get_device_type(device_info),
                    'host': device_info['ip_address'],
                    'username': self.auth_config['username'],
                    'password': self.auth_config['password'],
                    'timeout': self.processing_config.get('device_timeout', 60),
                    'global_delay_factor': 2,
                    'banner_timeout': 20,
                    'conn_timeout': 10
                }
                
                # Add enable password if specified
                if self.auth_config.get('enable_password'):
                    device_params['secret'] = self.auth_config['enable_password']
                
                # Add SSH key if specified
                if device_info.get('ssh_key_file'):
                    device_params['use_keys'] = True
                    device_params['key_file'] = device_info['ssh_key_file']
                
                connection = ConnectHandler(**device_params)
                connection.enable()  # Enter enable mode
                
                logger.info(f"Successfully connected to {device_info['hostname']}")
                return connection
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed for {device_info['hostname']}: {str(e)}")
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Failed to connect to {device_info['hostname']} after {retries} attempts")
                    return None
    
    def get_vlan_info(self, connection: ConnectHandler, device_type: str) -> List[VLANInfo]:
        """Get VLAN information from device based on vendor."""
        if device_type.startswith('cisco'):
            return self._get_cisco_vlans(connection)
        elif device_type.startswith('arista'):
            return self._get_arista_vlans(connection)
        elif device_type.startswith('juniper'):
            return self._get_juniper_vlans(connection)
        else:
            raise ValueError(f"Unsupported device type: {device_type}")
    
    def _get_cisco_vlans(self, connection: ConnectHandler) -> List[VLANInfo]:
        """Get VLAN information from Cisco devices."""
        vlans = []
        
        try:
            vlan_output = connection.send_command("show vlan brief")
            
            for line in vlan_output.split('\n'):
                if line.strip() and not line.startswith('VLAN') and not line.startswith('----'):
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].isdigit():
                        vlan_id = int(parts[0])
                        vlan_name = parts[1]
                        status = parts[2] if len(parts) > 2 else 'active'
                        ports_str = ' '.join(parts[3:]) if len(parts) > 3 else ''
                        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                        
                        is_unused = self._is_vlan_unused_cisco(connection, vlan_id, ports)
                        
                        vlan_info = VLANInfo(
                            vlan_id=vlan_id,
                            name=vlan_name,
                            status=status,
                            ports=ports,
                            is_unused=is_unused
                        )
                        
                        if is_unused:
                            vlan_info.removal_command = f"no vlan {vlan_id}"
                            vlan_info.risk_level = self._assess_risk_level(vlan_info)
                        
                        vlans.append(vlan_info)
            
        except Exception as e:
            logger.error(f"Error getting VLAN info from Cisco device: {str(e)}")
        
        return vlans
    
    def _get_arista_vlans(self, connection: ConnectHandler) -> List[VLANInfo]:
        """Get VLAN information from Arista devices."""
        vlans = []
        
        try:
            vlan_output = connection.send_command("show vlan")
            
            for line in vlan_output.split('\n'):
                if line.strip() and line[0].isdigit():
                    parts = line.split()
                    if len(parts) >= 2:
                        vlan_id = int(parts[0])
                        vlan_name = parts[1]
                        status = parts[2] if len(parts) > 2 else 'active'
                        ports_str = ' '.join(parts[3:]) if len(parts) > 3 else ''
                        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                        
                        is_unused = self._is_vlan_unused_arista(connection, vlan_id, ports)
                        
                        vlan_info = VLANInfo(
                            vlan_id=vlan_id,
                            name=vlan_name,
                            status=status,
                            ports=ports,
                            is_unused=is_unused
                        )
                        
                        if is_unused:
                            vlan_info.removal_command = f"no vlan {vlan_id}"
                            vlan_info.risk_level = self._assess_risk_level(vlan_info)
                        
                        vlans.append(vlan_info)
            
        except Exception as e:
            logger.error(f"Error getting VLAN info from Arista device: {str(e)}")
        
        return vlans
    
    def _get_juniper_vlans(self, connection: ConnectHandler) -> List[VLANInfo]:
        """Get VLAN information from Juniper devices."""
        vlans = []
        
        try:
            vlan_output = connection.send_command("show vlans")
            
            for line in vlan_output.split('\n'):
                if 'VLAN' in line and line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        vlan_name = parts[0]
                        vlan_id_str = parts[1] if len(parts) > 1 else ''
                        
                        if vlan_id_str.isdigit():
                            vlan_id = int(vlan_id_str)
                        else:
                            continue
                        
                        interfaces_str = ' '.join(parts[2:]) if len(parts) > 2 else ''
                        interfaces = [i.strip() for i in interfaces_str.split(',') if i.strip()]
                        
                        is_unused = self._is_vlan_unused_juniper(connection, vlan_id, interfaces)
                        
                        vlan_info = VLANInfo(
                            vlan_id=vlan_id,
                            name=vlan_name,
                            status='active',
                            ports=interfaces,
                            is_unused=is_unused
                        )
                        
                        if is_unused:
                            vlan_info.removal_command = f"delete vlans {vlan_name}"
                            vlan_info.risk_level = self._assess_risk_level(vlan_info)
                        
                        vlans.append(vlan_info)
            
        except Exception as e:
            logger.error(f"Error getting VLAN info from Juniper device: {str(e)}")
        
        return vlans
    
    def _is_vlan_unused_cisco(self, connection: ConnectHandler, vlan_id: int, ports: List[str]) -> bool:
        """Check if VLAN is unused on Cisco devices."""
        try:
            # Check reserved VLANs
            if vlan_id in self.config_manager.RESERVED_VLANS:
                return False
            
            # Check active ports
            if ports and any(port.strip() for port in ports):
                return False
            
            # Check SVI interfaces
            try:
                svi_output = connection.send_command(f"show interface vlan {vlan_id}")
                if "up" in svi_output.lower() and "line protocol is up" in svi_output.lower():
                    return False
            except:
                pass  # SVI might not exist
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking VLAN {vlan_id} usage: {str(e)}")
            return False  # Conservative approach
    
    def _is_vlan_unused_arista(self, connection: ConnectHandler, vlan_id: int, ports: List[str]) -> bool:
        """Check if VLAN is unused on Arista devices."""
        try:
            if vlan_id in self.config_manager.RESERVED_VLANS:
                return False
            
            if ports and any(port.strip() for port in ports):
                return False
            
            try:
                svi_output = connection.send_command(f"show interface vlan {vlan_id}")
                if "up" in svi_output.lower():
                    return False
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking VLAN {vlan_id} usage: {str(e)}")
            return False
    
    def _is_vlan_unused_juniper(self, connection: ConnectHandler, vlan_id: int, interfaces: List[str]) -> bool:
        """Check if VLAN is unused on Juniper devices."""
        try:
            if vlan_id in self.config_manager.RESERVED_VLANS:
                return False
            
            if interfaces and any(intf.strip() for intf in interfaces):
                return False
            
            try:
                irb_output = connection.send_command(f"show interfaces irb.{vlan_id}")
                if "up" in irb_output.lower():
                    return False
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking VLAN {vlan_id} usage: {str(e)}")
            return False
    
    def _assess_risk_level(self, vlan_info: VLANInfo) -> str:
        """Assess the risk level of removing a VLAN."""
        risk_level = "low"
        
        # Check critical VLAN names
        critical_names = self.config_manager.get_vlan_analysis_config().get('critical_vlan_names', [])
        if any(critical_name in vlan_info.name.lower() for critical_name in critical_names):
            risk_level = "critical"
        
        # Check management VLANs
        elif vlan_info.vlan_id in range(1, 10):
            risk_level = "high"
        
        # Check common voice VLAN ranges
        elif vlan_info.vlan_id in range(100, 200):
            risk_level = "medium"
        
        return risk_level
    
    def generate_rollback_commands(self, device_type: str, unused_vlans: List[VLANInfo]) -> List[str]:
        """Generate rollback commands for removed VLANs."""
        rollback_commands = []
        
        for vlan in unused_vlans:
            if device_type.startswith('cisco'):
                rollback_commands.append(f"vlan {vlan.vlan_id}")
                rollback_commands.append(f" name {vlan.name}")
            elif device_type.startswith('arista'):
                rollback_commands.append(f"vlan {vlan.vlan_id}")
                rollback_commands.append(f" name {vlan.name}")
            elif device_type.startswith('juniper'):
                rollback_commands.append(f"set vlans {vlan.name} vlan-id {vlan.vlan_id}")
        
        return rollback_commands
