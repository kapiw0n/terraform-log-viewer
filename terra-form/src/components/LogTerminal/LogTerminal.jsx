import React, { useState } from 'react';
import './LogTerminal.css';

const LogTerminal = ({ 
  logs, 
  filters, 
  onFilterChange, 
  onShowJson, 
  isDarkTheme, 
  onThemeToggle,
  onDeleteCurrent,
  historyCount,
  wasLogDeleted,
  pagination,
  onPageChange,
  isLoading,
  currentFileId
}) => {
  const [readLogs, setReadLogs] = useState(new Set());
  const [hideRead, setHideRead] = useState(false);

  const markAsRead = (logId) => {
    setReadLogs(prev => new Set([...prev, logId]));
  };

  const unmarkAsRead = (logId) => {
    setReadLogs(prev => {
      const newSet = new Set(prev);
      newSet.delete(logId);
      return newSet;
    });
  };

  const markAllAsRead = () => {
    const allIds = new Set(logs.map(log => log.id));
    setReadLogs(allIds);
  };

  const unmarkAllAsRead = () => {
    setReadLogs(new Set());
  };

  // Фильтрация логов
  let displayedLogs = logs || [];
  
  if (hideRead) {
    displayedLogs = displayedLogs.filter(log => !readLogs.has(log.id));
  }

  const readCount = readLogs.size;
  const unreadCount = displayedLogs.length - readCount;

  // Пагинация
  const handlePreviousPage = () => {
    if (pagination.page > 1) {
      onPageChange(pagination.page - 1);
    }
  };

  const handleNextPage = () => {
    if (pagination.page < pagination.totalPages) {
      onPageChange(pagination.page + 1);
    }
  };

  const hasLogs = Array.isArray(logs) && logs.length > 0;
  const hasAnyHistory = (historyCount || 0) > 0;

  const parseTimeString = (value) => {
    if (!value || typeof value !== 'string') {
      return { hh: '', mm: '', ss: '', ms: '' };
    }
    const [h, m, rest] = value.split(':');
    const [s, ms] = (rest || '').split('.');
    return {
      hh: h ?? '',
      mm: m ?? '',
      ss: s ?? '',
      ms: ms ?? ''
    };
    
  };

  const formatTimeString = ({ hh, mm, ss, ms }) => {
    const hasAny = (hh || mm || ss || ms);
    if (!hasAny) return '';
    const h = (hh ?? '0').toString();
    const m = (mm ?? '0').toString();
    const s = (ss ?? '0').toString();
    const msec = (ms ?? '0').toString();
    return `${h}:${m}:${s}.${msec}`;
  };

  const handleTimePartChange = (which, part, raw) => {
    const numsOnly = raw.replace(/[^0-9]/g, '');
    const maxLen = part === 'ms' ? 3 : 2;
    const limited = numsOnly.slice(0, maxLen);
    const current = which === 'from' ? parseTimeString(filters.time_from) : parseTimeString(filters.time_to);
    const next = { ...current, [part]: limited };
    const nextStr = formatTimeString(next);
    onFilterChange(which === 'from' ? 'time_from' : 'time_to', nextStr);
  };

  // Функция для рендеринга контента
  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="loading-state">
          <div className="spinner large"></div>
          <p>Loading logs...</p>
        </div>
      );
    }

    if (hasLogs) {
      return (
        <div className="log-list">
          {displayedLogs.map((log, index) => (
            <LogEntry 
              key={log.id || index} 
              log={log} 
              index={index}
              onShowJson={onShowJson}
              isRead={readLogs.has(log.id)}
              onMarkRead={markAsRead}
              onUnmarkRead={unmarkAsRead}
            />
          ))}
        </div>
      );
    }

    // Пустые состояния
    if (!hasAnyHistory) {
      return (
        <div className="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10,9 9,9 8,9"/>
          </svg>
          <h3>No Terraform logs loaded</h3>
          <p>Upload a JSON log file to get started</p>
        </div>
      );
    }

    if (wasLogDeleted || !currentFileId) {
      return (
        <div className="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/>
            <path d="M14 11v6"/>
            <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
          </svg>
          <h3>Selected log was removed</h3>
          <p>Please choose another log from the history</p>
        </div>
      );
    }

    return (
      <div className="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          <line x1="7" y1="11" x2="15" y2="11"/>
        </svg>
        <h3>No results for current filters</h3>
        <p>Try adjusting filters or clearing them</p>
      </div>
    );
  };

  return (
    <div className="log-terminal">
      <div className="terminal-header">
        <div className="header-main">
          <div className="header-left">
            <div className="terminal-title">Terraform Logs</div>
            <div className="terminal-stats">
              {hasLogs ? (
                <>
                  {pagination.totalCount} log entries total
                  {readCount > 0 && ` (${readCount} read, ${unreadCount} unread)`}
                  {isLoading && ' - Loading...'}
                </>
              ) : (
                <>
                  {currentFileId ? 'No logs loaded' : 'No file selected'}
                  {isLoading && ' - Loading...'}
                </>
              )}
            </div>
          </div>
          <div className="header-right">
            <button 
              className="theme-toggle" 
              onClick={onThemeToggle}
              title={isDarkTheme ? "Switch to light theme" : "Switch to dark theme"}
            >
              {isDarkTheme ? '☀️' : '🌙'}
            </button>
          </div>
        </div>

        <div className="header-controls">
          {/* Пагинация */}
          <div className="pagination-controls">
            <button 
              onClick={handlePreviousPage}
              disabled={pagination.page <= 1 || isLoading || !hasLogs}
              className="pagination-btn"
            >
              ← Previous
            </button>
            
            <span className="pagination-info">
              {hasLogs ? (
                <>Page {pagination.page} of {pagination.totalPages}{pagination.totalCount > 0 && ` (${pagination.totalCount} total)`}</>
              ) : (
                <>No pages</>
              )}
            </span>
            
            <button 
              onClick={handleNextPage}
              disabled={pagination.page >= pagination.totalPages || isLoading || !hasLogs}
              className="pagination-btn"
            >
              Next →
            </button>
            
            <select 
              value={pagination.pageSize}
              onChange={(e) => onPageChange(1, parseInt(e.target.value))}
              disabled={isLoading || !hasLogs}
              className="page-size-select"
            >
              <option value={20}>20 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
              <option value={200}>200 per page</option>
            </select>
          </div>

          {/* Управление прочитанными */}
          {hasLogs && (
            <div className="read-controls">
              <button 
                className={`hide-read-toggle ${hideRead ? 'active' : ''}`}
                onClick={() => setHideRead(!hideRead)}
              >
                {hideRead ? '👁 Show Read' : '👁‍🗨 Hide Read'}
              </button>
              <button onClick={markAllAsRead} className="mark-all-btn">
                ✓ Mark All Read
              </button>
              <button onClick={unmarkAllAsRead} className="unmark-all-btn">
                ✗ Unmark All Read
              </button>
              <button 
                className="delete-current"
                onClick={onDeleteCurrent}
                disabled={!currentFileId}
                title="Delete selected log"
              >
                Delete log list
              </button>
            </div>
          )}

          {/* Фильтры */}
          {filters && (
            <div className="terminal-filters">
              <select 
                value={filters.operation || 'all'} 
                onChange={(e) => onFilterChange('operation', e.target.value)}
              >
                <option value="all">All Operations</option>
                <option value="plan">Plan</option>
                <option value="apply">Apply</option>
                <option value="validate">Validate</option>
                <option value="general">General</option>
              </select>

              {(() => {
                const tf = parseTimeString(filters.time_from);
                const tt = parseTimeString(filters.time_to);
                return (
                  <>
                    <div className="time-range-group" title="Start time">
                      <span className="time-label">From</span>
                      <div className="time-inputs">
                        <input className="time-input hh" inputMode="numeric" placeholder="HH" value={tf.hh} onChange={(e) => handleTimePartChange('from', 'hh', e.target.value)} />
                        <span>:</span>
                        <input className="time-input mm" inputMode="numeric" placeholder="MM" value={tf.mm} onChange={(e) => handleTimePartChange('from', 'mm', e.target.value)} />
                        <span>:</span>
                        <input className="time-input ss" inputMode="numeric" placeholder="SS" value={tf.ss} onChange={(e) => handleTimePartChange('from', 'ss', e.target.value)} />
                        <span>.</span>
                        <input className="time-input ms" inputMode="numeric" placeholder="ms" value={tf.ms} onChange={(e) => handleTimePartChange('from', 'ms', e.target.value)} />
                      </div>
                    </div>
                    <div className="time-range-group" title="End time">
                      <span className="time-label">To</span>
                      <div className="time-inputs">
                        <input className="time-input hh" inputMode="numeric" placeholder="HH" value={tt.hh} onChange={(e) => handleTimePartChange('to', 'hh', e.target.value)} />
                        <span>:</span>
                        <input className="time-input mm" inputMode="numeric" placeholder="MM" value={tt.mm} onChange={(e) => handleTimePartChange('to', 'mm', e.target.value)} />
                        <span>:</span>
                        <input className="time-input ss" inputMode="numeric" placeholder="SS" value={tt.ss} onChange={(e) => handleTimePartChange('to', 'ss', e.target.value)} />
                        <span>.</span>
                        <input className="time-input ms" inputMode="numeric" placeholder="ms" value={tt.ms} onChange={(e) => handleTimePartChange('to', 'ms', e.target.value)} />
                      </div>
                    </div>
                  </>
                );
              })()}

              <select 
                value={filters.level || 'all'} 
                onChange={(e) => onFilterChange('level', e.target.value)}
              >
                <option value="all">All Levels</option>
                <option value="error">Error</option>
                <option value="warn">Warning</option>
                <option value="info">Info</option>
                <option value="debug">Debug</option>
                <option value="trace">Trace</option>
              </select>
              
              <select 
                value={filters.component || 'all'} 
                onChange={(e) => onFilterChange('component', e.target.value)}
              >
                <option value="all">All Components</option>
                <option value="core">Core</option>
                <option value="backend">Backend</option>
                <option value="provider">Provider</option>
                <option value="plugin">Plugin</option>
                <option value="http">HTTP</option>
                <option value="grpc">gRPC</option>
              </select>
              
              <input
                type="text"
                placeholder="Request ID..."
                value={filters.req_id || ''}
                onChange={(e) => onFilterChange('req_id', e.target.value)}
                className="text-input"
              />
              
              <input
                type="text"
                placeholder="Search messages..."
                value={filters.search_text || ''}
                onChange={(e) => onFilterChange('search_text', e.target.value)}
                className="text-input"
              />
            </div>
          )}
        </div>
      </div>
      
      <div className="terminal-content">
        {renderContent()}
      </div>
    </div>
  );
};

