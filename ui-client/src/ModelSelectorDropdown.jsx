import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';

export function ModelSelectorDropdown({
  activeModel,
  localModels = [],
  cloudModels = [],
  onSelectModel,
  disabled = false,
  className = '',
  openUpward = true,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState({
    top: 'auto',
    bottom: 'auto',
    left: 0,
    placement: 'up',
    maxHeight: 380,
    minWidth: 320,
  });

  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  // Compute exact position
  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;

    const isUpward = openUpward || (spaceBelow < 300 && spaceAbove > spaceBelow);
    const targetWidth = 340;

    let leftPos = rect.left;
    if (leftPos + targetWidth > window.innerWidth - 12) {
      leftPos = Math.max(12, window.innerWidth - targetWidth - 12);
    }

    if (isUpward) {
      setCoords({
        placement: 'up',
        top: 'auto',
        bottom: `${Math.round(window.innerHeight - rect.top + 8)}px`,
        left: Math.round(leftPos),
        maxHeight: Math.min(420, Math.max(160, spaceAbove - 24)),
        minWidth: targetWidth,
      });
    } else {
      setCoords({
        placement: 'down',
        top: `${Math.round(rect.bottom + 8)}px`,
        bottom: 'auto',
        left: Math.round(leftPos),
        maxHeight: Math.min(420, Math.max(160, spaceBelow - 24)),
        minWidth: targetWidth,
      });
    }
  };

  useLayoutEffect(() => {
    if (!isOpen) return;
    updatePosition();

    const handleScrollOrResize = (e) => {
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      updatePosition();
    };

    window.addEventListener('resize', handleScrollOrResize);
    window.addEventListener('scroll', handleScrollOrResize, true);

    return () => {
      window.removeEventListener('resize', handleScrollOrResize);
      window.removeEventListener('scroll', handleScrollOrResize, true);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event) {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(event.target) &&
        menuRef.current &&
        !menuRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e) {
      if (e.key === 'Escape') setIsOpen(false);
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Determine active display details
  const isCloud = activeModel?.is_cloud ?? false;
  const activeProvider = activeModel?.provider || 'ollama';
  const activeModelName = activeModel?.model || 'qwen3.5:4b';

  // Short pill display string
  const pillDisplay = isCloud
    ? `${activeProvider.toUpperCase()}: ${activeModelName.split(':')[0]}`
    : `OLLAMA: ${activeModelName}`;

  return (
    <div className={`apple-glass-dropdown-wrap model-selector-wrap ${className}`}>
      <button
        id="model-select-btn"
        ref={triggerRef}
        type="button"
        className={`apple-glass-dropdown-trigger model-selector-trigger ${isOpen ? 'active-open' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title={`Active LLM: ${activeModelName} (${isCloud ? 'Cloud' : 'Local'})`}
      >
        <span className={`model-indicator-dot ${isCloud ? 'cloud-dot' : 'local-dot'}`} />
        <span className="apple-dropdown-text model-trigger-text">{pillDisplay}</span>
        <svg
          className={`apple-dropdown-arrow ${isOpen ? 'rotated' : ''}`}
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen &&
        createPortal(
          <div
            ref={menuRef}
            className={`apple-glass-dropdown-menu model-selector-popover ${
              coords.placement === 'up' ? 'open-upward' : 'open-downward'
            }`}
            style={{
              position: 'fixed',
              top: coords.top,
              bottom: coords.bottom,
              left: `${coords.left}px`,
              width: `${coords.minWidth}px`,
              maxHeight: `${coords.maxHeight}px`,
              zIndex: 999999,
            }}
            role="listbox"
          >
            {/* Header with active info */}
            <div className="model-selector-header">
              <div className="model-selector-title-row">
                <span className="model-selector-title">LLM Model Selector</span>
                <span className={`model-header-pill ${isCloud ? 'cloud' : 'local'}`}>
                  {isCloud ? '☁️ Cloud Active' : '💻 Local Active'}
                </span>
              </div>
              <div className="model-selector-current-info">
                Active: <strong>{activeModelName}</strong> via <em>{activeProvider}</em>
              </div>
            </div>

            <div
              className="apple-dropdown-scroll-box model-selector-scroll"
              style={{ maxHeight: `${coords.maxHeight - 75}px` }}
            >
              {/* Field 1: Local Models */}
              <div className="model-group-section">
                <div className="model-group-heading">
                  <span className="group-heading-icon">💻</span>
                  <span className="group-heading-text">Local Models</span>
                  <span className="group-heading-desc">Offline · On-Device</span>
                </div>
                <div className="model-group-list">
                  {localModels.map((m) => {
                    const isSelected = !isCloud && (m.model === activeModelName || m.provider === activeProvider);
                    return (
                      <div
                        key={m.id || m.model}
                        className={`model-option-card ${isSelected ? 'selected' : ''}`}
                        role="option"
                        aria-selected={isSelected}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectModel(m.provider, m.model);
                          setIsOpen(false);
                        }}
                      >
                        <div className="model-card-left">
                          <div className="model-card-title-row">
                            <span className="model-card-name">{m.label || m.model}</span>
                            <span className="model-card-tag local-tag">Local</span>
                          </div>
                          <span className="model-card-exact-id">{m.model}</span>
                          <span className="model-card-desc">{m.details || 'Ollama private inference'}</span>
                        </div>
                        {isSelected && (
                          <div className="model-active-badge">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span>Active</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Field 2: Cloud Models */}
              <div className="model-group-section">
                <div className="model-group-heading">
                  <span className="group-heading-icon">☁️</span>
                  <span className="group-heading-text">Cloud Models</span>
                  <span className="group-heading-desc">API Key · High Performance</span>
                </div>
                <div className="model-group-list">
                  {cloudModels.map((m) => {
                    const isSelected = isCloud && (m.provider === activeProvider || m.model === activeModelName);
                    return (
                      <div
                        key={m.id || m.model}
                        className={`model-option-card ${isSelected ? 'selected' : ''}`}
                        role="option"
                        aria-selected={isSelected}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectModel(m.provider, m.model);
                          setIsOpen(false);
                        }}
                      >
                        <div className="model-card-left">
                          <div className="model-card-title-row">
                            <span className="model-card-name">{m.label || m.model}</span>
                            <span className="model-card-tag cloud-tag">{m.badge || 'Cloud'}</span>
                          </div>
                          <span className="model-card-exact-id">{m.model}</span>
                          <span className="model-card-desc">{m.details}</span>
                        </div>
                        {isSelected ? (
                          <div className="model-active-badge">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span>Active</span>
                          </div>
                        ) : !m.has_key ? (
                          <span className="model-key-hint">Set key in .env</span>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

