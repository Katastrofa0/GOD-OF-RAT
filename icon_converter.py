import tempfile
import subprocess
import os
import sys
from PIL import Image


HAS_WIN32GUI = False

try:
    import win32gui
    import win32ui
    import win32api
    import win32con
    HAS_WIN32GUI = True
except ImportError:
    pass

def extract_icon_from_exe(exe_path):
    
    # Method 1: win32gui (if Exist)
    if HAS_WIN32GUI:
        try:
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            
            if not large:
                return None

            icon_handle = large[0]
            for s in small:
                win32gui.DestroyIcon(s)
            
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, 32, 32)
            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)
            
            win32gui.DrawIcon(hdc_mem.GetSafeHdc(), 0, 0, icon_handle)
            
            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
            
            win32gui.DestroyIcon(icon_handle)
            hdc_mem.DeleteDC()
            win32gui.ReleaseDC(0, hdc.GetSafeHdc())
            
            temp_ico = tempfile.NamedTemporaryFile(suffix='.ico', delete=False)
            img.save(temp_ico.name, format='ICO')
            return temp_ico.name
            
        except Exception as e:
            print(f"[DEBUG] win32gui extraction failed: {e}, trying PowerShell fallback...")

    
    try:
        temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name
        
        ps_script = f'''
        Add-Type -AssemblyName System.Drawing
        try {{
            $icon = [System.Drawing.Icon]::ExtractAssociatedIcon("{exe_path}")
            if ($icon) {{
                $bmp = $icon.ToBitmap()
                $bmp.Save("{temp_png}", [System.Drawing.Imaging.ImageFormat]::Png)
                $bmp.Dispose()
                $icon.Dispose()
            }}
        }} catch {{ }}
        '''
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        
        subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
            capture_output=True, timeout=15,
            startupinfo=startupinfo, creationflags=creationflags
        )
        
        if os.path.exists(temp_png) and os.path.getsize(temp_png) > 0:
            return temp_png
        return None
            
    except Exception as e:
        print(f"[DEBUG] PowerShell extraction failed: {e}")
        return None


def convert_to_icon(image_path, output_path, sizes=None):
    try:
        img = Image.open(image_path)
        
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        if sizes is None:
            sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        
        icons = []
        for size in sizes:
            resized = img.copy()
            resized.thumbnail(size, Image.Resampling.LANCZOS)
            
            new_img = Image.new('RGBA', size, (0, 0, 0, 0))
            paste_x = (size[0] - resized.size[0]) // 2
            paste_y = (size[1] - resized.size[1]) // 2
            new_img.paste(resized, (paste_x, paste_y))
            icons.append(new_img)
        
        icons[0].save(output_path, format='ICO', 
                      sizes=[(i.width, i.height) for i in icons], 
                      append_images=icons[1:])
        
        if image_path.endswith('.png') and 'temp' in image_path.lower():
            try:
                os.unlink(image_path)
            except:
                pass
            
        return True, output_path
        
    except Exception as e:
        return False, str(e)


def get_supported_formats():
    return ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif', '*.ico']
