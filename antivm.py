
import os
import platform
import subprocess
import re

class AntiVM:
    INDICATORS = {
        "general": [
            "VBOX", "VMWARE", "VIRTUAL", "KVM", "XEN", "QEMU", "HYPER-V", "PARALLELS",
            "VIRTUALBOX", "VIRTUAL MACHINE", "MICROSOFT HYPERV", "INNOTEK", "ORACLE", 
            "VM PLATFORM", "GUEST ADDITIONS", "HOST-ONLY", "VMWARE VIRTUAL", "GENERIC", 
            "BOCHS", "TCG", "HV", "BHYVE", "PARAVIRTUAL", "MS HYPERV", "VMM", "HV_NESTED"
        ],
        "mac": [
            "00:05:69", "00:0C:29", "00:1C:14", "00:50:56", "08:00:27",
            "52:54:00", "00:15:5D", "00:16:3E", "0A:00:27", "00:21:F6",
        ],
        "process": [
            "vboxservice", "vboxtray", "vmtoolsd", "vmwaretray", "xenservice", "qemu-ga",
            "vmwareuser", "vmsrvc", "vmusrvc", "xenstore", "qga", "xenbus", "vmmouse",
            "vboxguest", "vboxvideo", "VBoxService.exe", "VBoxTray.exe", "VBoxControl.exe",
            "VGAuthService.exe", "vmacthlp.exe", "vmwareuser.exe", "vmwaretray.exe",
            "vmwaretoolsd.exe"
        ]
    }

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.detected_indicators = []
        self._result = self._detect()

    def _log(self, msg):
        if self.verbose:
            print(f"[AntiVM] {msg}")

    def _detect(self):
        system = platform.system()
        self._log(f"Detected OS: {system}")

        if system == "Windows":
            self._check_wmic()
            self._check_mac()
            self._check_processes()
        elif system == "Linux":
            self._check_dmi()
            self._check_cpuinfo()
            self._check_mac()
            self._check_processes()
        else:
            self._log(f"Unsupported OS: {system}")

        return len(self.detected_indicators) > 0

    def _check_wmic(self):
        try:
            powershell_command = 'Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object Manufacturer, Model'

            result = subprocess.run(
                ['powershell', '-Command', powershell_command],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.upper()
            self._log("WMIC Output:\n" + output.strip())
            for keyword in self.INDICATORS["general"]:
                if keyword in output:
                    self.detected_indicators.append(f"WMIC matched: {keyword}")
        except Exception as e:
            self._log(f"WMIC error: {e}")

    def _check_dmi(self):
        try:
            with open("/sys/class/dmi/id/product_name", "r") as f:
                content = f.read().upper()
                self._log(f"DMI Product Name: {content.strip()}")
                for keyword in self.INDICATORS["general"]:
                    if keyword in content:
                        self.detected_indicators.append(f"DMI matched: {keyword}")
        except Exception as e:
            self._log(f"DMI read error: {e}")

    def _check_cpuinfo(self):
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read().upper()
                for keyword in self.INDICATORS["general"]:
                    if keyword in content:
                        self.detected_indicators.append(f"CPU info matched: {keyword}")
        except Exception as e:
            self._log(f"CPU info error: {e}")

    def _check_mac(self):
        try:
            system = platform.system()
            if system == "Windows":
                result = subprocess.run(["getmac", "/v", "/fo", "list"], capture_output=True, text=True, timeout=5)
                macs = re.findall(r"Physical Address\s+: ([\w-]+)", result.stdout)
            else:
                result = subprocess.run(["ip", "link"], capture_output=True, text=True, timeout=5)
                macs = re.findall(r"link/ether ([\da-f:]{17})", result.stdout, re.IGNORECASE)

            for mac in macs:
                norm_mac = mac.replace("-", ":").lower()
                for prefix in self.INDICATORS["mac"]:
                    if norm_mac.startswith(prefix.lower()):
                        self.detected_indicators.append(f"MAC matched: {norm_mac}")
        except Exception as e:
            self._log(f"MAC check error: {e}")

    def _check_processes(self):
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            content = result.stdout.lower()
            for proc in self.INDICATORS["process"]:
                if proc.lower() in content:
                    self.detected_indicators.append(f"Process matched: {proc}")
        except Exception as e:
            self._log(f"Process check error: {e}")

    def get_data(self):
        if self._result:
            return "[!] VM Detected:\n" + "\n".join(f"- {x}" for x in self.detected_indicators)
        else:
            return "[OK] No VM Detected."

    def is_vm(self):
        return self._result

    def get_antivm_code(self):
        return '''
# === ANTI-VM MODULE ===
import platform
import subprocess
import re

class AntiVM:
    INDICATORS = {
        "general": [
            "VBOX", "VMWARE", "VIRTUAL", "KVM", "XEN", "QEMU", "HYPER-V", "PARALLELS",
            "VIRTUALBOX", "VIRTUAL MACHINE", "MICROSOFT HYPERV", "INNOTEK", "ORACLE", 
            "VM PLATFORM", "GUEST ADDITIONS", "HOST-ONLY", "VMWARE VIRTUAL", "GENERIC", 
            "BOCHS", "TCG", "HV", "BHYVE", "PARAVIRTUAL", "MS HYPERV", "VMM", "HV_NESTED"
        ],
        "mac": [
            "00:05:69", "00:0C:29", "00:1C:14", "00:50:56", "08:00:27",
            "52:54:00", "00:15:5D", "00:16:3E", "0A:00:27", "00:21:F6",
        ],
        "process": [
            "vboxservice", "vboxtray", "vmtoolsd", "vmwaretray", "xenservice", "qemu-ga",
            "vmwareuser", "vmsrvc", "vmusrvc", "xenstore", "qga", "xenbus", "vmmouse",
            "vboxguest", "vboxvideo", "VBoxService.exe", "VBoxTray.exe", "VBoxControl.exe",
            "VGAuthService.exe", "vmacthlp.exe", "vmwareuser.exe", "vmwaretray.exe",
            "vmwaretoolsd.exe"
        ]
    }

    def __init__(self):
        self.detected_indicators = []
        self._result = self._detect()

    def _detect(self):
        system = platform.system()
        if system == "Windows":
            self._check_wmic()
            self._check_mac()
            self._check_processes()
        elif system == "Linux":
            self._check_dmi()
            self._check_cpuinfo()
            self._check_mac()
            self._check_processes()
        return len(self.detected_indicators) > 0

    def _check_wmic(self):
        try:
            result = subprocess.run(
                ['powershell', '-Command', 'Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object Manufacturer, Model'],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.upper()
            for keyword in self.INDICATORS["general"]:
                if keyword in output:
                    self.detected_indicators.append(keyword)
        except:
            pass

    def _check_dmi(self):
        try:
            with open("/sys/class/dmi/id/product_name", "r") as f:
                content = f.read().upper()
                for keyword in self.INDICATORS["general"]:
                    if keyword in content:
                        self.detected_indicators.append(keyword)
        except:
            pass

    def _check_cpuinfo(self):
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read().upper()
                for keyword in self.INDICATORS["general"]:
                    if keyword in content:
                        self.detected_indicators.append(keyword)
        except:
            pass

    def _check_mac(self):
        try:
            system = platform.system()
            if system == "Windows":
                result = subprocess.run(["getmac", "/v", "/fo", "list"], capture_output=True, text=True, timeout=5)
                macs = re.findall(r"Physical Address\s+: ([\w-]+)", result.stdout)
            else:
                result = subprocess.run(["ip", "link"], capture_output=True, text=True, timeout=5)
                macs = re.findall(r"link/ether ([\da-f:]{17})", result.stdout, re.IGNORECASE)
            for mac in macs:
                norm_mac = mac.replace("-", ":").lower()
                for prefix in self.INDICATORS["mac"]:
                    if norm_mac.startswith(prefix.lower()):
                        self.detected_indicators.append(f"MAC:{prefix}")
        except:
            pass

    def _check_processes(self):
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            content = result.stdout.lower()
            for proc in self.INDICATORS["process"]:
                if proc.lower() in content:
                    self.detected_indicators.append(f"PROC:{proc}")
        except:
            pass

    def is_vm(self):
        return self._result

antivm = AntiVM()
if antivm.is_vm():
    import sys
    sys.exit(0)
'''


if __name__ == "__main__":
    antivm = AntiVM(verbose=True)
    print(antivm.get_data())
    print(f"\nResult: {'VM DETECTED' if antivm.is_vm() else 'No VM detected'}")