// Компонент LogEntry остается без изменений
const LogEntry = ({ log, index, onShowJson, isRead, onMarkRead, onUnmarkRead }) => {
  const [expanded, setExpanded] = useState(false);

  const getLogType = () => {
    return log.operation || log.type || 'GENERAL';
  };

  const getLogLevel = () => {
    return log.level || 'info';
  };

  const getLevelColor = (level) => {
    const levelMap = {
      'error': 'error', 'warn': 'warn', 'warning': 'warn',
      'info': 'info', 'debug': 'debug', 'trace': 'trace', 'unknown': 'unknown'
    };
    return levelMap[level?.toLowerCase()] || 'unknown';
  };

  const getTypeColor = (type) => {
    const typeMap = {
      'plan': '#10b981', 'apply': '#f59e0b', 'validate': '#8b5cf6',
      'general': '#3b82f6', 'unknown': '#6b7280'
    };
    return typeMap[type?.toLowerCase()] || '#8b5cf6';
  };

  const logType = getLogType();
  const logLevel = getLogLevel();

  const handleClick = () => {
    setExpanded(!expanded);
  };

  const handleMarkClick = (e) => {
    e.stopPropagation();
    if (isRead) {
      onUnmarkRead(log.id);
    } else {
      onMarkRead(log.id);
    }
  };
  

  return (
    <div className={`log-entry level-${getLevelColor(logLevel)} ${expanded ? 'expanded' : ''} ${isRead ? 'read' : ''}`}>
      <div className="log-main" onClick={handleClick}>
        {/* Обновленный индикатор прочитанности - кружок с галочкой */}
        <button 
          className={`read-indicator ${isRead ? 'read' : ''}`}
          onClick={handleMarkClick}
          title={isRead ? "Пометить как непрочитанное" : "Пометить как прочитанное"}
        >
          {isRead ? '✓' : ''}
        </button>

        <span className="log-type" style={{ color: getTypeColor(logType) }}>
          [{logType}]
        </span>
        <span className="log-time">[{log.timestamp || '--:--:--'}]</span>
        <span className="log-level">[{logLevel.toUpperCase()}]</span>
        
        {log.component && log.component !== 'UNKNOWN' && (
          <span className="log-component">[{log.component}]</span>
        )}
        
        {log.tf_req_id && (
          <span className="log-req-id" title="Request ID">#{log.tf_req_id}</span>
        )}
        
        <span className="log-message">{log.message}</span>
        
        {log.has_json_bodies && (
          <button 
            className="json-button"
            onClick={(e) => {
              e.stopPropagation();
              onShowJson(log.id);
            }}
            title="Показать JSON тела"
          >
            { }
          </button>
        )}
        
        <button className="expand-button">
          {expanded ? '▼' : '▶️'}
        </button>
      </div>
      
      {expanded && (
        <div className="log-details">
          <div className="detail-section">
            <h4>Детали записи:</h4>
            <div className="detail-grid">
              {log.operation && <div><strong>Операция:</strong> {log.operation}</div>}
              {log.component && <div><strong>Компонент:</strong> {log.component}</div>}
              {log.message_type && <div><strong>Тип сообщения:</strong> {log.message_type}</div>}
              {log.tf_req_id && <div><strong>Request ID:</strong> {log.tf_req_id}</div>}
              {log.tf_resource_type && <div><strong>Ресурс:</strong> {log.tf_resource_type}</div>}
              {log.tf_rpc && <div><strong>RPC:</strong> {log.tf_rpc}</div>}
              {log.line_number && <div><strong>Строка:</strong> {log.line_number}</div>}
            </div>
          </div>
          
          {log.raw_data && (
            <div className="detail-section">
              <h4>Исходные данные:</h4>
              <pre className="raw-json">{JSON.stringify(log.raw_data, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LogTerminal;