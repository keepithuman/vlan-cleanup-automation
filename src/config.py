"""
Configuration management for VLAN cleanup automation.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for VLAN cleanup automation."""
    
    RESERVED_VLANS = {1, 1002, 1003, 1004, 1005}
    CRITICAL_VLAN_NAMES = ['management', 'mgmt', 'native', 'default', 'voice', 'data']
    
    def __init__(self, config_file: str = "config.yaml"):
        """Initialize configuration manager."""
        self.config_file = config_file
        self.config = self._load_config()
        self.encryption_key = self._get_encryption_key()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.warning(f"Configuration file {self.config_file} not found, using defaults")
            return self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            'devices': [],
            'authentication': {
                'username': os.getenv('NETWORK_USERNAME', ''),
                'password': os.getenv('NETWORK_PASSWORD', ''),
                'enable_password': os.getenv('NETWORK_ENABLE_PASSWORD', '')
            },
            'vlan_analysis': {
                'exclude_vlans': list(self.RESERVED_VLANS),
                'minimum_age_days': 30,
                'require_manual_approval': True,
                'critical_vlan_names': list(self.CRITICAL_VLAN_NAMES)
            },
            'processing': {
                'max_concurrent_devices': 5,
                'device_timeout': 60,
                'connection_retries': 3,
                'retry_delay': 5
            },
            'output': {
                'format': 'json',
                'file': 'vlan_cleanup_results.json',
                'backup_commands': True,
                'generate_rollback': True
            },
            'logging': {
                'level': 'INFO',
                'file': 'vlan_cleanup.log',
                'max_size_mb': 10,
                'backup_count': 5
            },
            'security': {
                'encrypt_credentials': True,
                'audit_trail': True,
                'require_approval_for_critical': True
            }
        }
    
    def _get_encryption_key(self) -> Fernet:
        """Get or generate encryption key for sensitive data."""
        key_file = Path('.encryption_key')
        if key_file.exists():
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
        return Fernet(key)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return self.encryption_key.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return self.encryption_key.decrypt(encrypted_data.encode()).decode()
    
    def get_config(self, key: str = None) -> Any:
        """Get configuration value."""
        if key:
            return self.config.get(key)
        return self.config
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get device list from configuration."""
        return self.config.get('devices', [])
    
    def get_authentication(self) -> Dict[str, str]:
        """Get authentication configuration."""
        return self.config.get('authentication', {})
    
    def get_vlan_analysis_config(self) -> Dict[str, Any]:
        """Get VLAN analysis configuration."""
        return self.config.get('vlan_analysis', {})
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return self.config.get('processing', {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.config.get('output', {})
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        required_sections = ['devices', 'authentication']
        
        for section in required_sections:
            if section not in self.config:
                logger.error(f"Missing required configuration section: {section}")
                return False
        
        # Validate devices
        devices = self.get_devices()
        if not devices:
            logger.warning("No devices configured")
            return False
        
        for device in devices:
            required_fields = ['hostname', 'ip_address', 'vendor']
            for field in required_fields:
                if field not in device:
                    logger.error(f"Device missing required field: {field}")
                    return False
        
        # Validate authentication
        auth = self.get_authentication()
        if not auth.get('username'):
            logger.error("No username configured")
            return False
        
        return True
    
    def save_config(self, config_data: Dict[str, Any] = None) -> bool:
        """Save configuration to file."""
        try:
            data_to_save = config_data if config_data else self.config
            with open(self.config_file, 'w') as f:
                yaml.dump(data_to_save, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
