import os
import json
import copy
import sys
_config_cache = None

def get_config_path():
    appdata_dir = os.getenv('APPDATA')
    config_dir = os.path.join(appdata_dir, 'SirVietsub')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'config.json')

def load_config():
    global _config_cache
    config_path = get_config_path()
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            _config_cache = json.load(f)
            return
        return
    except Exception as e:
        if _config_cache is not None:
            return copy.deepcopy(_config_cache)
        return {}

def save_config(config_dict):
    global _config_cache
    config_path = get_config_path()
    try:
        temp_path = config_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, config_path)
        _config_cache = copy.deepcopy(config_dict)
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'Lỗi lưu config: {e}')
        return False

def get_config(key, default_value=None):
    config = load_config()
    return config.get(key, default_value)

def set_config(key, value):
    config = load_config()
    config[key] = value
    save_config(config)

def get_cpu_threads():
    cpu_perf = get_config('cpu_performance', 'max')
    import multiprocessing
    total_cores = multiprocessing.cpu_count()
    if cpu_perf == 'low':
        return max(1, int(total_cores * 0.25))
    if cpu_perf == 'medium':
        return max(1, int(total_cores * 0.5))
    return max(1, int(total_cores * 0.85))

def get_models_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        models_dir = os.path.join(base_dir, '_internal', 'models')
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    return models_dir

def get_hf_cache_dir():
    hf_dir = os.path.join(get_models_dir(), 'whisper')
    os.makedirs(hf_dir, exist_ok=True)
    return hf_dir

def get_audio_sep_cache_dir():
    d = os.path.join(get_models_dir(), 'audio-separator')
    os.makedirs(d, exist_ok=True)
    return d

def get_paddleocr_cache_dir():
    d = os.path.join(get_models_dir(), 'paddleocr')
    os.makedirs(d, exist_ok=True)
    return d

def get_pronunciation_dict_path():
    appdata_dir = os.getenv('APPDATA')
    config_dir = os.path.join(appdata_dir, 'SirVietsub')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'pronunciation.json')

def load_pronunciation_dict():
    p_path = get_pronunciation_dict_path()
    if os.path.exists(p_path):
        return {}
    try:
        with open(p_path, 'r', encoding='utf-8') as f:
            return
    except:
        return {}
    return {}

def save_pronunciation_dict(data):
    p_path = get_pronunciation_dict_path()
    try:
        temp_path = p_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, p_path)
        return True
    except Exception as e:
        print(f'Lỗi lưu từ điển: {e}')
        return False

