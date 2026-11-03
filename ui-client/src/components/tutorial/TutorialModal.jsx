import React, { useState, useEffect } from 'react';
import { BotAvatar } from 'bot-avatars';
import './tutorial.css';

export default function TutorialModal({
  isOpen,
  onClose,
  onSelectPrompt,
  currentUser,
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(true);

  // Sync state when opened
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const steps = [
    {
      badge: 'Curriculum Grounded',
      stepTag: 'Step 1 of 3 · Smart Textbook Tutor',
      icon: '📚',
      title: 'Ask anything from your NCERT curriculum',
      desc: 'Learnright is trained to help you master your specific grade textbooks. Every single explanation is verified against official curriculum text with exact page numbers and chapter sources.',
      previewType: 'prompts',
      prompts: [
        'Explain light reflection and refraction formulas',
        'What are the raw materials for photosynthesis?',
        'How does an electric motor work in Class 10 Physics?',
      ],
    },
    {
      badge: 'Classrooms & RBAC',
      stepTag: 'Step 2 of 3 · School Organization Hub',
      icon: '🏛️',
      title: 'Connect with your school, class & advisors',
      desc: 'Join your school organization using an invite code or manage classes, sections, and faculty. Principals oversee academic structure, faculty advisors mentor classes, and students collaborate safely.',
      previewType: 'institution',
      pills: [
        { label: '🏛️ Delhi Public School', type: 'violet' },
        { label: 'Class 10 · Section A', type: 'blue' },
        { label: '👨‍🏫 Faculty Advisor Assigned', type: 'green' },
      ],
    },
    {
      badge: 'Interactive Audio',
      stepTag: 'Step 3 of 3 · Natural Voice & Hints',
      icon: '🎙️',
      title: 'Listen, speak & solve problems step-by-step',
      desc: 'Click the speaker button to hear realistic spoken audio explanations. Tap the microphone in the prompt bar to ask questions hands-free, and ask for gentle hints when tackling tough homework.',
      previewType: 'voice',
      pills: [
        { label: '🔊 Audio Read-Aloud', type: 'violet' },
        { label: '🎤 Voice Dictation', type: 'blue' },
        { label: '💡 Socratic Problem Hints', type: 'green' },
      ],
    },
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleComplete = () => {
    if (dontShowAgain) {
      try {
        localStorage.setItem('learnright_tutorial_dismissed', 'true');
      } catch {}
    }
    onClose();
  };

  const handlePromptClick = (promptText) => {
    if (dontShowAgain) {
      try {
        localStorage.setItem('learnright_tutorial_dismissed', 'true');
      } catch {}
    }
    if (onSelectPrompt) {
      onSelectPrompt(promptText);
    }
    onClose();
  };

  const activeSlide = steps[currentStep];

  return (
    <div
      className="tutorial-backdrop"
      onClick={handleComplete}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Learnright Tutorial"
    >
      <div className="tutorial-card" onClick={(e) => e.stopPropagation()}>
        {/* Ambient Top Glow */}
        <div className="tutorial-ambient-glow" />

        {/* Close Button */}
        <button
          className="tutorial-close-btn"
          onClick={handleComplete}
          type="button"
          title="Close tutorial (Esc)"
        >
          ✕
        </button>

        {/* Hero Header with Animated Violet Clover Bot and Shimmering Text */}
        <header className="tutorial-header">
          <div
            className="tutorial-bot-wrap"
            title="Learnright Clover Bot · Click me!"
            onClick={() => {}}
          >
            <BotAvatar
              type="clover"
              size={76}
              color="#8b5cf6"
              shading="fabric"
              state="default"
              interactive={true}
            />
          </div>

          <div className="tutorial-badge">
            <span>✨</span>
            <span>Welcome to Learnright</span>
          </div>

          <h2 className="tutorial-title">
            {currentUser?.full_name
              ? `Welcome, ${currentUser.full_name.split(' ')[0]}!`
              : 'Welcome to Learnright'}
          </h2>

          <p className="tutorial-subtitle">
            Your intelligent NCERT curriculum companion, school classroom hub, and AI study tutor.
          </p>
        </header>

        {/* Carousel Slide Card */}
        <div className="tutorial-body">
          <div className="tutorial-slide-card" key={currentStep}>
            <div className="tutorial-slide-header">
              <div className="tutorial-step-icon">{activeSlide.icon}</div>
              <div className="tutorial-step-meta">
                <span className="tutorial-step-tag">{activeSlide.stepTag}</span>
                <h3 className="tutorial-step-title">{activeSlide.title}</h3>
              </div>
            </div>

            <p className="tutorial-step-desc">{activeSlide.desc}</p>

            {/* Slide Previews */}
            {activeSlide.previewType === 'prompts' && (
              <div className="tutorial-preview-box">
                <span className="tutorial-preview-label">Try asking:</span>
                <div className="tutorial-sample-chips">
                  {activeSlide.prompts.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="tutorial-sample-chip"
                      onClick={() => handlePromptClick(p)}
                      title="Click to ask this question immediately"
                    >
                      <span>💬</span>
                      <span>{p}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {(activeSlide.previewType === 'institution' || activeSlide.previewType === 'voice') && (
              <div className="tutorial-preview-box">
                <span className="tutorial-preview-label">Key Highlights:</span>
                <div className="tutorial-highlight-row" style={{ flexWrap: 'wrap' }}>
                  {activeSlide.pills.map((pill, idx) => (
                    <span
                      key={idx}
                      className={`tutorial-pill ${pill.type === 'violet' ? 'violet' : pill.type === 'green' ? 'green' : ''}`}
                    >
                      {pill.label}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Navigation & Stepper */}
        <footer className="tutorial-footer">
          {/* Claude-style step dots */}
          <div className="tutorial-dots" role="tablist" aria-label="Tutorial Steps">
            {steps.map((_, idx) => (
              <button
                key={idx}
                type="button"
                className={`tutorial-dot ${idx === currentStep ? 'active' : ''}`}
                onClick={() => setCurrentStep(idx)}
                aria-label={`Go to step ${idx + 1}`}
                role="tab"
                aria-selected={idx === currentStep}
              />
            ))}
          </div>

          <div className="tutorial-actions">
            {currentStep > 0 && (
              <button
                type="button"
                className="tutorial-btn-sec"
                onClick={handleBack}
              >
                Back
              </button>
            )}

            <button
              type="button"
              className="tutorial-btn-primary"
              onClick={handleNext}
            >
              <span>{currentStep === steps.length - 1 ? "Let's Learn ✨" : 'Next Step →'}</span>
            </button>
          </div>
        </footer>

        {/* Don't show again toggle */}
        <div className="tutorial-bottom-bar">
          <label className="tutorial-dont-show">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don't show this automatically on login</span>
          </label>
        </div>
      </div>
    </div>
  );
}

