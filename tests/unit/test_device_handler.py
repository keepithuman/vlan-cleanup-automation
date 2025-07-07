"""
Unit tests for device handler module.
"""
import pytest
from unittest.mock import MagicMock, patch, call
import time

from src.device_handler import DeviceHandler
from src.models import VLANInfo


class TestDeviceHandler:
    """Test cases for DeviceHandler class."""
    
    def test_init(self, config_manager):
        """Test DeviceHandler initialization."""
        handler = DeviceHandler(config_manager)
        
        assert handler.config_manager == config_manager
        assert hasattr(handler, 'processing_config')
        assert hasattr(handler, 'auth_config')
        assert isinstance(handler.processing_config, dict)
        assert isinstance(handler.auth_config, dict)
    
    def test_get_device_type_cisco(self, config_manager):
        """Test device type detection for Cisco devices."""
        handler = DeviceHandler(config_manager)
        
        # Test various Cisco device configurations
        cisco_devices = [
            {'vendor': 'cisco', 'model': '', 'device_type': ''},
            {'vendor': 'Cisco', 'model': 'Catalyst 3850', 'device_type': ''},
            {'vendor': '', 'model': 'ios', 'device_type': ''},
            {'vendor': '', 'model': '', 'device_type': 'cisco_ios'},
            {'vendor': '', 'model': 'iosxe', 'device_type': ''},
            {'vendor': '', 'model': '', 'device_type': 'cisco_nxos'},
        ]
        
        for device in cisco_devices:
            device_type = handler.get_device_type(device)
            assert device_type.startswith('cisco')
    
    def test_get_device_type_arista(self, config_manager):
        """Test device type detection for Arista devices."""
        handler = DeviceHandler(config_manager)
        
        arista_devices = [
            {'vendor': 'arista', 'model': '', 'device_type': ''},
            {'vendor': 'Arista', 'model': 'DCS-7050', 'device_type': ''},
            {'vendor': '', 'model': 'eos', 'device_type': ''},
            {'vendor': '', 'model': '', 'device_type': 'arista_eos'},
        ]
        
        for device in arista_devices:
            device_type = handler.get_device_type(device)
            assert device_type == 'arista_eos'
    
    def test_get_device_type_juniper(self, config_manager):
        """Test device type detection for Juniper devices."""
        handler = DeviceHandler(config_manager)
        
        juniper_devices = [
            {'vendor': 'juniper', 'model': '', 'device_type': ''},
            {'vendor': 'Juniper', 'model': 'EX4300', 'device_type': ''},
            {'vendor': '', 'model': 'junos', 'device_type': ''},
            {'vendor': '', 'model': '', 'device_type': 'juniper_junos'},
        ]
        
        for device in juniper_devices:
            device_type = handler.get_device_type(device)
            assert device_type == 'juniper_junos'
    
    def test_get_device_type_unknown(self, config_manager):
        """Test device type detection for unknown devices."""
        handler = DeviceHandler(config_manager)
        
        unknown_device = {'vendor': 'unknown', 'model': 'unknown', 'device_type': 'unknown'}
        device_type = handler.get_device_type(unknown_device)
        assert device_type == 'cisco_ios'  # Default fallback
    
    @patch('src.device_handler.ConnectHandler')
    def test_connect_to_device_success(self, mock_connect_handler, config_manager):
        """Test successful device connection."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        mock_connect_handler.return_value = mock_connection
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = handler.connect_to_device(device_info)
        
        assert result == mock_connection
        mock_connect_handler.assert_called_once()
        mock_connection.enable.assert_called_once()
    
    @patch('src.device_handler.ConnectHandler')
    def test_connect_to_device_with_ssh_key(self, mock_connect_handler, config_manager):
        """Test device connection with SSH key."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        mock_connect_handler.return_value = mock_connection
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios',
            'ssh_key_file': '/path/to/key'
        }
        
        result = handler.connect_to_device(device_info)
        
        # Verify SSH key parameters were passed
        call_args = mock_connect_handler.call_args[1]
        assert call_args['use_keys'] is True
        assert call_args['key_file'] == '/path/to/key'
    
    @patch('src.device_handler.ConnectHandler')
    @patch('time.sleep')
    def test_connect_to_device_retry_logic(self, mock_sleep, mock_connect_handler, config_manager):
        """Test device connection retry logic."""
        handler = DeviceHandler(config_manager)
        
        # Mock connection failures then success
        mock_connect_handler.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            MagicMock()  # Success on third attempt
        ]
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = handler.connect_to_device(device_info)
        
        # Should retry and eventually succeed
        assert result is not None
        assert mock_connect_handler.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries
    
    @patch('src.device_handler.ConnectHandler')
    def test_connect_to_device_max_retries_exceeded(self, mock_connect_handler, config_manager):
        """Test device connection when max retries exceeded."""
        handler = DeviceHandler(config_manager)
        
        # Mock all connection attempts to fail
        mock_connect_handler.side_effect = Exception("Connection failed")
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = handler.connect_to_device(device_info)
        
        assert result is None
        # Should attempt connection retries times (default is 3)
        assert mock_connect_handler.call_count == 3


