#!/usr/bin/env python3
"""
Cross-Platform Hardware ID Detection
Updated version of check_hardware_id.py that works on Windows, macOS, and Linux
"""

import platform
import subprocess
import hashlib
import sys

def get_cross_platform_hardware_id():
    """
    Get hardware ID that works across Windows, macOS, and Linux
    """
    system = platform.system().lower()
    
    try:
        if system == 'windows':
            return get_windows_hardware_id()
        elif system == 'darwin':  # macOS
            return get_macos_hardware_id()
        elif system == 'linux':
            return get_linux_hardware_id()
        else:
            return get_fallback_hardware_id()
    except Exception as e:
        print(f"[WARN] Error getting hardware ID: {e}")
        return get_fallback_hardware_id()

def get_windows_hardware_id():
    """Windows-specific hardware ID (your current method)"""
    try:
        import wmi
        c = wmi.WMI()
        
        # Get motherboard serial
        motherboard = c.Win32_BaseBoard()[0]
        mb_serial = motherboard.SerialNumber
        
        # Get CPU ID
        cpu = c.Win32_Processor()[0]
        cpu_id = cpu.ProcessorId
        
        # Combine and hash
        combined = f"{mb_serial}-{cpu_id}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
        
    except Exception:
        # Fallback to MAC address on Windows
        import uuid
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
        return hashlib.md5(mac.encode()).hexdigest()[:16]

def get_macos_hardware_id():
    """macOS-specific hardware ID using system_profiler"""
    try:
        # Get hardware UUID (most reliable on macOS)
        result = subprocess.run(['system_profiler', 'SPHardwareDataType'], 
                              capture_output=True, text=True)
        
        for line in result.stdout.split('\n'):
            if 'Hardware UUID' in line:
                uuid = line.split(':')[1].strip()
                return hashlib.md5(uuid.encode()).hexdigest()[:16]
        
        # Fallback to serial number
        result = subprocess.run(['system_profiler', 'SPHardwareDataType'], 
                              capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'Serial Number' in line:
                serial = line.split(':')[1].strip()
                return hashlib.md5(serial.encode()).hexdigest()[:16]
                
    except Exception:
        pass
    
    # Final fallback to MAC address
    return get_mac_based_id()

def get_linux_hardware_id():
    """Linux-specific hardware ID using /proc and dmidecode"""
    try:
        # Try to get motherboard serial
        result = subprocess.run(['sudo', 'dmidecode', '-s', 'baseboard-serial-number'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            serial = result.stdout.strip()
            return hashlib.md5(serial.encode()).hexdigest()[:16]
        
        # Try machine-id (available on most modern Linux)
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
                return hashlib.md5(machine_id.encode()).hexdigest()[:16]
        except FileNotFoundError:
            pass
        
        # Try /proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                # Extract serial if available
                for line in content.split('\n'):
                    if 'Serial' in line:
                        serial = line.split(':')[1].strip()
                        return hashlib.md5(serial.encode()).hexdigest()[:16]
        except Exception:
            pass
            
    except Exception:
        pass
    
    return get_mac_based_id()

def get_mac_based_id():
    """Fallback method using MAC address (works on all platforms)"""
    import uuid
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                   for elements in range(0,2*6,2)][::-1])
    return hashlib.md5(mac.encode()).hexdigest()[:16]

def get_fallback_hardware_id():
    """Ultimate fallback using system info"""
    system_info = f"{platform.system()}-{platform.machine()}-{platform.processor()}"
    return hashlib.md5(system_info.encode()).hexdigest()[:16]

def get_platform_info():
    """Get detailed platform information"""
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': sys.version,
        'platform': platform.platform()
    }

if __name__ == "__main__":
    print("[SCREEN]️ CROSS-PLATFORM HARDWARE ID DETECTION")
    print("=" * 50)
    
    # Show platform info
    platform_info = get_platform_info()
    print(f"System: {platform_info['system']}")
    print(f"Platform: {platform_info['platform']}")
    print(f"Machine: {platform_info['machine']}")
    
    # Get hardware ID
    hardware_id = get_cross_platform_hardware_id()
    print(f"\n🔑 Hardware ID: {hardware_id}")
    print(f"📏 Length: {len(hardware_id)} characters")
    
    # Show what method was used
    system = platform.system().lower()
    if system == 'windows':
        print("[WIN] Method: Windows WMI (motherboard + CPU)")
    elif system == 'darwin':
        print("🍎 Method: macOS system_profiler (Hardware UUID)")
    elif system == 'linux':
        print("🐧 Method: Linux dmidecode/machine-id")
    else:
        print("[?] Method: Fallback (system info hash)")
    
    print(f"\n[OK] This ID will be consistent across app restarts on this device")
    print(f"[WARN]  ID will change if hardware is significantly modified")