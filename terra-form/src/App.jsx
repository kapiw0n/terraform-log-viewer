import React, { useState, useEffect } from 'react';
import FileUploader from './components/FileUploader/FileUploader';
import LogHistory from './components/LogHistory/LogHistory';
import LogTerminal from './components/LogTerminal/LogTerminal';
import { useLocalStorage } from './hooks/useLocalStorage';
import '../src/styles/App.css';

const App = () => {
  const [logs, setLogs] = useState([]);
  const [history, setHistory] = useLocalStorage('tf_history', []);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);
  const [filters, setFilters] = useState({});
  const [isDarkTheme, setIsDarkTheme] = useLocalStorage('tf_is_dark_theme', false);

  const [sessionId, setSessionId] = useLocalStorage('tf_session_id', null);
  const [currentFileId, setCurrentFileId] = useLocalStorage('tf_current_file_id', null);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 50,
    totalCount: 0,
    totalPages: 0
  });
  const [isLoading, setIsLoading] = useState(false);
  const [wasLogDeleted, setWasLogDeleted] = useState(false);

  useEffect(() => {
    initializeSession();
    restoreHistoryState();
  }, []);

  const restoreHistoryState = async () => {
    if (history.length > 0 && sessionId) {

      if (currentFileId) {
        const currentHistoryItem = history.find(item => item.fileId === currentFileId);
        if (currentHistoryItem) {
          try {
            await loadLogs(currentFileId, 1, pagination.pageSize, filters);
            setSelectedHistoryItem(currentHistoryItem.id);
            setWasLogDeleted(false);
          } catch (error) {
            setCurrentFileId(null);
            setSelectedHistoryItem(null);
            setWasLogDeleted(true);
          }
        }
      }
    }
  };

  useEffect(() => {
    const appElement = document.querySelector('.app');
    if (appElement) {
      if (isDarkTheme) {
        appElement.classList.add('theme-dark');
        appElement.classList.remove('theme-light');
      } else {
        appElement.classList.add('theme-light');
        appElement.classList.remove('theme-dark');
      }
    }
  }, [isDarkTheme]);

  useEffect(() => {
    if (!currentFileId) return;
    const timer = setTimeout(() => {
      loadLogs(currentFileId, 1, pagination.pageSize, filters);
    }, 400);
    return () => clearTimeout(timer);
  }, [filters, currentFileId]);

  const initializeSession = async () => {
    if (!sessionId) {
      try {
        const formData = new FormData();
        formData.append('action', 'get_session');

        const response = await fetch('/api/upload/', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          setSessionId(data.session_id);
        }
      } catch (error) {
        console.error('Failed to initialize session:', error);
        setSessionId('client_' + Date.now());
      }
    }
  };

  const loadLogs = async (fileId = currentFileId, page = 1, pageSize = pagination.pageSize, filters = {}) => {
    if (!fileId) return;

    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('action', 'get_logs');
      formData.append('file_id', fileId);
      formData.append('session_id', sessionId);
      formData.append('page', page.toString());
      formData.append('page_size', pageSize.toString());

      Object.keys(filters).forEach(key => {
        if (filters[key]) {
          formData.append(key, filters[key]);
        }
      });

      const response = await fetch('/api/upload/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      setLogs(data.logs || []);
      setWasLogDeleted(false);
      setPagination({
        page: data.page || 1,
        pageSize: data.page_size || pageSize,
        totalCount: data.total_count || 0,
        totalPages: data.total_pages || 1
      });

      return data;
    } catch (error) {
      console.error('Error loading logs:', error);
      alert(`Error loading logs: ${error.message}`);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (uploadResult) => {
    const { file_id, session_id, filename, statistics, count } = uploadResult;
    
    if (session_id) {
      setSessionId(session_id);
    }
    
    setCurrentFileId(file_id);
    
    const historyItem = {
      id: file_id,
      name: filename,
      timestamp: new Date().toLocaleString(),
      fileId: file_id,
      sessionId: session_id || sessionId,
      statistics,
      count
    };
    
    setHistory(prev => {
      const currentHistory = Array.isArray(prev) ? prev : [];
      const filteredHistory = currentHistory.filter(item => item.fileId !== file_id);
      return [historyItem, ...filteredHistory].slice(0, 1000);
    });
    
    setSelectedHistoryItem(file_id);
    setWasLogDeleted(false);
    
    await loadLogs(file_id, 1, pagination.pageSize, filters);
  };

  const handleHistorySelect = async (item) => {
    setCurrentFileId(item.fileId);
    setSelectedHistoryItem(item.id);
    setWasLogDeleted(false);
    await loadLogs(item.fileId, 1, pagination.pageSize, filters);
  };

  const handleHistoryClear = async () => {
    try {
      const formData = new FormData();
      formData.append('action', 'clear_data');
      formData.append('session_id', sessionId);
      
      await fetch('/api/upload/', {
        method: 'POST',
        body: formData,
      });
    } catch (error) {
      console.error('Error clearing backend data:', error);
    } finally {
      setHistory([]);
      setLogs([]);
      setSelectedHistoryItem(null);
      setCurrentFileId(null);
      setWasLogDeleted(false);
      setPagination({
        page: 1,
        pageSize: 50,
        totalCount: 0,
        totalPages: 0
      });
    }
  };

  const handleDeleteCurrentLog = async () => {
    if (!currentFileId) return;
    try {
      const formData = new FormData();
      formData.append('action', 'clear_data');
      formData.append('session_id', sessionId);
      formData.append('file_id', currentFileId);

      await fetch('/api/upload/', {
        method: 'POST',
        body: formData,
      });
    } catch (error) {
      console.error('Error deleting current log on backend:', error);
    } finally {
      setHistory(prev => (Array.isArray(prev) ? prev.filter(item => item.fileId !== currentFileId) : []));
      setLogs([]);
      setSelectedHistoryItem(null);
      setCurrentFileId(null);
      setWasLogDeleted(true);
      setPagination({
        page: 1,
        pageSize: 50,
        totalCount: 0,
        totalPages: 0
      });
    }
  };

  const handleFilterChange = (filterType, value) => {
    const newFilters = {
      ...filters,
      [filterType]: value
    };
    setFilters(newFilters);
  };

  const handlePageChange = async (newPage, newPageSize) => {
    if (currentFileId) {
      const pageSizeToUse = newPageSize ?? pagination.pageSize;
      await loadLogs(currentFileId, newPage, pageSizeToUse, filters);
    }
  };

  const handleShowJson = async (logId) => {
    if (!currentFileId || !sessionId) return;
    
    try {
      const formData = new FormData();
      formData.append('action', 'get_json_bodies');
      formData.append('file_id', currentFileId);
      formData.append('session_id', sessionId);
      formData.append('log_id', logId);

      const response = await fetch('/api/upload/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const jsonWindow = window.open('', '_blank');
      jsonWindow.document.write(`
        <html>
          <head><title>JSON Bodies - Log ${logId}</title></head>
          <body style="background: #1a1a1a; color: white; padding: 20px; font-family: monospace;">
            <h2>JSON Bodies for Log ${logId}</h2>
            <pre>${JSON.stringify(data.json_bodies, null, 2)}</pre>
          </body>
        </html>
      `);
    } catch (error) {
      console.error('Error loading JSON bodies:', error);
      alert(`Error loading JSON: ${error.message}`);
    }
  };

  const toggleTheme = () => {
    setIsDarkTheme(!isDarkTheme);
  };


  return (
    <div className="app">
      <div className="sidebar">
        <div className="upload-section">
          <FileUploader 
            onFileUpload={handleFileUpload} 
            sessionId={sessionId}
          />
        </div>
        <div className="history-section">
          <LogHistory 
            history={history}
            selectedItem={selectedHistoryItem}
            onSelect={handleHistorySelect}
            onClear={handleHistoryClear}
          />
        </div>
      </div>
      <div className="main-content">
        <LogTerminal 
          logs={logs}
          filters={filters}
          onFilterChange={handleFilterChange}
          onShowJson={handleShowJson}
          isDarkTheme={isDarkTheme}
          onThemeToggle={toggleTheme}
          onDeleteCurrent={handleDeleteCurrentLog}
          historyCount={Array.isArray(history) ? history.length : 0}
          wasLogDeleted={wasLogDeleted}
          pagination={pagination}
          onPageChange={handlePageChange}
          isLoading={isLoading}
          currentFileId={currentFileId}
        />
      </div>
    </div>
  );
};

export default App;
