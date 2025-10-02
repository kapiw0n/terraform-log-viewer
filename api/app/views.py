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
    try:
        log_file = request.FILES['log_file']

        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as tmp_file:
            for chunk in log_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        parser = TerraformLogParser()
        result = parser.parse_file(tmp_path)

        os.unlink(tmp_path)

        file_id = str(uuid.uuid4())
        parsed_filename = f"{file_id}_parsed.json"
        parsed_file_path = os.path.join(settings.LOG_STORAGE_DIR, parsed_filename)

        with open(parsed_file_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'original_filename': log_file.name,
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'file_id': file_id
                },
                'parsed_data': result
            }, f, ensure_ascii=False, indent=2)

        DATA_STORAGE[file_id] = {
            'raw_data': result,
            'filename': log_file.name,
            'file_path': parsed_file_path,
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
            'filename': log_file.name
        })
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def handle_get_logs(request, session_id):
    try:
        file_id = request.POST.get('file_id')
        if not file_id:
            return JsonResponse({'logs': [], 'total_count': 0, 'current_file': None})

        if file_id not in DATA_STORAGE:
            file_path, _ = find_file_on_disk(file_id)
            if file_path and os.path.exists(file_path):
                if file_path.endswith('_parsed.json'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = json.load(f)

                    metadata = file_content.get('metadata', {})
                    result = file_content.get('parsed_data', {})

                    DATA_STORAGE[file_id] = {
                        'raw_data': result,
                        'filename': metadata.get('original_filename', 'Unknown'),
                        'file_path': file_path,
                        'session_id': metadata.get('session_id', session_id),
                        'timestamp': metadata.get('timestamp', os.path.getctime(file_path))
                    }
                else:
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

        if file_data['session_id'] != session_id:
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

        logs = file_data['raw_data']['logs']

        filtered_logs = apply_filters(logs, request.POST)

        json_bodies = file_data['raw_data'].get('json_bodies', {})
        for log in filtered_logs:
            log['has_json_bodies'] = log['id'] in json_bodies

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
    
    level = params.get('level')
    if level and level != 'all':
        filtered = [log for log in filtered if log.get('level') == level]
    
    operation = params.get('operation')
    if operation and operation != 'all':
        filtered = [log for log in filtered if log.get('operation') == operation]
    
    component = params.get('component')
    if component and component != 'all':
        filtered = [log for log in filtered if log.get('component') == component]
    
    req_id = params.get('req_id')
    if req_id:
        filtered = [log for log in filtered if req_id in log.get('tf_req_id', '')]
    
    search_text = params.get('search_text')
    if search_text:
        search_lower = search_text.lower()
        filtered = [log for log in filtered if (
            search_lower in log.get('message', '').lower() or
            search_lower in log.get('tf_resource_type', '').lower() or
            search_lower in log.get('tf_rpc', '').lower()
        )]

    body_filter = params.get('body_filter')
    if body_filter and body_filter != 'all':
        if body_filter == 'has_req_body':
            filtered = [log for log in filtered if log.get('raw_data') and 'tf_http_req_body' in log['raw_data']]
        elif body_filter == 'has_res_body':
            filtered = [log for log in filtered if log.get('raw_data') and 'tf_http_res_body' in log['raw_data']]
        elif body_filter == 'has_both':
            filtered = [log for log in filtered if log.get('raw_data') and ('tf_http_req_body' in log['raw_data'] or 'tf_http_res_body' in log['raw_data'])]

    rawDataSearch = params.get('rawDataSearch')
    if rawDataSearch:
        search_lower = rawDataSearch.lower()
        filtered = [log for log in filtered if log.get('raw_data') and search_lower in json.dumps(log['raw_data'], ensure_ascii=False).lower()]

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
            if file_id in DATA_STORAGE and DATA_STORAGE[file_id]['session_id'] == session_id:
                file_data = DATA_STORAGE[file_id]
                file_path = file_data.get('file_path')
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Deleted file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")
                
                del DATA_STORAGE[file_id]
        else:
            files_to_delete = [
                file_id for file_id, data in DATA_STORAGE.items() 
                if data['session_id'] == session_id
            ]
            for file_id in files_to_delete:
                file_data = DATA_STORAGE[file_id]
                file_path = file_data.get('file_path')
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Deleted file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")
                
                del DATA_STORAGE[file_id]
        
        return JsonResponse({'status': 'success', 'message': 'Данные очищены'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def cleanup_old_data(max_age_hours=24):
    """Очищает данные старше указанного времени"""
    import time
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    files_to_delete = [
        file_id for file_id, data in DATA_STORAGE.items()
        if current_time - data['timestamp'] > max_age_seconds
    ]
    
    deleted_count = 0
    for file_id in files_to_delete:
        file_data = DATA_STORAGE[file_id]
        file_path = file_data.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted parsed file: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting parsed file {file_path}: {e}")
        
        del DATA_STORAGE[file_id]
    
    if os.path.exists(settings.LOG_STORAGE_DIR):
        for filename in os.listdir(settings.LOG_STORAGE_DIR):
            file_path = os.path.join(settings.LOG_STORAGE_DIR, filename)
            file_age = current_time - os.path.getctime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    print(f"Deleted old file: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting old file {file_path}: {e}")
    
    return deleted_count
def find_file_on_disk(file_id):
    """Ищет файл с ПАРСИРОВАННЫМИ данными на диске по file_id"""
    if not os.path.exists(settings.LOG_STORAGE_DIR):
        return None, None
    
    parsed_filename = f"{file_id}_parsed.json"
    parsed_file_path = os.path.join(settings.LOG_STORAGE_DIR, parsed_filename)
    
    if os.path.exists(parsed_file_path):
        return parsed_file_path, None
    
    for filename in os.listdir(settings.LOG_STORAGE_DIR):
        if filename.startswith(file_id + '_') and not filename.endswith('_parsed.json'):
            return os.path.join(settings.LOG_STORAGE_DIR, filename), None
    
    return None, None

def convert_old_files_to_parsed():
    """Конвертирует старые исходные файлы в формат с парсированными данными"""
    if not os.path.exists(settings.LOG_STORAGE_DIR):
        return 0
    
    converted_count = 0
    parser = TerraformLogParser()
    
    for filename in os.listdir(settings.LOG_STORAGE_DIR):
        file_path = os.path.join(settings.LOG_STORAGE_DIR, filename)
        
        if filename.endswith('_parsed.json'):
            continue
            
        if '_' not in filename:
            continue
            
        try:
            file_id, original_name = filename.split('_', 1)
            
            result = parser.parse_file(file_path)
            
            parsed_filename = f"{file_id}_parsed.json"
            parsed_file_path = os.path.join(settings.LOG_STORAGE_DIR, parsed_filename)
            
            with open(parsed_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'original_filename': original_name,
                        'session_id': 'converted',  
                        'timestamp': os.path.getctime(file_path),
                        'file_id': file_id
                    },
                    'parsed_data': result
                }, f, ensure_ascii=False, indent=2)
            
            os.remove(file_path)
            converted_count += 1
            print(f"Converted {filename} to parsed format")
            
        except Exception as e:
            print(f"Error converting {filename}: {e}")
    
    return converted_count
