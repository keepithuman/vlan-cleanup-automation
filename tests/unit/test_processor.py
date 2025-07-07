"""
Unit tests for processor module.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from concurrent.futures import Future

from src.processor import VLANCleanupProcessor
from src.models import DeviceInfo, VLANInfo, ProcessingResult, BusinessMetrics


class TestVLANCleanupProcessor:
    """Test cases for VLANCleanupProcessor class."""
    
    def test_init_success(self, temp_config_file):
        """Test successful processor initialization."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        assert processor.dry_run is True
        assert processor.results == []
        assert hasattr(processor, 'config_manager')
        assert hasattr(processor, 'device_handler')
        assert processor.max_concurrent_devices == 2  # From test config
    
    def test_init_invalid_config(self):
        """Test processor initialization with invalid config."""
        # Create a processor with missing config that will fail validation
        with patch('src.config.ConfigManager.validate_config') as mock_validate:
            mock_validate.return_value = False
            
            with pytest.raises(ValueError, match="Invalid configuration"):
                VLANCleanupProcessor('invalid.yaml')
    
    @patch('src.processor.time.time')
    def test_process_single_device_success(self, mock_time, temp_config_file, sample_vlan_info):
        """Test successful single device processing."""
        mock_time.side_effect = [0.0, 5.0]  # Start and end times
        
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock device handler methods
        mock_connection = MagicMock()
        processor.device_handler.connect_to_device = MagicMock(return_value=mock_connection)
        processor.device_handler.get_device_type = MagicMock(return_value='cisco_ios')
        processor.device_handler.get_vlan_info = MagicMock(return_value=[sample_vlan_info])
        processor.device_handler.generate_rollback_commands = MagicMock(return_value=['vlan 100'])
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = processor.process_single_device(device_info)
        
        assert isinstance(result, ProcessingResult)
        assert result.status == 'success'
        assert result.total_vlans == 1
        assert len(result.unused_vlans) == 1
        assert result.processing_time == 5.0
        assert len(result.removal_commands) == 1
        assert len(result.rollback_commands) == 1
        
        # Verify device handler was called correctly
        processor.device_handler.connect_to_device.assert_called_once_with(device_info)
        processor.device_handler.get_vlan_info.assert_called_once_with(mock_connection, 'cisco_ios')
        mock_connection.disconnect.assert_called_once()
    
    def test_process_single_device_connection_failure(self, temp_config_file):
        """Test single device processing with connection failure."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock connection failure
        processor.device_handler.connect_to_device = MagicMock(return_value=None)
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = processor.process_single_device(device_info)
        
        assert result.status == 'failed'
        assert result.error_message == 'Failed to connect to device'
        assert result.total_vlans == 0
        assert len(result.unused_vlans) == 0
    
    def test_process_single_device_exception(self, temp_config_file):
        """Test single device processing with exception."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock exception during processing
        processor.device_handler.connect_to_device = MagicMock(side_effect=Exception("Test error"))
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = processor.process_single_device(device_info)
        
        assert result.status == 'failed'
        assert result.error_message == 'Test error'
    
    def test_process_single_device_high_risk_warnings(self, temp_config_file):
        """Test that high-risk VLANs generate warnings."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Create high-risk VLAN
        high_risk_vlan = VLANInfo(
            vlan_id=100,
            name='management',
            status='active',
            ports=[],
            is_unused=True,
            risk_level='critical'
        )
        
        mock_connection = MagicMock()
        processor.device_handler.connect_to_device = MagicMock(return_value=mock_connection)
        processor.device_handler.get_device_type = MagicMock(return_value='cisco_ios')
        processor.device_handler.get_vlan_info = MagicMock(return_value=[high_risk_vlan])
        processor.device_handler.generate_rollback_commands = MagicMock(return_value=[])
        
        device_info = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'vendor': 'cisco',
            'device_type': 'cisco_ios'
        }
        
        result = processor.process_single_device(device_info)
        
        assert len(result.warnings) == 1
        assert 'critical risk' in result.warnings[0]
    
    @patch('src.processor.ThreadPoolExecutor')
    def test_process_devices_success(self, mock_executor, temp_config_file, sample_processing_result):
        """Test successful processing of multiple devices."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock ThreadPoolExecutor
        mock_future = MagicMock()
        mock_future.result.return_value = sample_processing_result
        
        mock_executor_instance = MagicMock()
        mock_executor_instance.submit.return_value = mock_future
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor.return_value = mock_executor_instance
        
        # Mock as_completed to return our future
        with patch('src.processor.as_completed') as mock_as_completed:
            mock_as_completed.return_value = [mock_future]
            
            device_list = [
                {
                    'hostname': 'test-switch-01',
                    'ip_address': '192.168.1.10',
                    'vendor': 'cisco',
                    'device_type': 'cisco_ios'
                }
            ]
            
            results = processor.process_devices(device_list)
        
        assert len(results) == 1
        assert results[0] == sample_processing_result
        assert processor.results == results
    
    def test_process_devices_no_devices(self, temp_config_file):
        """Test processing with no devices configured."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Override config to have no devices
        processor.config_manager.get_devices = MagicMock(return_value=[])
        
        results = processor.process_devices()
        
        assert results == []


class TestBusinessMetricsCalculation:
    """Test cases for business metrics calculation."""
    
    def test_calculate_business_metrics_no_results(self, temp_config_file):
        """Test business metrics calculation with no results."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        metrics = processor.calculate_business_metrics()
        
        assert isinstance(metrics, BusinessMetrics)
        assert metrics.time_saved_minutes == 0
        assert metrics.time_saved_hours == 0
        assert metrics.estimated_cost_savings_usd == 0
        assert metrics.devices_processed == 0
        assert metrics.vlans_cleaned == 0
    
    def test_calculate_business_metrics_with_results(self, temp_config_file, sample_processing_result):
        """Test business metrics calculation with results."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        processor.results = [sample_processing_result]
        
        metrics = processor.calculate_business_metrics()
        
        # Manual time: 30 min, automated: 2 min, difference: 28 min per device
        expected_time_saved = 28.0
        expected_cost_savings = 28.0 * 2  # $2 per minute
        
        assert metrics.time_saved_minutes == expected_time_saved
        assert metrics.time_saved_hours == round(expected_time_saved / 60, 2)
        assert metrics.estimated_cost_savings_usd == expected_cost_savings
        assert metrics.devices_processed == 1
        assert metrics.vlans_cleaned == 1  # One unused VLAN in sample result
        assert len(metrics.operational_benefits) > 0


class TestRecommendationsGeneration:
    """Test cases for recommendations generation."""
    
    def test_generate_recommendations_no_results(self, temp_config_file):
        """Test recommendations with no results."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        recommendations = processor.generate_recommendations()
        
        assert len(recommendations) == 1
        assert "No processing results available" in recommendations[0]
    
    def test_generate_recommendations_with_high_risk_vlans(self, temp_config_file, sample_device):
        """Test recommendations with high-risk VLANs."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Create result with high-risk VLAN
        high_risk_vlan = VLANInfo(
            vlan_id=100,
            name='management',
            status='active',
            ports=[],
            is_unused=True,
            risk_level='critical'
        )
        
        result = ProcessingResult(
            device=sample_device,
            total_vlans=10,
            unused_vlans=[high_risk_vlan],
            removal_commands=[],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        processor.results = [result]
        
        recommendations = processor.generate_recommendations()
        
        # Should recommend manual review for high-risk VLANs
        high_risk_rec = next((r for r in recommendations if "Manual review required" in r), None)
        assert high_risk_rec is not None
        assert "1 high/critical risk VLANs" in high_risk_rec
    
    def test_generate_recommendations_with_failed_devices(self, temp_config_file, sample_device):
        """Test recommendations with failed devices."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Create failed result
        failed_result = ProcessingResult(
            device=sample_device,
            total_vlans=0,
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=2.0,
            status='failed',
            error_message='Connection timeout'
        )
        
        processor.results = [failed_result]
        
        recommendations = processor.generate_recommendations()
        
        # Should recommend investigating connection issues
        failed_rec = next((r for r in recommendations if "connection issues" in r), None)
        assert failed_rec is not None
        assert "1 failed devices" in failed_rec
    
    def test_generate_recommendations_high_cleanup_percentage(self, temp_config_file, sample_device, sample_vlan_info):
        """Test recommendations with high cleanup percentage."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Create result with high percentage of unused VLANs
        unused_vlans = [sample_vlan_info] * 8  # 8 unused out of 10 total = 80%
        
        result = ProcessingResult(
            device=sample_device,
            total_vlans=10,
            unused_vlans=unused_vlans,
            removal_commands=[],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        processor.results = [result]
        
        recommendations = processor.generate_recommendations()
        
        # Should recommend VLAN lifecycle management
        lifecycle_rec = next((r for r in recommendations if "lifecycle management" in r), None)
        assert lifecycle_rec is not None


class TestCleanupExecution:
    """Test cases for cleanup execution."""
    
    def test_execute_cleanup_dry_run_mode(self, temp_config_file):
        """Test that cleanup cannot be executed in dry-run mode."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        result = processor.execute_cleanup()
        
        assert result is False
    
    def test_execute_cleanup_no_results(self, temp_config_file):
        """Test cleanup execution with no results."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        result = processor.execute_cleanup()
        
        assert result is False
    
    def test_execute_cleanup_success(self, temp_config_file, sample_processing_result):
        """Test successful cleanup execution."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        processor.results = [sample_processing_result]
        
        # Mock the device cleanup method
        with patch.object(processor, '_execute_device_cleanup') as mock_cleanup:
            mock_cleanup.return_value = True
            
            result = processor.execute_cleanup()
        
        assert result is True
        mock_cleanup.assert_called_once()
    
    def test_execute_cleanup_skip_high_risk_without_approval(self, temp_config_file, sample_device):
        """Test that high-risk VLANs are skipped without approval."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        # Create result with high-risk VLAN
        high_risk_vlan = VLANInfo(
            vlan_id=100,
            name='management',
            status='active',
            ports=[],
            is_unused=True,
            risk_level='critical'
        )
        
        result_with_high_risk = ProcessingResult(
            device=sample_device,
            total_vlans=1,
            unused_vlans=[high_risk_vlan],
            removal_commands=['no vlan 100'],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        processor.results = [result_with_high_risk]
        
        # Mock the device cleanup method
        with patch.object(processor, '_execute_device_cleanup') as mock_cleanup:
            result = processor.execute_cleanup(approve_all=False)
        
        # Should not call cleanup since high-risk VLAN was skipped
        mock_cleanup.assert_not_called()
        assert result is True  # Still returns True as operation succeeded (just skipped VLANs)
    
    def test_execute_cleanup_approve_all(self, temp_config_file, sample_device):
        """Test cleanup execution with approve_all flag."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        # Create result with high-risk VLAN
        high_risk_vlan = VLANInfo(
            vlan_id=100,
            name='management',
            status='active',
            ports=[],
            is_unused=True,
            risk_level='critical'
        )
        
        result_with_high_risk = ProcessingResult(
            device=sample_device,
            total_vlans=1,
            unused_vlans=[high_risk_vlan],
            removal_commands=['no vlan 100'],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        processor.results = [result_with_high_risk]
        
        # Mock the device cleanup method
        with patch.object(processor, '_execute_device_cleanup') as mock_cleanup:
            mock_cleanup.return_value = True
            
            result = processor.execute_cleanup(approve_all=True)
        
        # Should call cleanup even for high-risk VLAN
        mock_cleanup.assert_called_once()
        assert result is True
    
    @patch('src.device_handler.DeviceHandler.connect_to_device')
    def test_execute_device_cleanup_success_cisco(self, mock_connect, temp_config_file, sample_device):
        """Test successful device cleanup execution for Cisco."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        # Mock connection and commands
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        
        vlans_to_remove = [
            VLANInfo(vlan_id=100, name='test-vlan', status='active', ports=[], 
                    removal_command='no vlan 100')
        ]
        
        # Set device vendor to cisco
        sample_device.vendor = 'cisco'
        
        result = processor._execute_device_cleanup(sample_device, vlans_to_remove)
        
        assert result is True
        mock_connection.send_config_set.assert_called_once_with(['no vlan 100'])
        mock_connection.send_command.assert_called_once_with('write memory')
        mock_connection.disconnect.assert_called_once()
    
    @patch('src.device_handler.DeviceHandler.connect_to_device')
    def test_execute_device_cleanup_connection_failure(self, mock_connect, temp_config_file, sample_device):
        """Test device cleanup with connection failure."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        # Mock connection failure
        mock_connect.return_value = None
        
        vlans_to_remove = [
            VLANInfo(vlan_id=100, name='test-vlan', status='active', ports=[])
        ]
        
        result = processor._execute_device_cleanup(sample_device, vlans_to_remove)
        
        assert result is False
    
    @patch('src.device_handler.DeviceHandler.connect_to_device')
    def test_execute_device_cleanup_exception(self, mock_connect, temp_config_file, sample_device):
        """Test device cleanup with exception."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=False)
        
        # Mock connection that raises exception
        mock_connect.side_effect = Exception("Connection error")
        
        vlans_to_remove = [
            VLANInfo(vlan_id=100, name='test-vlan', status='active', ports=[])
        ]
        
        result = processor._execute_device_cleanup(sample_device, vlans_to_remove)
        
        assert result is False
