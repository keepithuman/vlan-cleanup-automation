"""
Report generation and output management.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from .models import ProcessingResult, BusinessMetrics

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates comprehensive reports for VLAN cleanup analysis."""
    
    def __init__(self, config_manager):
        """Initialize report generator."""
        self.config_manager = config_manager
        self.output_config = config_manager.get_output_config()
    
    def generate_comprehensive_report(self, results: List[ProcessingResult], 
                                    business_metrics: BusinessMetrics,
                                    recommendations: List[str],
                                    dry_run: bool = True) -> Dict[str, Any]:
        """Generate comprehensive report of VLAN cleanup analysis."""
        if not results:
            logger.warning("No results available for report generation")
            return {}
        
        # Summary statistics
        total_devices = len(results)
        successful_devices = len([r for r in results if r.status == "success"])
        failed_devices = total_devices - successful_devices
        
        total_vlans = sum(r.total_vlans for r in results)
        total_unused_vlans = sum(len(r.unused_vlans) for r in results)
        
        # Risk analysis
        risk_analysis = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for result in results:
            for vlan in result.unused_vlans:
                risk_analysis[vlan.risk_level] += 1
        
        # Device-specific summaries
        device_summaries = []
        for result in results:
            device_summaries.append({
                "hostname": result.device.hostname,
                "vendor": result.device.vendor,
                "status": result.status,
                "total_vlans": result.total_vlans,
                "unused_vlans_count": len(result.unused_vlans),
                "processing_time": round(result.processing_time, 2),
                "warnings_count": len(result.warnings),
                "cleanup_percentage": round((len(result.unused_vlans) / result.total_vlans * 100), 2) if result.total_vlans > 0 else 0
            })
        
        # Performance metrics
        total_processing_time = sum(r.processing_time for r in results)
        avg_processing_time = total_processing_time / len(results) if results else 0
        
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "report_version": "1.0",
                "dry_run_mode": dry_run,
                "total_processing_time_seconds": round(total_processing_time, 2)
            },
            "executive_summary": {
                "total_devices_analyzed": total_devices,
                "successful_analyses": successful_devices,
                "failed_analyses": failed_devices,
                "total_vlans_discovered": total_vlans,
                "unused_vlans_identified": total_unused_vlans,
                "potential_cleanup_percentage": round((total_unused_vlans / total_vlans * 100), 2) if total_vlans > 0 else 0,
                "average_processing_time_per_device": round(avg_processing_time, 2)
            },
            "risk_assessment": {
                "risk_distribution": risk_analysis,
                "high_risk_vlans_requiring_approval": risk_analysis["high"] + risk_analysis["critical"],
                "safe_for_automated_cleanup": risk_analysis["low"] + risk_analysis["medium"]
            },
            "business_impact": business_metrics.to_dict(),
            "device_analysis": {
                "device_summaries": device_summaries,
                "vendor_breakdown": self._get_vendor_breakdown(results),
                "performance_metrics": {
                    "fastest_device_processing": min([r.processing_time for r in results if r.status == "success"], default=0),
                    "slowest_device_processing": max([r.processing_time for r in results if r.status == "success"], default=0),
                    "average_processing_time": round(avg_processing_time, 2)
                }
            },
            "operational_recommendations": recommendations,
            "detailed_findings": {
                "devices_with_most_unused_vlans": self._get_top_cleanup_candidates(results),
                "critical_warnings": self._extract_critical_warnings(results),
                "configuration_issues": self._identify_config_issues(results)
            },
            "next_steps": self._generate_next_steps(results, risk_analysis),
            "detailed_results": [result.to_dict() for result in results]
        }
        
        return report
    
    def _get_vendor_breakdown(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """Get breakdown of results by vendor."""
        vendor_stats = {}
        
        for result in results:
            vendor = result.device.vendor
            if vendor not in vendor_stats:
                vendor_stats[vendor] = {
                    "device_count": 0,
                    "total_vlans": 0,
                    "unused_vlans": 0,
                    "success_rate": 0
                }
            
            vendor_stats[vendor]["device_count"] += 1
            vendor_stats[vendor]["total_vlans"] += result.total_vlans
            vendor_stats[vendor]["unused_vlans"] += len(result.unused_vlans)
            if result.status == "success":
                vendor_stats[vendor]["success_rate"] += 1
        
        # Calculate success rates
        for vendor, stats in vendor_stats.items():
            stats["success_rate"] = round((stats["success_rate"] / stats["device_count"] * 100), 2)
            stats["cleanup_percentage"] = round((stats["unused_vlans"] / stats["total_vlans"] * 100), 2) if stats["total_vlans"] > 0 else 0
        
        return vendor_stats
    
    def _get_top_cleanup_candidates(self, results: List[ProcessingResult], limit: int = 5) -> List[Dict[str, Any]]:
        """Get devices with the most unused VLANs."""
        candidates = []
        
        for result in results:
            if result.status == "success" and result.unused_vlans:
                candidates.append({
                    "hostname": result.device.hostname,
                    "vendor": result.device.vendor,
                    "unused_vlans_count": len(result.unused_vlans),
                    "total_vlans": result.total_vlans,
                    "cleanup_percentage": round((len(result.unused_vlans) / result.total_vlans * 100), 2) if result.total_vlans > 0 else 0,
                    "high_risk_vlans": len([v for v in result.unused_vlans if v.risk_level in ['high', 'critical']])
                })
        
        # Sort by unused VLAN count
        candidates.sort(key=lambda x: x["unused_vlans_count"], reverse=True)
        return candidates[:limit]
    
    def _extract_critical_warnings(self, results: List[ProcessingResult]) -> List[Dict[str, Any]]:
        """Extract critical warnings from results."""
        critical_warnings = []
        
        for result in results:
            if result.warnings:
                for warning in result.warnings:
                    critical_warnings.append({
                        "device": result.device.hostname,
                        "warning": warning,
                        "severity": "critical" if "critical" in warning.lower() else "high"
                    })
        
        return critical_warnings
    
    def _identify_config_issues(self, results: List[ProcessingResult]) -> List[Dict[str, Any]]:
        """Identify potential configuration issues."""
        issues = []
        
        for result in results:
            if result.status == "failed":
                issues.append({
                    "device": result.device.hostname,
                    "issue_type": "connection_failure",
                    "description": result.error_message,
                    "recommendation": "Check device connectivity and credentials"
                })
            
            # Check for devices with unusually high VLAN counts
            if result.total_vlans > 100:
                issues.append({
                    "device": result.device.hostname,
                    "issue_type": "high_vlan_count",
                    "description": f"Device has {result.total_vlans} VLANs configured",
                    "recommendation": "Review VLAN management practices"
                })
        
        return issues
    
    def _generate_next_steps(self, results: List[ProcessingResult], risk_analysis: Dict[str, int]) -> List[str]:
        """Generate actionable next steps."""
        next_steps = []
        
        # Check for immediate actions needed
        high_risk_count = risk_analysis["high"] + risk_analysis["critical"]
        if high_risk_count > 0:
            next_steps.append(f"IMMEDIATE: Review {high_risk_count} high/critical risk VLANs before any cleanup")
        
        # Check for failed devices
        failed_devices = [r for r in results if r.status == "failed"]
        if failed_devices:
            next_steps.append(f"URGENT: Resolve connectivity issues for {len(failed_devices)} failed devices")
        
        # Check for cleanup opportunities
        safe_vlans = risk_analysis["low"] + risk_analysis["medium"]
        if safe_vlans > 0:
            next_steps.append(f"READY: {safe_vlans} VLANs can be safely removed automatically")
        
        # General next steps
        next_steps.extend([
            "Schedule regular VLAN cleanup cycles",
            "Implement VLAN lifecycle management processes",
            "Update network documentation with current VLAN usage",
            "Create change management procedures for VLAN modifications"
        ])
        
        return next_steps
    
    def save_report(self, report: Dict[str, Any], filename: str = None) -> str:
        """Save report to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vlan_cleanup_report_{timestamp}.json"
        
        try:
            output_path = Path(filename)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Report saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error saving report to {filename}: {str(e)}")
            raise
    
    def generate_summary_csv(self, results: List[ProcessingResult], filename: str = None) -> str:
        """Generate CSV summary for easy analysis."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vlan_cleanup_summary_{timestamp}.csv"
        
        try:
            import csv
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Hostname', 'Vendor', 'Status', 'Total_VLANs', 'Unused_VLANs',
                    'Cleanup_Percentage', 'Processing_Time', 'Warnings', 'Risk_High_Critical'
                ])
                
                # Write data
                for result in results:
                    high_risk_count = len([v for v in result.unused_vlans if v.risk_level in ['high', 'critical']])
                    cleanup_percentage = round((len(result.unused_vlans) / result.total_vlans * 100), 2) if result.total_vlans > 0 else 0
                    
                    writer.writerow([
                        result.device.hostname,
                        result.device.vendor,
                        result.status,
                        result.total_vlans,
                        len(result.unused_vlans),
                        cleanup_percentage,
                        round(result.processing_time, 2),
                        len(result.warnings),
                        high_risk_count
                    ])
            
            logger.info(f"CSV summary saved to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving CSV summary: {str(e)}")
            raise
