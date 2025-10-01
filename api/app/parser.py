import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class TerraformLogParser:
    def __init__(self):
        self.parsed_logs = []
        self.json_bodies_map = {}
        # Убрали глобальное состояние current_operation
    
    def parse_file(self, file_path: str) -> Dict:
        """Основной метод парсинга файла логов"""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    self.process_log_entry(data, line_num)
                except json.JSONDecodeError:
                    # Обрабатываем не-JSON строки с эвристиками
                    self.process_raw_line(line, line_num)
        
        return {
            'count': len(self.parsed_logs),
            'logs': self.parsed_logs,
            'json_bodies': self.json_bodies_map,
            'statistics': self.generate_statistics()
        }
    
    def process_log_entry(self, data: Dict, line_num: int):
        """Обрабатывает JSON запись лога"""
        # Определяем операцию, уровень и компонент
        operation = self.detect_operation(data)
        level = self.extract_level(data)
        component = self.detect_component(data)
        message_type = self.detect_message_type(data)
        
        # Создаем структурированную запись
        log_entry = {
            'id': f"log_{line_num}",
            'timestamp': self.extract_timestamp(data),
            'level': level,
            'operation': operation,
            'component': component,
            'message_type': message_type,
            'message': self.extract_message(data),
            'raw_data': data,
            'line_number': line_num,
            'tf_req_id': data.get('@request_id') or data.get('tf_req_id') or data.get('req_id', ''),
            'tf_resource_type': data.get('@resource_type') or data.get('tf_resource_type') or data.get('resource_type', ''),
            'tf_rpc': data.get('@rpc') or data.get('tf_rpc') or data.get('rpc', '')
        }
        
        self.parsed_logs.append(log_entry)
        self.extract_json_bodies(log_entry['id'], data)
    
    def process_raw_line(self, line: str, line_num: int):
        """Обрабатывает не-JSON строки с помощью эвристик"""
        # Эвристики для извлечения данных из raw строк
        timestamp = self.extract_timestamp_from_raw(line)
        level = self.extract_level_from_raw(line)
        operation = self.detect_operation_from_raw(line)
        component = self.detect_component_from_raw(line)
        
        log_entry = {
            'id': f"raw_{line_num}",
            'timestamp': timestamp,
            'level': level,
            'operation': operation,
            'component': component,
            'message_type': 'RAW',
            'message': line,
            'raw_data': {'raw_line': line},
            'line_number': line_num,
            'tf_req_id': self.extract_req_id_from_raw(line),
            'tf_resource_type': '',
            'tf_rpc': ''
        }
        
        self.parsed_logs.append(log_entry)
    
    def detect_operation(self, data: Dict) -> str:
        """Определяет операцию Terraform с улучшенной эвристикой"""
        message = self.extract_message(data)
        message_lower = message.lower()
        
        # Улучшенные маркеры операций (в нижнем регистре)
        operation_markers = {
            'plan': [
                'plan',
                'terraform plan',
                'plan operation',
                'planning',
                'refresh plan',
                'plan:',
                '-plan-',
                'execution plan',
                'proposed changes',
                'speculative plan',
                'no actions need to be taken',
                'planned change',
                'refresh:'
            ],
            'apply': [
                'apply',
                'terraform apply', 
                'apply operation',
                'applying',
                'apply:',
                '-apply-',
                'provisioning',
                'deploying',
                'creating',
                'modifying',
                'destroying',
                'executing actions',
                'applying configuration'
            ],
            'validate': [
                'validate',
                'validation',
                'validating',
                'validate operation',
                'syntax valid',
                'configuration is valid',
                'checking configuration'
            ],
            'init': [
                'init',
                'terraform init',
                'initializing',
                'initialization',
                'init:',
                '-init-',
                'initializing backend',
                'installing plugins',
                'downloading modules',
                'provider installation',
                'module installation',
                'terraform.lock.hcl',
                'required_providers'
            ],
            'destroy': [
                'destroy',
                'terraform destroy',
                'destroying',
                'destroy:',
                'deprovisioning',
                'cleaning up',
                'removing resources',
                'destroy mode',
                'plan to destroy',
                'destroy plan',
                'apply -destroy'
            ],
            'refresh': [
                'refresh',
                'refreshing',
                'refresh:',
                'refresh-only',
                'updating state',
                'synchronizing state',
                'reconcile state'
            ]
        }
        
        for op, markers in operation_markers.items():
            if any(marker in message_lower for marker in markers):
                return op
        
        # Дополнительные эвристики из полей данных
        if 'plan' in str(data.get('@module', '')).lower():
            return 'plan'
        elif 'apply' in str(data.get('@module', '')).lower():
            return 'apply'
        elif 'init' in str(data.get('@module', '')).lower():
            return 'init'
        
        # Эвристика из типа RPC
        rpc_type = data.get('tf_rpc', '')
        if 'plan' in rpc_type.lower():
            return 'plan'
        elif 'apply' in rpc_type.lower():
            return 'apply'
        
        return 'general'
    
    def detect_operation_from_raw(self, line: str) -> str:
        """Определяет операцию из raw строки"""
        line_lower = line.lower()
        
        operation_markers = {
            'plan': ['plan', 'planning'],
            'apply': ['apply', 'applying'],
            'validate': ['validate', 'validation'],
            'init': ['init', 'initializing'],
            'destroy': ['destroy', 'destroying']
        }
        
        for op, markers in operation_markers.items():
            if any(marker in line_lower for marker in markers):
                return op
        
        return 'general'
    
    def detect_component(self, data: Dict) -> str:
        """Определяет компонент системы"""
        message = self.extract_message(data)
        message_lower = message.lower()
        
        component_indicators = {
            'core': [
                'terraform', 'cli', 'command', 'args', 'version',
                'root', 'working directory', 'config'
            ],
            'backend': [
                'backend', 'statemgr', 'state', 'local:', 'remote:',
                'loading state', 'saving state'
            ],
            'provider': [
                'provider', 'registry', 'plugin', 'tf-provider',
                'initializing provider'
            ],
            'provisioner': [
                'provisioner', 'local-exec', 'remote-exec'
            ],
            'http': [
                'http', 'https', 'request', 'response', 'get', 'post',
                'status code', 'header'
            ],
            'grpc': [
                'grpc', 'rpc', 'protocol', 'client', 'server'
            ]
        }
        
        for component, indicators in component_indicators.items():
            if any(indicator in message_lower for indicator in indicators):
                return component
        
        return 'unknown'
    
    def detect_component_from_raw(self, line: str) -> str:
        """Определяет компонент из raw строки"""
        line_lower = line.lower()
        
        component_indicators = {
            'core': ['terraform', 'cli', 'command'],
            'backend': ['backend', 'state'],
            'provider': ['provider', 'registry'],
            'http': ['http', 'request'],
            'grpc': ['grpc', 'rpc']
        }
        
        for component, indicators in component_indicators.items():
            if any(indicator in line_lower for indicator in indicators):
                return component
        
        return 'unknown'
    
    def detect_message_type(self, data: Dict) -> str:
        """Определяет тип сообщения"""
        message = self.extract_message(data)
        message_lower = message.lower()
        
        if 'error' in message_lower or 'failed' in message_lower:
            return 'error'
        elif 'warning' in message_lower or 'warn' in message_lower:
            return 'warning'
        elif 'debug' in message_lower:
            return 'debug'
        elif 'trace' in message_lower:
            return 'trace'
        
        return 'info'
    
    def extract_level(self, data: Dict) -> str:
        """Извлекает уровень логирования"""
        # Прямое получение из полей (приоритет по порядку)
        level_fields = ['@level', 'level', 'log_level', 'severity']
        for field in level_fields:
            level = data.get(field)
            if level:
                level_str = str(level).lower()
                if level_str in ['error', 'warn', 'warning', 'info', 'debug', 'trace']:
                    return 'warn' if level_str == 'warning' else level_str
        
        # Эвристический анализ сообщения
        message = self.extract_message(data).lower()
        
        level_patterns = {
            'error': ['error', 'failed', 'failure', 'exception', 'panic', 'fatal'],
            'warn': ['warn', 'warning', 'deprecated', 'deprecation'],
            'info': ['info', 'starting', 'completed', 'success', 'created', 'updated'],
            'debug': ['debug', 'checking', 'scanning', 'reading', 'writing'],
            'trace': ['trace', 'waiting', 'calling', 'entering', 'exiting']
        }
        
        for level_name, patterns in level_patterns.items():
            if any(pattern in message for pattern in patterns):
                return level_name
        
        return 'info'
    
    def extract_level_from_raw(self, line: str) -> str:
        """Извлекает уровень из raw строки"""
        line_lower = line.lower()
        
        level_patterns = {
            'error': ['error', 'failed', 'failure', 'exception'],
            'warn': ['warn', 'warning'],
            'info': ['info', 'starting', 'completed'],
            'debug': ['debug'],
            'trace': ['trace']
        }
        
        for level_name, patterns in level_patterns.items():
            if any(pattern in line_lower for pattern in patterns):
                return level_name
        
        return 'info'
    
    def extract_timestamp(self, data: Dict) -> str:
        """Извлекает и форматирует timestamp"""
        timestamp_fields = ['@timestamp', 'timestamp', 'time', '@time']
        
        for field in timestamp_fields:
            timestamp_str = data.get(field)
            if timestamp_str:
                try:
                    # Нормализуем формат
                    if isinstance(timestamp_str, str):
                        if 'Z' in timestamp_str:
                            timestamp_str = timestamp_str.replace('Z', '+00:00')
                        
                        dt = datetime.fromisoformat(timestamp_str)
                        return dt.strftime('%H:%M:%S.%f')[:-3]  # HH:MM:SS.mmm
                except (ValueError, TypeError):
                    continue
        
        return '--:--:--'
    
    def extract_timestamp_from_raw(self, line: str) -> str:
        """Пытается извлечь timestamp из raw строки с помощью regex"""
        patterns = [
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',  # ISO format
            r'\d{2}:\d{2}:\d{2}',  # HH:MM:SS
            r'\d{2}:\d{2}:\d{2}\.\d{3}'  # HH:MM:SS.mmm
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                timestamp = match.group()
                # Если есть миллисекунды - убираем их
                if '.' in timestamp:
                    timestamp = timestamp.split('.')[0]
                return timestamp
        
        return '--:--:--'
    
    def extract_req_id_from_raw(self, line: str) -> str:
        """Извлекает request ID из raw строки"""
        patterns = [
            r'req[_\-]id[=:]?\s*([\w\-]+)',
            r'request[_\-]id[=:]?\s*([\w\-]+)',
            r'\[req[_\-]id=([\w\-]+)\]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ''
    
    def extract_message(self, data: Dict) -> str:
        """Извлекает сообщение из различных возможных полей"""
        message_fields = ['@message', 'message', 'msg', 'log', 'text']
        
        for field in message_fields:
            message = data.get(field)
            if message:
                return str(message)
        
        # Если нет явного поля сообщения, используем весь JSON
        return json.dumps(data, ensure_ascii=False)
    
    def extract_json_bodies(self, log_id: str, data: Dict):
        """Извлекает JSON тела из полей запроса/ответа"""
        if not log_id:
            return
        
        json_fields = [
            'tf_http_req_body', 'tf_http_res_body', 
            'request_body', 'response_body',
            'body', 'data', 'json'
        ]
        
        for field in json_fields:
            if field in data and data[field]:
                json_str = data[field]
                if isinstance(json_str, str) and json_str.strip():
                    try:
                        json_data = json.loads(json_str)
                        body_entry = {
                            'field_name': field,
                            'json_data': json_data
                        }
                    except json.JSONDecodeError:
                        body_entry = {
                            'field_name': field,
                            'json_data': {'raw_string': json_str}
                        }
                    
                    if log_id not in self.json_bodies_map:
                        self.json_bodies_map[log_id] = []
                    self.json_bodies_map[log_id].append(body_entry)
    
    def generate_statistics(self) -> Dict:
        """Генерирует статистику по логам"""
        stats = {
            'total_entries': len(self.parsed_logs),
            'by_level': {},
            'by_operation': {},
            'by_component': {},
            'errors_count': 0
        }
        
        for log in self.parsed_logs:
            # Статистика по уровням
            level = log['level']
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
            
            # Статистика по операциям
            operation = log['operation']
            stats['by_operation'][operation] = stats['by_operation'].get(operation, 0) + 1
            
            # Статистика по компонентам
            component = log['component']
            stats['by_component'][component] = stats['by_component'].get(component, 0) + 1
            
            # Подсчет ошибок
            if log['level'] == 'error':
                stats['errors_count'] += 1
        
        return stats