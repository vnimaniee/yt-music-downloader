import os
import sys
import locale

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_system_locale():
    winlocale_to_rfc1766 = {
        'English_United States': 'en_US',
        'Korean_Korea': 'ko_KR' 
    }
    sys_locale, _ = locale.getlocale()
    if "win" in sys.platform and sys_locale not in winlocale_to_rfc1766.values():
        try:
            sys_locale = winlocale_to_rfc1766[sys_locale]
        except KeyError:
            return None
    
    return sys_locale
