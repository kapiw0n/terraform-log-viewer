import React from 'react';
import './LogHistory.css';

const LogHistory = ({ history, selectedItem, onSelect, onClear }) => {
  console.log('LogHistory rendering with', history?.length, 'items');
  
  if (!history || history.length === 0) {
    return (
      <div className="log-history">
        <div className="history-header">
          <h3>History</h3>
        </div>
        <div className="empty-history">
          No log files loaded yet
        </div>
      </div>
    );
  }

  return (
    <div className="log-history">
      <div className="history-header">
        <h3>History ({history.length})</h3>
        <button className="clear-button" onClick={onClear} title="Clear all history">
          Clear All
        </button>
      </div>
      
      <div className="history-list">
        {history.map((item) => (
          <div
            key={item.fileId || item.id}
            className={`history-item ${selectedItem === item.id ? 'selected' : ''}`}
            onClick={() => onSelect(item)}
            title={`Click to load ${item.name}`}
          >
            <div className="history-name">{item.name || 'Unnamed file'}</div>
            <div className="history-timestamp">{item.timestamp || 'Unknown date'}</div>
            <div className="history-stats">
              <span className="log-count">{item.count || 0} logs</span>
              {item.statistics && item.statistics.levels && (
                <span className="level-stats">
                  {Object.entries(item.statistics.levels).map(([level, count]) => (
                    <span key={level} className={`level-badge level-${level.toLowerCase()}`}>
                      {level}:{count}
                    </span>
                  ))}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LogHistory;