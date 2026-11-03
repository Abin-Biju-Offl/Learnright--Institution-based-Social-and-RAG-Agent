import React, { useState, useEffect, useRef } from 'react';
import { ShieldIcon } from './ParentalNavButton';
import OverviewTab from './tabs/OverviewTab';
import ChatHistoryTab from './tabs/ChatHistoryTab';
import FlaggedAlertsTab from './tabs/FlaggedAlertsTab';
import ContentFilterTab from './tabs/ContentFilterTab';
import SecurityPinTab from './tabs/SecurityPinTab';
import TextbookUploadTab from './tabs/TextbookUploadTab';
import './parental.css';

/**
 * ParentalPortalModal
 * Main frosted-glass dialog modal housing the 5 parental governance tabs:
 * Overview, Chat History, Flagged Alerts, Content Filtering, and Security/PIN.
 */
export default function ParentalPortalModal({
  isOpen,
  onClose,
  token,
  onLogout,
  expiresInSeconds = 900,
  initialTab = 'overview',
  onBookUploaded,
}) {
  const VALID_TABS = ['overview', 'history', 'flagged', 'filtering', 'upload', 'security'];
  const getSafeTab = (tab) => (typeof tab === 'string' && VALID_TABS.includes(tab) ? tab : 'overview');

  const [activeTab, setActiveTab] = useState(() => getSafeTab(initialTab));
  const [showIntro, setShowIntro] = useState(true);
  const [unreviewedCount, setUnreviewedCount] = useState(0);
  const [remainingTime, setRemainingTime] = useState(expiresInSeconds);

  const countdownRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      const safeTab = getSafeTab(initialTab);
      setActiveTab(safeTab);
      setShowIntro(true);

      const introTimer = setTimeout(() => {
        setShowIntro(false);
        setActiveTab(safeTab);
      }, 1400);

      return () => clearTimeout(introTimer);
    } else {
      setShowIntro(true);
    }
  }, [isOpen, initialTab]);

  const handleSelectTab = (tab) => {
    setShowIntro(false);
    setActiveTab(getSafeTab(tab));
  };

  // Initialize countdown on open
  useEffect(() => {
    if (isOpen) {
      setRemainingTime(expiresInSeconds);
      if (countdownRef.current) clearInterval(countdownRef.current);

      countdownRef.current = setInterval(() => {
        setRemainingTime((prev) => {
          if (prev <= 1) {
            clearInterval(countdownRef.current);
            if (onLogout) onLogout();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isOpen, expiresInSeconds, onLogout]);

  // Format seconds to mm:ss
  const formatCountdown = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div className="parental-modal-overlay" onClick={onClose}>
      <div className="parental-portal-card" onClick={(e) => e.stopPropagation()}>
        {/* ── Modal Header ── */}
        <div className="parental-portal-header">
          <div className="parental-portal-header-left">
            <h3 className="parental-portal-title">
              <ShieldIcon size={22} color="#8ab4f8" />
              <span>Parental Control Center</span>
            </h3>
            <span className="parental-portal-status-pill">
              ● Active Under-18 Protection
            </span>
          </div>

          <div className="parental-portal-header-right">
            <div className="session-countdown-pill" title="Time remaining before session automatically locks">
              <span>⏱️ Auto-lock:</span>
              <span style={{ fontWeight: 600, color: '#e3e3e3' }}>
                {formatCountdown(remainingTime)}
              </span>
            </div>

            <button
              type="button"
              className="lock-signout-btn"
              onClick={onLogout}
              title="Lock parental portal and sign out"
            >
              <span>🔒</span> Lock & Exit
            </button>

            <button
              type="button"
              className="portal-close-btn"
              onClick={onClose}
              aria-label="Close portal"
            >
              ✕
            </button>
          </div>
        </div>

        {/* ── Tab Navigation Bar ── */}
        <nav className="parental-tabs">
          <button
            type="button"
            className={`parental-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => handleSelectTab('overview')}
          >
            <span>📊</span> Overview
          </button>

          <button
            type="button"
            className={`parental-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => handleSelectTab('history')}
          >
            <span>💬</span> Chat History
          </button>

          <button
            type="button"
            className={`parental-tab ${activeTab === 'flagged' ? 'active' : ''}`}
            onClick={() => handleSelectTab('flagged')}
          >
            <span>🚨</span> Flagged Alerts
            {unreviewedCount > 0 && (
              <span className="tab-badge">{unreviewedCount}</span>
            )}
          </button>

          <button
            type="button"
            className={`parental-tab ${activeTab === 'filtering' ? 'active' : ''}`}
            onClick={() => handleSelectTab('filtering')}
          >
            <span>🛡️</span> Content Filtering
          </button>

          <button
            type="button"
            className={`parental-tab ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => handleSelectTab('upload')}
          >
            <span>📚</span> Upload Textbook
          </button>

          <button
            type="button"
            className={`parental-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => handleSelectTab('security')}
          >
            <span>🔑</span> Security & PIN
          </button>
        </nav>

        {/* ── Active Tab Content Panel ── */}
        <div className="parental-tab-body">
          {showIntro ? (
            <div
              className="parental-intro-screen"
              onClick={() => {
                setShowIntro(false);
                setActiveTab(getSafeTab(initialTab));
              }}
              title="Click to jump to Overview"
            >
              <div className="parental-intro-glow" />
              <div className="parental-intro-content">
                <div className="parental-intro-icon-wrap">
                  <ShieldIcon size={46} color="#8ab4f8" />
                  <div className="parental-intro-ring" />
                </div>
                <h2 className="parental-intro-title">Parental Control</h2>
                <p className="parental-intro-subtitle">
                  Active Under-18 Protection &amp; Curriculum Governance
                </p>
                <div className="parental-intro-loader">
                  <div className="parental-intro-loader-bar" />
                </div>
              </div>
            </div>
          ) : (
            <div className="parental-tab-content-enter">
              {activeTab === 'overview' && (
                <OverviewTab
                  token={token}
                  onSwitchTab={(tab) => handleSelectTab(tab)}
                />
              )}

              {activeTab === 'upload' && (
                <TextbookUploadTab
                  token={token}
                  onBookUploaded={onBookUploaded}
                />
              )}

              {activeTab === 'history' && (
                <ChatHistoryTab token={token} />
              )}

              {activeTab === 'flagged' && (
                <FlaggedAlertsTab
                  token={token}
                  onAlertCountChange={(count) => setUnreviewedCount(count)}
                />
              )}

              {activeTab === 'filtering' && (
                <ContentFilterTab token={token} />
              )}

              {activeTab === 'security' && (
                <SecurityPinTab
                  token={token}
                  onLogout={onLogout}
                  sessionExpiresIn={remainingTime}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
