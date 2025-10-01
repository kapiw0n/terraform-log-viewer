import json
import os
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.shortcuts import render
from .parser import TerraformLogParser
import tempfile
import time
from django.conf import settings

# Глобальное хранилище для данных (вместо БД)
# На практике для продакшена лучше использовать Redis или файловую систему с индексацией
DATA_STORAGE = {}

@csrf_exempt
def terraform_logs_view(request):
    if request.method == 'GET':
        return render(request, 'logs.html')
    
    elif request.method == 'POST':
        session_id = request.COOKIES.get('session_id') or request.POST.get('session_id')
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if request.FILES.get('log_file'):
            return handle_file_upload(request, session_id)
        
        action = request.POST.get('action')
        
        if action == 'get_logs':
            return handle_get_logs(request, session_id)
        elif action == 'get_json_bodies':
            return handle_get_json_bodies(request, session_id)
        elif action == 'clear_data':
            return handle_clear_data(request, session_id)
        elif action == 'get_statistics':
            return handle_get_statistics(request, session_id)
        elif action == 'get_session':
            return JsonResponse({'session_id': session_id})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

def handle_file_upload(request, session_id):
    """Обрабатывает загрузку файла и сохраняет данные на диск"""
    try:
        log_file = request.FILES['log_file']
        
        # Сохраняем исходный файл на диск
        file_id = str(uuid.uuid4())
        # Сохраняем оригинальное имя файла отдельно
        original_filename = log_file.name
        # Сохраняем файл с ID в имени, но запоминаем оригинальное имя
        file_path = os.path.join(settings.LOG_STORAGE_DIR, f"{file_id}_{original_filename}")
        
        with open(file_path, 'wb+') as destination:
            for chunk in log_file.chunks():
                destination.write(chunk)
        
        parser = TerraformLogParser()
        result = parser.parse_file(file_path)
        
        # Сохраняем метаданные в DATA_STORAGE
        DATA_STORAGE[file_id] = {
            'raw_data': result,
            'filename': original_filename,  # Сохраняем оригинальное имя
            'file_path': file_path,
            'session_id': session_id,
            'timestamp': time.time()
        }
        
        return JsonResponse({
            'status': 'success', 
            'message': f'Файл успешно обработан. Записей: {result["count"]}',
            'count': result['count'],
            'statistics': result['statistics'],
            'file_id': file_id,
            'session_id': session_id,
            'filename': original_filename  # Возвращаем оригинальное имя
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def handle_get_logs(request, session_id):
    """Обрабатывает запрос на получение логов с фильтрами"""
    try:
        file_id = request.POST.get('file_id')
        if not file_id:
            return JsonResponse({'logs': [], 'total_count': 0, 'current_file': None})
        
        # Если файла нет в памяти, пробуем загрузить с диска
        if file_id not in DATA_STORAGE:
            file_path = find_file_on_disk(file_id)
            if file_path and os.path.exists(file_path):
                parser = TerraformLogParser()
                result = parser.parse_file(file_path)
                
                DATA_STORAGE[file_id] = {
                    'raw_data': result,
                    'filename': os.path.basename(file_path).split('_', 1)[1],
                    'file_path': file_path,
                    'session_id': session_id,
                    'timestamp': os.path.getctime(file_path)
                }
            else:
                return JsonResponse({'logs': [], 'total_count': 0, 'current_file': None})
        
        file_data = DATA_STORAGE[file_id]
        
        # Проверяем принадлежность сессии
        if file_data['session_id'] != session_id:
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        
        logs = file_data['raw_data']['logs']
        
        # Применяем фильтры
        filtered_logs = apply_filters(logs, request.POST)
        
        # Добавляем флаг наличия JSON тел
        json_bodies = file_data['raw_data'].get('json_bodies', {})
        for log in filtered_logs:
            log['has_json_bodies'] = log['id'] in json_bodies
        
        # Пагинация
        page = int(request.POST.get('page', 1))
        page_size = int(request.POST.get('page_size', 100))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated_logs = filtered_logs[start_idx:end_idx]
        
        return JsonResponse({
            'logs': paginated_logs,
            'total_count': len(filtered_logs),
            'current_file': file_data['filename'],
            'page': page,
            'page_size': page_size,
            'total_pages': (len(filtered_logs) + page_size - 1) // page_size
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def apply_filters(logs, params):
    """Применяет фильтры к логам"""
    filtered = logs
    
    # Фильтр по уровню
    level = params.get('level')
    if level and level != 'all':
        filtered = [log for log in filtered if log.get('level') == level]
    
    # Фильтр по операции
    operation = params.get('operation')
    if operation and operation != 'all':
        filtered = [log for log in filtered if log.get('operation') == operation]
    
    # Фильтр по компоненту
    component = params.get('component')
    if component and component != 'all':
        filtered = [log for log in filtered if log.get('component') == component]
    
    # Фильтр по req_id
    req_id = params.get('req_id')
    if req_id:
        filtered = [log for log in filtered if req_id in log.get('tf_req_id', '')]
    
    # Полнотекстовый поиск
    search_text = params.get('search_text')
    if search_text:
        search_lower = search_text.lower()
        filtered = [log for log in filtered if (
            search_lower in log.get('message', '').lower() or
            search_lower in log.get('tf_resource_type', '').lower() or
            search_lower in log.get('tf_rpc', '').lower()
        )]

    # Фильтр по временному интервалу по явным границам time_from/time_to в формате HH:MM:SS.mmm
    def parse_ts(ts_str: str):
        try:
            if not isinstance(ts_str, str):
                return None
            parts = ts_str.split(':')
            if len(parts) < 3:
                return None
            hours = int(parts[0])
            minutes = int(parts[1])
            sec_parts = parts[2].split('.')
            seconds = int(sec_parts[0])
            millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
            return hours * 3600_000 + minutes * 60_000 + seconds * 1000 + millis
        except Exception:
            return None

    time_from = params.get('time_from')
    time_to = params.get('time_to')
    if (time_from or time_to) and filtered:
        from_ms = parse_ts(time_from) if time_from else None
        to_ms = parse_ts(time_to) if time_to else None
        if from_ms is not None or to_ms is not None:
            def in_range(log):
                ts = parse_ts(log.get('timestamp'))
                if ts is None:
                    return False
                if from_ms is not None and ts < from_ms:
                    return False
                if to_ms is not None and ts > to_ms:
                    return False
                return True
            filtered = [log for log in filtered if in_range(log)]
    
    # Сортировка по номеру строки
    filtered.sort(key=lambda x: x['line_number'])
    
    return filtered

def handle_get_json_bodies(request, session_id):
    """Обрабатывает запрос на получение JSON тел"""
    try:
        file_id = request.POST.get('file_id')
        log_id = request.POST.get('log_id')
        
        if not file_id or file_id not in DATA_STORAGE:
            return JsonResponse({'json_bodies': []})
        
        file_data = DATA_STORAGE[file_id]
        
        # Проверяем принадлежность сессии
        if file_data['session_id'] != session_id:
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        
        json_bodies = file_data['raw_data'].get('json_bodies', {})
        
        if log_id and log_id in json_bodies:
            return JsonResponse({'json_bodies': json_bodies[log_id]})
        else:
            return JsonResponse({'json_bodies': []})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def handle_clear_data(request, session_id):
    """Очищает данные для конкретной сессии"""
    try:
        file_id = request.POST.get('file_id')
        
        if file_id:
            # Удаляем конкретный файл
            if file_id in DATA_STORAGE and DATA_STORAGE[file_id]['session_id'] == session_id:
                del DATA_STORAGE[file_id]
        else:
            # Удаляем все файлы сессии
            files_to_delete = [
                file_id for file_id, data in DATA_STORAGE.items() 
                if data['session_id'] == session_id
            ]
            for file_id in files_to_delete:
                del DATA_STORAGE[file_id]
        
        return JsonResponse({'status': 'success', 'message': 'Данные очищены'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def handle_get_statistics(request, session_id):
    """Возвращает статистику"""
    try:
        file_id = request.POST.get('file_id')
        if not file_id or file_id not in DATA_STORAGE:
            return JsonResponse({'statistics': {}})
        
        file_data = DATA_STORAGE[file_id]
        
        # Проверяем принадлежность сессии
        if file_data['session_id'] != session_id:
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        
        return JsonResponse({'statistics': file_data['raw_data'].get('statistics', {})})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Фоновая задача для очистки устаревших данных (можно запускать по cron)
def cleanup_old_data(max_age_hours=24):
    """Очищает данные старше указанного времени"""
    import time
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    files_to_delete = [
        file_id for file_id, data in DATA_STORAGE.items()
        if current_time - data['timestamp'] > max_age_seconds
    ]
    
    for file_id in files_to_delete:
        del DATA_STORAGE[file_id]
    
    return len(files_to_delete)

def find_file_on_disk(file_id):
    """Ищет файл на диске по file_id"""
    if not os.path.exists(settings.LOG_STORAGE_DIR):
        return None
    
    for filename in os.listdir(settings.LOG_STORAGE_DIR):
        if filename.startswith(file_id + '_'):
            return os.path.join(settings.LOG_STORAGE_DIR, filename)
    return None