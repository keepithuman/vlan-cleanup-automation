#!/usr/bin/env python3
"""
VLAN Cleanup Automation - Main CLI Interface
============================================

Enterprise-grade automation solution for identifying unused VLANs and generating
removal commands for Cisco, Arista, and Juniper network devices.

Usage:
    python main.py --config config.yaml --dry-run
    python main.py --execute --approve-all
"""

import sys
import logging
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.processor import VLANCleanupProcessor
from src.reporting import ReportGenerator
from src.config import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to run the VLAN cleanup automation."""
    parser = argparse.ArgumentParser(
        description='VLAN Cleanup Automation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run analysis (default)
  python main.py --config config.yaml
  
  # Execute cleanup with manual approval for high-risk VLANs
  python main.py --execute --config config.yaml
  
  # Execute cleanup with automatic approval for all VLANs
  python main.py --execute --approve-all --config config.yaml
  
  # Generate report only from existing results
  python main.py --report-only --input results.json
        """
    )
    
    parser.add_argument('--config', '-c', default='config.yaml',
                       help='Configuration file path (default: config.yaml)')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (default: True)')
    parser.add_argument('--execute', action='store_true',
                       help='Execute actual VLAN cleanup (disables dry-run)')
    parser.add_argument('--approve-all', action='store_true',
                       help='Approve removal of high-risk VLANs (use with caution)')
    parser.add_argument('--output', '-o', default=None,
                       help='Output file for results')
    parser.add_argument('--csv', action='store_true',
                       help='Also generate CSV summary')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--report-only', action='store_true',
                       help='Generate report from existing results file')
    parser.add_argument('--input', '-i', default=None,
                       help='Input results file for report generation')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine run mode
    dry_run = not args.execute
    if args.execute:
        logger.info("Running in PRODUCTION mode - changes will be applied to devices")
        if args.approve_all:
            logger.warning("AUTO-APPROVAL enabled - high-risk VLANs will be removed automatically")
    else:
        logger.info("Running in DRY-RUN mode - no changes will be applied")
    
    try:
        if args.report_only:
            # Generate report from existing results
            if not args.input:
                logger.error("--input required when using --report-only")
                return 1
            
            import json
            with open(args.input, 'r') as f:
                data = json.load(f)
            
            # Extract results from saved data
            if 'detailed_results' in data:
                from src.models import ProcessingResult, DeviceInfo, VLANInfo
                
                results = []
                for result_data in data['detailed_results']:
                    # Reconstruct objects from saved data
                    device = DeviceInfo(**result_data['device'])
                    vlans = [VLANInfo(**vlan_data) for vlan_data in result_data['unused_vlans']]
                    
                    result = ProcessingResult(
                        device=device,
                        total_vlans=result_data['total_vlans'],
                        unused_vlans=vlans,
                        removal_commands=result_data['removal_commands'],
                        rollback_commands=result_data['rollback_commands'],
                        processing_time=result_data['processing_time'],
                        status=result_data['status'],
                        error_message=result_data.get('error_message', ''),
                        warnings=result_data.get('warnings', [])
                    )
                    results.append(result)
                
                # Generate new report
                config_manager = ConfigManager(args.config)
                report_generator = ReportGenerator(config_manager)
                processor = VLANCleanupProcessor(args.config, dry_run=True)
                
                business_metrics = processor.calculate_business_metrics()
                recommendations = processor.generate_recommendations()
                
                report = report_generator.generate_comprehensive_report(
                    results, business_metrics, recommendations, dry_run=True
                )
                
                # Save report
                report_file = report_generator.save_report(report, args.output)
                logger.info(f"Report generated successfully: {report_file}")
                
                if args.csv:
                    csv_file = report_generator.generate_summary_csv(results)
                    logger.info(f"CSV summary generated: {csv_file}")
            
            return 0
        
        # Normal processing mode
        # Initialize processor
        processor = VLANCleanupProcessor(args.config, dry_run=dry_run)
        
        # Process devices
        logger.info("Starting VLAN cleanup analysis...")
        results = processor.process_devices()
        
        if not results:
            logger.error("No results generated - check configuration and device connectivity")
            return 1
        
        # Calculate business metrics
        business_metrics = processor.calculate_business_metrics()
        
        # Generate recommendations
        recommendations = processor.generate_recommendations()
        
        # Generate comprehensive report
        config_manager = ConfigManager(args.config)
        report_generator = ReportGenerator(config_manager)
        
        report = report_generator.generate_comprehensive_report(
            results, business_metrics, recommendations, dry_run
        )
        
        # Save results
        report_file = report_generator.save_report(report, args.output)
        logger.info(f"Analysis complete. Report saved to: {report_file}")
        
        # Generate CSV if requested
        if args.csv:
            csv_file = report_generator.generate_summary_csv(results)
            logger.info(f"CSV summary generated: {csv_file}")
        
        # Print summary to console
        print_summary(report)
        
        # Execute cleanup if requested
        if args.execute:
            logger.info("Proceeding with VLAN cleanup execution...")
            success = processor.execute_cleanup(approve_all=args.approve_all)
            if success:
                logger.info("VLAN cleanup execution completed successfully")
            else:
                logger.error("VLAN cleanup execution encountered errors")
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def print_summary(report):
    """Print executive summary to console."""
    print("\n" + "="*60)
    print("VLAN CLEANUP AUTOMATION - EXECUTIVE SUMMARY")
    print("="*60)
    
    summary = report.get('executive_summary', {})
    business = report.get('business_impact', {})
    risk = report.get('risk_assessment', {})
    
    print(f"Devices Analyzed: {summary.get('total_devices_analyzed', 0)}")
    print(f"Successful Analyses: {summary.get('successful_analyses', 0)}")
    print(f"Total VLANs Discovered: {summary.get('total_vlans_discovered', 0)}")
    print(f"Unused VLANs Identified: {summary.get('unused_vlans_identified', 0)}")
    print(f"Potential Cleanup: {summary.get('potential_cleanup_percentage', 0)}%")
    
    print(f"\nBUSINESS IMPACT:")
    print(f"Time Saved: {business.get('time_saved_hours', 0)} hours")
    print(f"Cost Savings: ${business.get('estimated_cost_savings_usd', 0)}")
    
    print(f"\nRISK ASSESSMENT:")
    risk_dist = risk.get('risk_distribution', {})
    print(f"Low Risk: {risk_dist.get('low', 0)} VLANs")
    print(f"Medium Risk: {risk_dist.get('medium', 0)} VLANs")
    print(f"High Risk: {risk_dist.get('high', 0)} VLANs")
    print(f"Critical Risk: {risk_dist.get('critical', 0)} VLANs")
    
    print(f"\nSafe for Automation: {risk.get('safe_for_automated_cleanup', 0)} VLANs")
    print(f"Require Manual Review: {risk.get('high_risk_vlans_requiring_approval', 0)} VLANs")
    
    print("\nNext Steps:")
    for step in report.get('next_steps', [])[:3]:  # Show first 3 steps
        print(f"  • {step}")
    
    print("="*60)


if __name__ == "__main__":
    sys.exit(main())
