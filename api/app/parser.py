import json
import re
from datetime import datetime

class TerraformLogParser:
    def __init__(self):
        self.parsed_logs = []

    def parse_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    self.process_log_entry(data, line_num)
                except json.JSONDecodeError:
                    self.process_raw_line(line, line_num)

        return {
            'count': len(self.parsed_logs),
            'logs': self.parsed_logs,
            'statistics': self.generate_statistics()
        }

    def process_log_entry(self, data, line_num):
        parsed_data = self.parse_json_bodies_in_data(data)

        operation = self.detect_operation(parsed_data)
        level = self.extract_level(parsed_data)
        component = self.detect_component(parsed_data)
        message_type = self.detect_message_type(parsed_data)

        log_entry = {
            'id': f"log_{line_num}",
            'timestamp': self.extract_timestamp(parsed_data),
            'level': level,
            'operation': operation,
            'component': component,
            'message_type': message_type,
            'message': self.extract_message(parsed_data),
            'raw_data': parsed_data,
            'line_number': line_num,
            'tf_req_id': parsed_data.get('@request_id') or parsed_data.get('tf_req_id') or parsed_data.get('req_id', ''),
            'tf_resource_type': parsed_data.get('@resource_type') or parsed_data.get('tf_resource_type') or parsed_data.get('resource_type', ''),
            'tf_rpc': parsed_data.get('@rpc') or parsed_data.get('tf_rpc') or parsed_data.get('rpc', '')
        }

        self.parsed_logs.append(log_entry)

    def parse_json_bodies_in_data(self, data):
        result = data.copy()

        json_fields = ['tf_http_req_body', 'tf_http_res_body']

        for field in json_fields:
            if field in result and result[field]:
                field_value = result[field]

                if isinstance(field_value, str) and field_value.strip():
                    try:
                        parsed_json = json.loads(field_value)
                        result[field] = parsed_json
                    except json.JSONDecodeError:
                        try:
                            unescaped = field_value.encode().decode('unicode_escape')
                            parsed_json = json.loads(unescaped)
                            result[field] = parsed_json
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass

        return result

    def process_raw_line(self, line, line_num):
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

    def detect_operation(self, data):
        message = self.extract_message(data)
        message_lower = message.lower()

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

        if 'plan' in str(data.get('@module', '')).lower():
            return 'plan'
        elif 'apply' in str(data.get('@module', '')).lower():
            return 'apply'
        elif 'init' in str(data.get('@module', '')).lower():
            return 'init'

        rpc_type = data.get('tf_rpc', '')
        if 'plan' in rpc_type.lower():
            return 'plan'
        elif 'apply' in rpc_type.lower():
            return 'apply'

        return 'general'

    def detect_operation_from_raw(self, line):
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

    def detect_component(self, data):
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

    def detect_component_from_raw(self, line):
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

    def detect_message_type(self, data):
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

    def extract_level(self, data):
        level_fields = ['@level', 'level', 'log_level', 'severity']
        for field in level_fields:
            level = data.get(field)
            if level:
                level_str = str(level).lower()
                if level_str in ['error', 'warn', 'warning', 'info', 'debug', 'trace']:
                    return 'warn' if level_str == 'warning' else level_str

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

    def extract_level_from_raw(self, line):
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

    def extract_timestamp(self, data):
        timestamp_fields = ['@timestamp', 'timestamp', 'time', '@time']

        for field in timestamp_fields:
            timestamp_str = data.get(field)
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, str):
                        if 'Z' in timestamp_str:
                            timestamp_str = timestamp_str.replace('Z', '+00:00')

                        dt = datetime.fromisoformat(timestamp_str)
                        return dt.strftime('%H:%M:%S.%f')[:-3]
                except (ValueError, TypeError):
                    continue

        return '--:--:--'

    def extract_timestamp_from_raw(self, line):
        patterns = [
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}:\d{2}\.\d{3}'
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                timestamp = match.group()
                if '.' in timestamp:
                    timestamp = timestamp.split('.')[0]
                return timestamp

        return '--:--:--'

    def extract_req_id_from_raw(self, line):
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

    def extract_message(self, data):
        message_fields = ['@message', 'message', 'msg', 'log', 'text']

        for field in message_fields:
            message = data.get(field)
            if message:
                return str(message)

        return json.dumps(data, ensure_ascii=False)

    def generate_statistics(self):
        stats = {
            'total_entries': len(self.parsed_logs),
            'by_level': {},
            'by_operation': {},
            'by_component': {},
            'errors_count': 0
        }

        for log in self.parsed_logs:
            level = log['level']
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1

            operation = log['operation']
            stats['by_operation'][operation] = stats['by_operation'].get(operation, 0) + 1

            component = log['component']
            stats['by_component'][component] = stats['by_component'].get(component, 0) + 1

            if log['level'] == 'error':
                stats['errors_count'] += 1

        return stats
