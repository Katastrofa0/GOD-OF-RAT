import win32gui
import win32api
import win32con
import tempfile
from PIL import Image

def extract_icon_from_exe(exe_path):
    try:

        large, small = win32gui.ExtractIconEx(exe_path, 0)
        
        if not large:
            return None


        icon_handle = large[0]
        for s in small: win32gui.DestroyIcon(s) 
        
        import win32ui
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
        print(f"Error extracting icon: {e}")
        return None

def convert_to_icon(image_path, output_path, sizes=None):

    try:

        img = Image.open(image_path)
        

        if img.mode not in ('RGBA', 'RGB'):
            img = img.convert('RGB')

        icons = []
        for size in sizes:

            resized = img.copy()
            resized.thumbnail(size, Image.Resampling.LANCZOS)

            new_img = Image.new('RGBA', size, (0,0,0,0))
            paste_x = (size[0] - resized.size[0]) // 2
            paste_y = (size[1] - resized.size[1]) // 2
            new_img.paste(resized, (paste_x, paste_y))
            
            icons.append(new_img)

        icons[0].save(output_path, format='ICO', sizes=[(img.width, img.height) for img in icons], append_images=icons[1:])
        return True, output_path
    except Exception as e:
        return False, str(e)

def get_supported_formats():

    return ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif', '*.ico']