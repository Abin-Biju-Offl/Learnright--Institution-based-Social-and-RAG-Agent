import React from 'react';
import './parental.css';

/**
 * Shield SVG icon
 */
export function ShieldIcon({ size = 18, color = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

/**
 * ParentalNavButton
 * Displays a navigation button with shield icon and alert badge count.
 * Suitable for both the Gemini sidebar and mobile header.
 */
export default function ParentalNavButton({
  onClick,
  unreviewedCount = 0,
  isCollapsed = false,
  className = '',
}) {
  return (
    <button
      type="button"
      className={`parental-nav-btn ${className}`}
      onClick={onClick}
      title="Parental Controls & Student Safety Portal"
      aria-label="Parental Controls"
    >
      <div className="parental-nav-btn-left">
        <span className="parental-shield-icon">
          <ShieldIcon size={18} color="#8ab4f8" />
        </span>
        {!isCollapsed && <span>Parental Controls</span>}
      </div>

      {unreviewedCount > 0 && (
        <span className="parental-badge-pill" title={`${unreviewedCount} unreviewed safety alerts`}>
          {unreviewedCount}
        </span>
      )}
    </button>
  );
}
