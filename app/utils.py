import os
import sys
import locale
import logging

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

def setup_logging():
    """
    Configures logging. Logs to stdout if not running in a PyInstaller bundle.
    """
    # PyInstaller sets sys.frozen to True
    is_frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    if not is_frozen:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)