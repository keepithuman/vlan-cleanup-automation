"""
Unit tests for configuration module.
"""
import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

from src.config import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def test_init_with_existing_config(self, temp_config_file):
        """Test ConfigManager initialization with existing config file."""
        config_manager = ConfigManager(temp_config_file)
        
        assert config_manager.config_file == temp_config_file
        assert 'devices' in config_manager.config
        assert 'authentication' in config_manager.config
        assert len(config_manager.config['devices']) == 1
        assert config_manager.config['devices'][0]['hostname'] == 'test-switch-01'
    
    def test_init_with_missing_config(self):
        """Test ConfigManager initialization with missing config file."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            config_manager = ConfigManager('nonexistent.yaml')
            
            # Should use default config
            assert 'devices' in config_manager.config
            assert 'authentication' in config_manager.config
            assert config_manager.config['devices'] == []
    
    def test_init_with_invalid_yaml(self):
        """Test ConfigManager initialization with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with pytest.raises(yaml.YAMLError):
                ConfigManager('invalid.yaml')
    
    def test_get_default_config(self):
        """Test default configuration generation."""
        config_manager = ConfigManager.__new__(ConfigManager)
        default_config = config_manager._get_default_config()
        
        # Check required sections
        assert 'devices' in default_config
        assert 'authentication' in default_config
        assert 'vlan_analysis' in default_config
        assert 'processing' in default_config
        assert 'output' in default_config
        assert 'logging' in default_config
        assert 'security' in default_config
        
        # Check default values
        assert default_config['devices'] == []
        assert default_config['processing']['max_concurrent_devices'] == 5
        assert default_config['vlan_analysis']['require_manual_approval'] is True
    
    @patch.dict(os.environ, {'NETWORK_USERNAME': 'env_user', 'NETWORK_PASSWORD': 'env_pass'})
    def test_environment_variable_usage(self):
        """Test that environment variables are used in default config."""
        config_manager = ConfigManager.__new__(ConfigManager)
        default_config = config_manager._get_default_config()
        
        assert default_config['authentication']['username'] == 'env_user'
        assert default_config['authentication']['password'] == 'env_pass'
    
    def test_get_config_methods(self, config_manager):
        """Test various get_config methods."""
        # Test get_config without key (returns full config)
        full_config = config_manager.get_config()
        assert 'devices' in full_config
        assert 'authentication' in full_config
        
        # Test get_config with key
        devices = config_manager.get_config('devices')
        assert isinstance(devices, list)
        assert len(devices) == 1
        
        # Test specific getter methods
        devices = config_manager.get_devices()
        assert isinstance(devices, list)
        assert len(devices) == 1
        assert devices[0]['hostname'] == 'test-switch-01'
        
        auth = config_manager.get_authentication()
        assert isinstance(auth, dict)
        assert 'username' in auth
        assert 'password' in auth
        
        vlan_config = config_manager.get_vlan_analysis_config()
        assert isinstance(vlan_config, dict)
        assert 'exclude_vlans' in vlan_config
        
        processing_config = config_manager.get_processing_config()
        assert isinstance(processing_config, dict)
        assert 'max_concurrent_devices' in processing_config
        
        output_config = config_manager.get_output_config()
        assert isinstance(output_config, dict)
    
    def test_validate_config_success(self, config_manager):
        """Test successful configuration validation."""
        assert config_manager.validate_config() is True
    
    def test_validate_config_missing_sections(self):
        """Test configuration validation with missing sections."""
        incomplete_config = {'devices': []}
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(incomplete_config))):
            config_manager = ConfigManager('test.yaml')
            assert config_manager.validate_config() is False
    
    def test_validate_config_missing_device_fields(self):
        """Test configuration validation with incomplete device info."""
        config_data = {
            'devices': [
                {'hostname': 'test-switch'}  # missing required fields
            ],
            'authentication': {
                'username': 'test'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):
            config_manager = ConfigManager('test.yaml')
            assert config_manager.validate_config() is False
    
    def test_validate_config_no_username(self):
        """Test configuration validation with missing username."""
        config_data = {
            'devices': [
                {
                    'hostname': 'test-switch',
                    'ip_address': '192.168.1.1',
                    'vendor': 'cisco'
                }
            ],
            'authentication': {}
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):
            config_manager = ConfigManager('test.yaml')
            assert config_manager.validate_config() is False
    
    def test_validate_config_no_devices(self):
        """Test configuration validation with no devices."""
        config_data = {
            'devices': [],
            'authentication': {
                'username': 'test'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):
            config_manager = ConfigManager('test.yaml')
            assert config_manager.validate_config() is False
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_save_config_success(self, mock_yaml_dump, mock_file, config_manager):
        """Test successful configuration save."""
        test_config = {'test': 'config'}
        
        result = config_manager.save_config(test_config)
        
        assert result is True
        mock_file.assert_called_once_with(config_manager.config_file, 'w')
        mock_yaml_dump.assert_called_once_with(test_config, mock_file(), default_flow_style=False, indent=2)
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_config_failure(self, mock_file, config_manager):
        """Test configuration save failure."""
        test_config = {'test': 'config'}
        
        result = config_manager.save_config(test_config)
        
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_save_config_default(self, mock_yaml_dump, mock_file, config_manager):
        """Test saving current config when no config_data provided."""
        result = config_manager.save_config()
        
        assert result is True
        mock_yaml_dump.assert_called_once_with(config_manager.config, mock_file(), default_flow_style=False, indent=2)


class TestConfigManagerEncryption:
    """Test cases for ConfigManager encryption functionality."""
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.chmod')
    def test_encryption_key_generation(self, mock_chmod, mock_file, mock_exists):
        """Test encryption key generation for new installations."""
        mock_exists.return_value = False
        
        with patch('src.config.Fernet.generate_key') as mock_generate:
            mock_generate.return_value = b'fake_key_data'
            
            config_manager = ConfigManager.__new__(ConfigManager)
            encryption_key = config_manager._get_encryption_key()
            
            # Should generate new key
            mock_generate.assert_called_once()
            # Should write key to file
            mock_file.assert_called()
            # Should set restrictive permissions
            mock_chmod.assert_called_once()
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b'existing_key')
    def test_encryption_key_loading(self, mock_file, mock_exists):
        """Test loading existing encryption key."""
        mock_exists.return_value = True
        
        config_manager = ConfigManager.__new__(ConfigManager)
        encryption_key = config_manager._get_encryption_key()
        
        # Should read existing key
        mock_file.assert_called()
    
    def test_encrypt_decrypt_data(self, temp_config_file):
        """Test data encryption and decryption."""
        config_manager = ConfigManager(temp_config_file)
        
        test_data = "sensitive_password"
        encrypted = config_manager.encrypt_sensitive_data(test_data)
        decrypted = config_manager.decrypt_sensitive_data(encrypted)
        
        assert encrypted != test_data  # Should be encrypted
        assert decrypted == test_data  # Should decrypt back to original
        assert isinstance(encrypted, str)
        assert isinstance(decrypted, str)


class TestConfigManagerConstants:
    """Test cases for ConfigManager constants and class variables."""
    
    def test_reserved_vlans_constant(self):
        """Test RESERVED_VLANS constant."""
        assert hasattr(ConfigManager, 'RESERVED_VLANS')
        assert isinstance(ConfigManager.RESERVED_VLANS, set)
        assert 1 in ConfigManager.RESERVED_VLANS
        assert 1002 in ConfigManager.RESERVED_VLANS
    
    def test_critical_vlan_names_constant(self):
        """Test CRITICAL_VLAN_NAMES constant."""
        assert hasattr(ConfigManager, 'CRITICAL_VLAN_NAMES')
        assert isinstance(ConfigManager.CRITICAL_VLAN_NAMES, list)
        assert 'management' in ConfigManager.CRITICAL_VLAN_NAMES
        assert 'voice' in ConfigManager.CRITICAL_VLAN_NAMES
