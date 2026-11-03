import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';

export function AppleGlassDropdown({
  id,
  label,
  value,
  options = [],
  placeholder = '',
  onChange,
  disabled = false,
  className = '',
  menuWidth,
  openUpward = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState({
    top: 'auto',
    bottom: 'auto',
    left: 0,
    placement: 'up',
    maxHeight: 280,
    minWidth: 140,
  });

  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const selectedOpt = options.find((opt) => String(opt.value) === String(value));
  const displayText = selectedOpt
    ? selectedOpt.label
    : (placeholder || options[0]?.label || 'Select');

  // Compute exact viewport position when open
  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;

    // Prefer upward if requested OR if space below is limited
    const isUpward = openUpward || (spaceBelow < 240 && spaceAbove > spaceBelow);

    // Compute width
    let targetWidth = 140;
    if (menuWidth) {
      targetWidth = parseInt(menuWidth, 10) || 140;
    } else if (rect.width > targetWidth) {
      targetWidth = Math.round(rect.width);
    }

    // Keep within horizontal screen bounds
    let leftPos = rect.left;
    if (leftPos + targetWidth > window.innerWidth - 12) {
      leftPos = Math.max(12, window.innerWidth - targetWidth - 12);
    }

    if (isUpward) {
      setCoords({
        placement: 'up',
        top: 'auto',
        bottom: `${Math.round(window.innerHeight - rect.top + 6)}px`,
        left: Math.round(leftPos),
        maxHeight: Math.min(320, Math.max(120, spaceAbove - 20)),
        minWidth: Math.max(targetWidth, Math.round(rect.width)),
      });
    } else {
      setCoords({
        placement: 'down',
        top: `${Math.round(rect.bottom + 6)}px`,
        bottom: 'auto',
        left: Math.round(leftPos),
        maxHeight: Math.min(320, Math.max(120, spaceBelow - 20)),
        minWidth: Math.max(targetWidth, Math.round(rect.width)),
      });
    }
  };

  // Re-calculate position on open, scroll, resize
  useLayoutEffect(() => {
    if (!isOpen) return;
    updatePosition();

    const handleScrollOrResize = (e) => {
      // Don't close if scrolling inside the dropdown popover itself
      if (menuRef.current && menuRef.current.contains(e.target)) {
        return;
      }
      updatePosition();
    };

    window.addEventListener('resize', handleScrollOrResize);
    window.addEventListener('scroll', handleScrollOrResize, true);

    return () => {
      window.removeEventListener('resize', handleScrollOrResize);
      window.removeEventListener('scroll', handleScrollOrResize, true);
    };
  }, [isOpen, options.length]);

  // Close on click outside
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

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  return (
    <div className={`apple-glass-dropdown-wrap ${className}`}>
      {label && <span className="setting-label">{label}</span>}
      <button
        id={id}
        ref={triggerRef}
        type="button"
        className={`apple-glass-dropdown-trigger ${isOpen ? 'active-open' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="apple-dropdown-text">{displayText}</span>
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

      {/* Render via Portal to document.body so overflow: hidden can NEVER clip it */}
      {isOpen &&
        createPortal(
          <div
            ref={menuRef}
            className={`apple-glass-dropdown-menu ${coords.placement === 'up' ? 'open-upward' : 'open-downward'}`}
            style={{
              position: 'fixed',
              top: coords.top,
              bottom: coords.bottom,
              left: `${coords.left}px`,
              minWidth: `${coords.minWidth}px`,
              maxHeight: `${coords.maxHeight}px`,
              zIndex: 999999,
            }}
            role="listbox"
          >
            <div
              className="apple-dropdown-scroll-box"
              style={{ maxHeight: `${coords.maxHeight - 12}px` }}
            >
              {options.map((opt) => {
                const isSelected = String(opt.value) === String(value);
                return (
                  <div
                    key={opt.value || opt.label}
                    className={`apple-glass-dropdown-item ${isSelected ? 'selected' : ''}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={(e) => {
                      e.stopPropagation();
                      onChange(opt.value);
                      setIsOpen(false);
                    }}
                  >
                    <span className="apple-item-label">{opt.label}</span>
                    {isSelected && (
                      <svg
                        className="apple-item-check"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>
                );
              })}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