class TestDeviceHandlerVLANParsing:
    """Test cases for VLAN parsing functionality."""
    
    def test_get_cisco_vlans(self, config_manager, cisco_vlan_output):
        """Test parsing Cisco VLAN output."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = cisco_vlan_output
        
        # Mock the unused VLAN check to return True for specific VLANs
        with patch.object(handler, '_is_vlan_unused_cisco') as mock_unused:
            mock_unused.side_effect = lambda conn, vlan_id, ports: vlan_id in [100, 200]
            
            vlans = handler._get_cisco_vlans(mock_connection)
        
        # Should parse VLANs correctly
        assert len(vlans) > 0
        
        # Find specific VLANs
        vlan_100 = next((v for v in vlans if v.vlan_id == 100), None)
        assert vlan_100 is not None
        assert vlan_100.name == 'unused-vlan'
        assert vlan_100.is_unused is True
        assert vlan_100.removal_command == 'no vlan 100'
        
        # Check management VLAN is not marked as unused
        vlan_10 = next((v for v in vlans if v.vlan_id == 10), None)
        if vlan_10:
            assert vlan_10.is_unused is False
    
    def test_get_arista_vlans(self, config_manager, arista_vlan_output):
        """Test parsing Arista VLAN output."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = arista_vlan_output
        
        with patch.object(handler, '_is_vlan_unused_arista') as mock_unused:
            mock_unused.side_effect = lambda conn, vlan_id, ports: vlan_id in [100, 200]
            
            vlans = handler._get_arista_vlans(mock_connection)
        
        assert len(vlans) > 0
        
        vlan_100 = next((v for v in vlans if v.vlan_id == 100), None)
        assert vlan_100 is not None
        assert vlan_100.name == 'unused-vlan'
        assert vlan_100.is_unused is True
        assert vlan_100.removal_command == 'no vlan 100'
    
    def test_get_juniper_vlans(self, config_manager, juniper_vlan_output):
        """Test parsing Juniper VLAN output."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = juniper_vlan_output
        
        with patch.object(handler, '_is_vlan_unused_juniper') as mock_unused:
            mock_unused.side_effect = lambda conn, vlan_id, intfs: vlan_id in [100, 200]
            
            vlans = handler._get_juniper_vlans(mock_connection)
        
        assert len(vlans) > 0
        
        vlan_100 = next((v for v in vlans if v.vlan_id == 100), None)
        assert vlan_100 is not None
        assert vlan_100.name == 'unused-vlan'
        assert vlan_100.is_unused is True
        assert vlan_100.removal_command == 'delete vlans unused-vlan'


class TestDeviceHandlerVLANAnalysis:
    """Test cases for VLAN usage analysis."""
    
    def test_is_vlan_unused_cisco_reserved(self, config_manager):
        """Test Cisco VLAN usage check for reserved VLANs."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        # Test reserved VLAN
        is_unused = handler._is_vlan_unused_cisco(mock_connection, 1, [])
        assert is_unused is False
        
        is_unused = handler._is_vlan_unused_cisco(mock_connection, 1002, [])
        assert is_unused is False
    
    def test_is_vlan_unused_cisco_with_ports(self, config_manager):
        """Test Cisco VLAN usage check with active ports."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        # Test VLAN with active ports
        is_unused = handler._is_vlan_unused_cisco(mock_connection, 100, ['Gi1/0/1', 'Gi1/0/2'])
        assert is_unused is False
        
        # Test VLAN without ports
        mock_connection.send_command.return_value = "Interface not found"
        is_unused = handler._is_vlan_unused_cisco(mock_connection, 100, [])
        assert is_unused is True
    
    def test_is_vlan_unused_cisco_with_svi(self, config_manager):
        """Test Cisco VLAN usage check with active SVI."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        # Mock SVI interface that is up
        mock_connection.send_command.return_value = "Vlan100 is up, line protocol is up"
        
        is_unused = handler._is_vlan_unused_cisco(mock_connection, 100, [])
        assert is_unused is False
    
    def test_assess_risk_level(self, config_manager):
        """Test VLAN risk level assessment."""
        handler = DeviceHandler(config_manager)
        
        # Test critical VLAN names
        critical_vlan = VLANInfo(vlan_id=100, name='management', status='active', ports=[])
        risk = handler._assess_risk_level(critical_vlan)
        assert risk == 'critical'
        
        voice_vlan = VLANInfo(vlan_id=100, name='voice-users', status='active', ports=[])
        risk = handler._assess_risk_level(voice_vlan)
        assert risk == 'critical'
        
        # Test management VLAN range
        mgmt_vlan = VLANInfo(vlan_id=5, name='regular-vlan', status='active', ports=[])
        risk = handler._assess_risk_level(mgmt_vlan)
        assert risk == 'high'
        
        # Test voice VLAN range
        voice_range_vlan = VLANInfo(vlan_id=150, name='regular-vlan', status='active', ports=[])
        risk = handler._assess_risk_level(voice_range_vlan)
        assert risk == 'medium'
        
        # Test low risk VLAN
        low_risk_vlan = VLANInfo(vlan_id=300, name='test-vlan', status='active', ports=[])
        risk = handler._assess_risk_level(low_risk_vlan)
        assert risk == 'low'
    
    def test_generate_rollback_commands_cisco(self, config_manager):
        """Test rollback command generation for Cisco devices."""
        handler = DeviceHandler(config_manager)
        
        unused_vlans = [
            VLANInfo(vlan_id=100, name='test-vlan-1', status='active', ports=[]),
            VLANInfo(vlan_id=200, name='test-vlan-2', status='active', ports=[])
        ]
        
        commands = handler.generate_rollback_commands('cisco_ios', unused_vlans)
        
        expected_commands = [
            'vlan 100',
            ' name test-vlan-1',
            'vlan 200',
            ' name test-vlan-2'
        ]
        
        assert commands == expected_commands
    
    def test_generate_rollback_commands_arista(self, config_manager):
        """Test rollback command generation for Arista devices."""
        handler = DeviceHandler(config_manager)
        
        unused_vlans = [
            VLANInfo(vlan_id=100, name='test-vlan', status='active', ports=[])
        ]
        
        commands = handler.generate_rollback_commands('arista_eos', unused_vlans)
        
        expected_commands = [
            'vlan 100',
            ' name test-vlan'
        ]
        
        assert commands == expected_commands
    
    def test_generate_rollback_commands_juniper(self, config_manager):
        """Test rollback command generation for Juniper devices."""
        handler = DeviceHandler(config_manager)
        
        unused_vlans = [
            VLANInfo(vlan_id=100, name='test-vlan', status='active', ports=[])
        ]
        
        commands = handler.generate_rollback_commands('juniper_junos', unused_vlans)
        
        expected_commands = [
            'set vlans test-vlan vlan-id 100'
        ]
        
        assert commands == expected_commands


class TestDeviceHandlerIntegration:
    """Integration test cases for DeviceHandler."""
    
    def test_get_vlan_info_cisco_integration(self, config_manager):
        """Test complete VLAN info retrieval for Cisco devices."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        vlans = handler.get_vlan_info(mock_connection, 'cisco_ios')
        
        # Should call the correct method for Cisco
        assert isinstance(vlans, list)
    
    def test_get_vlan_info_arista_integration(self, config_manager):
        """Test complete VLAN info retrieval for Arista devices."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        vlans = handler.get_vlan_info(mock_connection, 'arista_eos')
        
        assert isinstance(vlans, list)
    
    def test_get_vlan_info_juniper_integration(self, config_manager):
        """Test complete VLAN info retrieval for Juniper devices."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        vlans = handler.get_vlan_info(mock_connection, 'juniper_junos')
        
        assert isinstance(vlans, list)
    
    def test_get_vlan_info_unsupported_device(self, config_manager):
        """Test VLAN info retrieval for unsupported device type."""
        handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        with pytest.raises(ValueError, match="Unsupported device type"):
            handler.get_vlan_info(mock_connection, 'unsupported_device')
