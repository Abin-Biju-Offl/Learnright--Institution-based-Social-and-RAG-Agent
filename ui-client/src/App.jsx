import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { BotAvatar } from 'bot-avatars';
import { ThinkingOrb } from 'thinking-orbs';
import { MetalFx, MetalBadge, MetalText } from 'metal-fx';
import { BorderBeam } from 'border-beam';
import {
  GeminiStarIcon,
  SidebarToggleIcon,
  SearchIcon,
  ComposeIcon,
  LibraryIcon,
  ScheduledIcon,
  CustomiseIcon,
  PlusIcon,
  FilterIcon,
  NotebookIcon,
  LearnrightLogo,
  RobotAskIcon,
  ShieldIcon,
  BookOpenIcon,
  ChevronDownIcon,
  SettingsGearIcon,
} from './GeminiIcons';
import { AppleGlassDropdown } from './AppleGlassDropdown';
import { ModelSelectorDropdown } from './ModelSelectorDropdown';
import ParentalAuthModal from './components/parental/ParentalAuthModal';
import ParentalPortalModal from './components/parental/ParentalPortalModal';
import InstitutionAdminModal from './components/institution/InstitutionAdminModal';
import JoinInstitutionModal from './components/institution/JoinInstitutionModal';
import TutorialModal from './components/tutorial/TutorialModal';
import { THEMES } from './themes';
import './App.css';

const STORAGE_KEY = 'ncert-tutor-sessions-v3';

const BOOK_CODE_MAP = {
  '10|Science': { code: 'jesc1', dir: 'class-10/science' },
  '10|English': { code: 'jeff1', dir: 'class-10/english' },
  '10|Social Science': { code: 'jess1', dir: 'class-10/social-science' },
  '5|English': { code: 'eeen1', dir: 'class-5/english' },
  '5|Science': { code: 'eesc1', dir: 'class-5/science' },
  '5|Social Science': { code: 'eess1', dir: 'class-5/social-science' },
};

function getChapterPdfPath(grade, subject, chapterNum = 1) {
  const info = BOOK_CODE_MAP[`${grade}|${subject}`];
  if (!info) return null;
  const pad = String(chapterNum).padStart(2, '0');
  return `${info.dir}/${info.code}${pad}.pdf`;
}

const TEXTBOOK_CATALOG = [
  {
    grade: 10,
    subject: 'Science',
    title: 'NCERT Science',
    subtitle: 'Chemical Reactions, Life Processes, Light, Electricity & Environment',
    chapters: [
      { number: 1, title: 'Chemical Reactions and Equations' },
      { number: 2, title: 'Acids, Bases and Salts' },
      { number: 3, title: 'Metals and Non-metals' },
      { number: 4, title: 'Carbon and its Compounds' },
      { number: 5, title: 'Life Processes' },
      { number: 6, title: 'Control and Coordination' },
      { number: 7, title: 'How do Organisms Reproduce?' },
      { number: 8, title: 'Heredity' },
      { number: 9, title: 'Light – Reflection and Refraction' },
      { number: 10, title: 'The Human Eye and the Colourful World' },
      { number: 11, title: 'Electricity' },
      { number: 12, title: 'Magnetic Effects of Electric Current' },
      { number: 13, title: 'Our Environment' },
    ],
  },
  {
    grade: 10,
    subject: 'English',
    title: 'First Flight',
    subtitle: 'Letter to God, Nelson Mandela, Anne Frank, Stories & Poetry',
    chapters: [
      { number: 1, title: 'A Letter to God' },
      { number: 2, title: 'Nelson Mandela: Long Walk to Freedom' },
      { number: 3, title: 'Two Stories about Flying' },
      { number: 4, title: 'From the Diary of Anne Frank' },
      { number: 5, title: 'Glimpses of India' },
      { number: 6, title: 'Mijbil the Otter' },
      { number: 7, title: 'Madam Rides the Bus' },
      { number: 8, title: 'The Sermon at Benares' },
      { number: 9, title: 'The Proposal' },
    ],
  },
  {
    grade: 10,
    subject: 'Social Science',
    title: 'Contemporary India II (Geography)',
    subtitle: 'Resources, Forest & Wildlife, Water, Agriculture, Minerals & Industries',
    chapters: [
      { number: 1, title: 'Resources and Development' },
      { number: 2, title: 'Forest and Wildlife Resources' },
      { number: 3, title: 'Water Resources' },
      { number: 4, title: 'Agriculture' },
      { number: 5, title: 'Minerals and Energy Resources' },
      { number: 6, title: 'Manufacturing Industries' },
      { number: 7, title: 'Lifelines of National Economy' },
    ],
  },
  {
    grade: 5,
    subject: 'English',
    title: 'Sunshine Reader',
    subtitle: 'Foundational English reading stories, poems and comprehension',
    chapters: [
      { number: 1, title: 'The Thirsty Crow' },
      { number: 2, title: "Meena's Kite" },
      { number: 3, title: 'A Letter to Grandma' },
      { number: 4, title: 'Tara the Otter' },
      { number: 5, title: 'Raghu and the Rain' },
    ],
  },
  {
    grade: 5,
    subject: 'Science',
    title: 'Science Around Us (EVS)',
    subtitle: 'Plants, Light & Shadows, Electricity, Senses and Environment',
    chapters: [
      { number: 1, title: 'How Plants Make Their Food' },
      { number: 2, title: 'Light and Shadows' },
      { number: 3, title: 'Electricity Around Us' },
      { number: 4, title: 'Our Senses and Our Eyes' },
      { number: 5, title: 'Taking Care of Our Environment' },
    ],
  },
  {
    grade: 5,
    subject: 'Social Science',
    title: 'Our Land and People',
    subtitle: 'Soil, Wildlife, Water Resources, Farming, Travel & Communication',
    chapters: [
      { number: 1, title: 'Soil: The Ground Beneath Our Feet' },
      { number: 2, title: 'Forests and Wild Animals' },
      { number: 3, title: 'Water: Our Precious Friend' },
      { number: 4, title: 'Farmers and Farming' },
      { number: 5, title: 'Travelling and Sending Messages' },
    ],
  },
];

const EXAMPLES = {
  // Class 10 (Real NCERT books)
  '10|English': [
    'Why did Lencho write a letter to God?',
    'What did Mandela learn about courage?'
  ],
  '10|Science': [
    'What is a balanced chemical equation?',
    'Why does the sky appear blue?'
  ],
  '10|Social Science': [
    'What are the different types of soil in India?',
    'What is Project Tiger?'
  ],
  // Class 5 (Demo books)
  '5|English': [
    'What happened to the thirsty crow?',
    'What did Meena do with her kite?'
  ],
  '5|Science': [
    'How do plants make their food?',
    'What is a shadow?'
  ],
  '5|Social Science': [
    'Why is water important for us?',
    'What kind of animals live in forests?'
  ],
};

function formatAnswer(text) {
  if (!text) return '';
  // Basic markdown formatting: bold, code, bullets, paragraphs
  const lines = text.split('\n');
  const rendered = [];
  let inList = false;

  lines.forEach((line, idx) => {
    let trimmed = line.trim();
    if (!trimmed) {
      if (inList) {
        rendered.push('</ul>');
        inList = false;
      }
      return;
    }

    // Bold replacement
    let formatted = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Inline code replacement
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        rendered.push('<ul>');
        inList = true;
      }
      rendered.push(`<li>${formatted.slice(2)}</li>`);
    } else {
      if (inList) {
        rendered.push('</ul>');
        inList = false;
      }
      rendered.push(`<p>${formatted}</p>`);
    }
  });

  if (inList) rendered.push('</ul>');
  return rendered.join('');
}

export default function App() {
  // Sessions & Messages
  const [sessions, setSessions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  });

  // Always start in a fresh new chat session by default on website open/refresh
  const [activeSessionId, setActiveSessionId] = useState(null);

  // Server data
  const [subjects, setSubjects] = useState([]);
  const [selectedGrade, setSelectedGrade] = useState(() => {
    try {
      const raw = localStorage.getItem('student_user');
      if (raw) return JSON.parse(raw)?.grade || 10;
    } catch { }
    return 10;
  });
  const [selectedSubject, setSelectedSubject] = useState('');
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [language, setLanguage] = useState('English');
  const [status, setStatus] = useState({ text: 'Connecting…', type: 'connecting' });

  // Model Selector state (Local & Cloud models)
  const [activeModelInfo, setActiveModelInfo] = useState({
    provider: 'ollama',
    model: 'qwen3.5:4b',
    is_cloud: false,
    tag: 'Local',
    display_name: 'Ollama: qwen3.5:4b',
  });
  const [localModels, setLocalModels] = useState([]);
  const [cloudModels, setCloudModels] = useState([]);

  // Input & In-flight state
  const [question, setQuestion] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [thinkingState, setThinkingState] = useState('searching');
  const [thinkingText, setThinkingText] = useState('Searching your textbook…');
  const [currentStreamAnswer, setCurrentStreamAnswer] = useState('');
  const [currentStreamSources, setCurrentStreamSources] = useState([]);
  const [feedbackSent, setFeedbackSent] = useState(false);

  // PDF Preview Drawer
  const [pdfPreview, setPdfPreview] = useState({
    isOpen: false,
    file: '',
    page: 1,
    title: 'PDF preview',
  });

  // UI responsive drawer & Gemini Sidebar Collapse
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('gemini_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  // Gemini Sidebar Features State
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [activeModal, setActiveModal] = useState(null); // 'library' | 'activity' | 'customise' | 'videos' | 'notebooks'
  const [metricsData, setMetricsData] = useState(null);
  const [tutorPersona, setTutorPersona] = useState('friendly');
  const [notebooks, setNotebooks] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('gemini_notebooks') || '[]');
      return saved.length > 0
        ? saved
        : [
          { id: '1', title: 'Chapter 1 Key Definitions', createdAt: Date.now() - 86400000 },
          { id: '2', title: 'Science Exam Formulas', createdAt: Date.now() - 43200000 },
        ];
    } catch {
      return [];
    }
  });

  // Library Modal State
  const [libraryGradeFilter, setLibraryGradeFilter] = useState('all');
  const [expandedBookKey, setExpandedBookKey] = useState('10|Science');
  const [librarySearch, setLibrarySearch] = useState('');

  // Theme & Appearance State (10 Predefined Themes)
  const [currentThemeId, setCurrentThemeId] = useState(() => {
    try {
      return localStorage.getItem('ncert_theme') || 'gemini-dark';
    } catch {
      return 'gemini-dark';
    }
  });
  const [themeModeFilter, setThemeModeFilter] = useState('all');
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);

  // Apply Theme to documentElement
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', currentThemeId);
    const themeObj = THEMES.find((t) => t.id === currentThemeId) || THEMES[0];
    if (themeObj.mode === 'light') {
      document.documentElement.classList.add('light-mode');
      document.documentElement.classList.remove('dark-mode');
    } else {
      document.documentElement.classList.add('dark-mode');
      document.documentElement.classList.remove('light-mode');
    }
    try {
      localStorage.setItem('ncert_theme', currentThemeId);
    } catch { }
  }, [currentThemeId]);

  const currentThemeObj = THEMES.find((t) => t.id === currentThemeId) || THEMES[0];

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Parental Controls State
  const [parentAuthOpen, setParentAuthOpen] = useState(false);
  const [parentPortalOpen, setParentPortalOpen] = useState(false);
  const [parentSessionToken, setParentSessionToken] = useState(() => {
    try {
      return sessionStorage.getItem('ncert_parent_token') || null;
    } catch {
      return null;
    }
  });
  const [parentPortalTab, setParentPortalTab] = useState('overview');
  const [unreviewedAlertCount, setUnreviewedAlertCount] = useState(0);

  const isValidJwt = (t) => typeof t === 'string' && t.trim().split('.').length === 3;

  const getStoredToken = () => {
    try {
      const candidates = [
        localStorage.getItem('ncert_access_token'),
        localStorage.getItem('student_token'),
        sessionStorage.getItem('ncert_access_token'),
        sessionStorage.getItem('student_token'),
      ];
      for (const c of candidates) {
        if (isValidJwt(c)) return c.trim();
      }
      // Purge non-JWT or corrupted tokens that crash PyJWT
      ['ncert_access_token', 'student_token'].forEach((k) => {
        localStorage.removeItem(k);
        sessionStorage.removeItem(k);
      });
      return null;
    } catch {
      return null;
    }
  };

  // Student / User Profile State
  const [studentUser, setStudentUser] = useState(() => {
    try {
      const raw = localStorage.getItem('student_user');
      if (raw) return JSON.parse(raw);
    } catch { }
    return { username: 'abin_biju', full_name: 'Abin Biju', grade: 10, role: 'student' };
  });
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [authToken, setAuthToken] = useState(() => getStoredToken());
  const [instAdminModalOpen, setInstAdminModalOpen] = useState(false);
  const [joinInstModalOpen, setJoinInstModalOpen] = useState(false);
  const [urlInviteToken, setUrlInviteToken] = useState('');
  const [tutorialModalOpen, setTutorialModalOpen] = useState(() => {
    try {
      const justLoggedIn = sessionStorage.getItem('just_logged_in');
      if (justLoggedIn === 'true') {
        sessionStorage.removeItem('just_logged_in');
        return true;
      }
      return localStorage.getItem('learnright_tutorial_dismissed') !== 'true';
    } catch {
      return true;
    }
  });

  // Auto-detect invite link in URL (?invite=...)
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      let invite = params.get('invite');
      if (!invite && window.location.hash.includes('invite=')) {
        invite = window.location.hash.split('invite=')[1]?.split('&')[0];
      }
      if (invite) {
        setUrlInviteToken(invite);
        setJoinInstModalOpen(true);
      }
    } catch {}
  }, []);

  const refreshUserProfile = useCallback(async () => {
    const token = isValidJwt(authToken) ? authToken : getStoredToken();
    if (!token) return;
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const u = await res.json();
        setStudentUser(u);
        try { localStorage.setItem('student_user', JSON.stringify(u)); } catch {}
      } else if (res.status === 401) {
        setAuthToken(null);
        try {
          localStorage.removeItem('ncert_access_token');
          localStorage.removeItem('student_token');
          sessionStorage.removeItem('ncert_access_token');
          sessionStorage.removeItem('student_token');
        } catch {}
      }
    } catch {}
  }, [authToken]);

  useEffect(() => {
    refreshUserProfile();
  }, [refreshUserProfile]);

  const handleJoinedInstitutionSuccess = (tokens, user) => {
    if (tokens?.access_token && isValidJwt(tokens.access_token)) {
      setAuthToken(tokens.access_token);
      try {
        localStorage.setItem('ncert_access_token', tokens.access_token);
        localStorage.setItem('student_token', tokens.access_token);
        if (tokens.refresh_token) {
          localStorage.setItem('ncert_refresh_token', tokens.refresh_token);
          localStorage.setItem('student_refresh_token', tokens.refresh_token);
        }
      } catch {}
    }
    if (user) {
      setStudentUser(user);
      try { localStorage.setItem('student_user', JSON.stringify(user)); } catch {}
    }
    reloadSubjects();
  };

  const handleSwitchDemoRole = async (role, grade = 10) => {
    setUserMenuOpen(false);
    try {
      const res = await fetch('/api/auth/demo-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, grade }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.access_token && isValidJwt(data.access_token)) {
          setAuthToken(data.access_token);
          try {
            localStorage.setItem('ncert_access_token', data.access_token);
            localStorage.setItem('student_token', data.access_token);
            if (data.refresh_token) {
              localStorage.setItem('ncert_refresh_token', data.refresh_token);
              localStorage.setItem('student_refresh_token', data.refresh_token);
            }
          } catch {}
        }
        if (data.user) {
          setStudentUser(data.user);
          try { localStorage.setItem('student_user', JSON.stringify(data.user)); } catch {}
        }
      } else {
        const updated = {
          ...studentUser,
          role,
          grade: role === 'student' ? grade : null,
          subject_tags: role === 'lecturer' ? ['Science', 'Physics'] : [],
        };
        setStudentUser(updated);
        try { localStorage.setItem('student_user', JSON.stringify(updated)); } catch {}
      }
    } catch {
      const updated = {
        ...studentUser,
        role,
        grade: role === 'student' ? grade : null,
        subject_tags: role === 'lecturer' ? ['Science', 'Physics'] : [],
      };
      setStudentUser(updated);
      try { localStorage.setItem('student_user', JSON.stringify(updated)); } catch {}
    }
    reloadSubjects();
  };

  const handleOpenParental = (tab = 'overview') => {
    const validTabs = ['overview', 'history', 'flagged', 'filtering', 'upload', 'security'];
    const safeTab = typeof tab === 'string' && validTabs.includes(tab) ? tab : 'overview';
    setParentPortalTab(safeTab);
    if (parentSessionToken) {
      setParentPortalOpen(true);
    } else {
      setParentAuthOpen(true);
    }
  };

  const reloadSubjects = async () => {
    try {
      const token = authToken || getStoredToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const sRes = await fetch('/api/subjects', { headers });
      if (sRes.ok) {
        const data = await sRes.json();
        setSubjects(data);
      }
    } catch (e) {
      console.error('Failed to reload subjects', e);
    }
  };

  const handleParentAuthSuccess = (token) => {
    setParentSessionToken(token);
    try {
      sessionStorage.setItem('ncert_parent_token', token);
    } catch { }
    setParentAuthOpen(false);
    setParentPortalOpen(true);
  };

  const handleParentLogout = async () => {
    if (parentSessionToken) {
      try {
        await fetch('/api/parent/auth/logout', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${parentSessionToken}`,
          },
        });
      } catch (e) {
        console.warn('Logout network error', e);
      }
    }
    setParentSessionToken(null);
    try {
      sessionStorage.removeItem('ncert_parent_token');
    } catch { }
    setParentPortalOpen(false);
  };

  // Check unreviewed alert count when token is active
  useEffect(() => {
    if (!parentSessionToken) return;
    async function fetchAlertCount() {
      try {
        const res = await fetch('/api/parent/overview', {
          headers: {
            Authorization: `Bearer ${parentSessionToken}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setUnreviewedAlertCount(data.unreviewed_alerts || 0);
        } else if (res.status === 401) {
          setParentSessionToken(null);
          try {
            sessionStorage.removeItem('ncert_parent_token');
          } catch { }
        }
      } catch (e) {
        console.warn('Could not fetch overview alert count', e);
      }
    }
    fetchAlertCount();
  }, [parentSessionToken]);

  // Active session helper
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const messages = activeSession?.messages || [];

  // Persist sessions
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, 30)));
  }, [sessions]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamAnswer, isAsking]);

  // Initial Health & Subjects check
  useEffect(() => {
    async function init() {
      // Health check
      try {
        const hRes = await fetch('/api/health');
        if (hRes.ok) {
          const h = await hRes.json();
          const ok = h.status === 'ok';
          setStatus({
            text: ok ? 'Ready' : 'Problem',
            type: ok ? 'ok' : 'error',
          });
        } else {
          setStatus({ text: 'Server offline', type: 'error' });
        }
      } catch {
        setStatus({ text: 'Server offline', type: 'error' });
      }

      // Load subjects
      try {
        const token = getStoredToken();
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const sRes = await fetch('/api/subjects', { headers });
        if (sRes.ok) {
          const data = await sRes.json();
          setSubjects(data);
          // Do NOT auto-select subject! Let user select "Choose subject" every time.
        }
      } catch (e) {
        console.error('Failed to load subjects', e);
      }

      // Load models & active LLM
      try {
        const mRes = await fetch('/api/models');
        if (mRes.ok) {
          const mData = await mRes.json();
          if (mData.active) setActiveModelInfo(mData.active);
          if (mData.local) setLocalModels(mData.local);
          if (mData.cloud) setCloudModels(mData.cloud);
        }
      } catch (e) {
        console.error('Failed to load models', e);
      }
    }
    init();
  }, []);

  const handleSelectModel = async (provider, model) => {
    try {
      const res = await fetch('/api/models/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.active) {
          setActiveModelInfo(data.active);
        }
      }
    } catch (e) {
      console.error('Failed to switch model', e);
    }
  };

  // Ensure an active session exists
  const getOrCreateActiveSessionId = () => {
    if (activeSessionId && sessions.some((s) => s.id === activeSessionId)) {
      return activeSessionId;
    }
    const newSession = {
      id: crypto.randomUUID(),
      title: 'New conversation',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    return newSession.id;
  };

  const handleNewChat = () => {
    const newSession = {
      id: crypto.randomUUID(),
      title: 'New conversation',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setSelectedSubject('');
    setSelectedChapter(null);
    setCurrentStreamAnswer('');
    setCurrentStreamSources([]);
    setFeedbackSent(false);
    setSidebarOpen(false);
  };

  const handleClearHistory = () => {
    if (window.confirm('Clear all conversation history?')) {
      setSessions([]);
      setActiveSessionId(null);
      setCurrentStreamAnswer('');
      setCurrentStreamSources([]);
    }
  };

  const handleDeleteSession = (sessionId) => {
    setSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(remaining[0]?.id || null);
      }
      return remaining;
    });
  };

  const openActivityModal = async () => {
    setActiveModal('activity');
    try {
      const res = await fetch('/api/metrics?limit=30');
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      }
    } catch (e) {
      console.error('Failed to load metrics:', e);
    }
  };

  const handleNewNotebook = () => {
    const title = window.prompt('Enter notebook name:');
    if (title && title.trim()) {
      const newNb = {
        id: 'nb_' + Date.now(),
        title: title.trim(),
        createdAt: Date.now(),
      };
      const updated = [newNb, ...notebooks];
      setNotebooks(updated);
      try {
        localStorage.setItem('gemini_notebooks', JSON.stringify(updated));
      } catch { }
      setActiveModal('notebooks');
    }
  };

  // Sync sidebar collapsed state
  useEffect(() => {
    try {
      localStorage.setItem('gemini_sidebar_collapsed', sidebarCollapsed ? 'true' : 'false');
    } catch { }
  }, [sidebarCollapsed]);

  // Filtered session list for real-time search
  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    if (s.title && s.title.toLowerCase().includes(q)) return true;
    return s.messages?.some((m) => m.text && m.text.toLowerCase().includes(q));
  });

  const submitQuestion = async (q, pureLlm = false, fromMessageIndex = null) => {
    const cleanQ = (q || '').trim();
    if (!cleanQ || isAsking) return;

    if (!selectedSubject) {
      const subjectBtn = document.getElementById('subject-select');
      if (subjectBtn) {
        subjectBtn.click();
        subjectBtn.focus();
      }
      return;
    }

    const currentSid = getOrCreateActiveSessionId();

    if (fromMessageIndex !== null) {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSid) {
            const updated = [...s.messages];
            if (updated[fromMessageIndex]) {
              updated[fromMessageIndex] = {
                ...updated[fromMessageIndex],
                promptPureLlm: false,
                declinedPureLlm: false,
                pureLlmRequested: true,
              };
            }
            return { ...s, messages: updated };
          }
          return s;
        })
      );
    } else {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSid) {
            const isFirstUserMsg = s.messages.length === 0 || s.title === 'New conversation';
            return {
              ...s,
              title: isFirstUserMsg ? cleanQ.slice(0, 42) : s.title,
              updatedAt: Date.now(),
              messages: [...s.messages, { role: 'user', text: cleanQ }],
            };
          }
          return s;
        })
      );
      setQuestion('');
    }

    setIsAsking(true);
    setThinkingState(pureLlm ? 'working' : 'searching');
    setThinkingText(pureLlm ? 'Generating AI answer…' : 'Searching your textbook…');
    setCurrentStreamAnswer('');
    setCurrentStreamSources([]);
    setFeedbackSent(false);

    const activeSession = sessions.find((s) => s.id === currentSid);
    const historyPayload = (activeSession?.messages || [])
      .filter((m) => m.text && (m.role === 'user' || m.role === 'assistant'))
      .slice(-30)
      .map((m) => ({
        role: m.role,
        content: m.text,
        model_id: m.model_id,
      }));

    const currentModelId = activeModelInfo?.model_id || `${activeModelInfo?.provider}/${activeModelInfo?.model}`;
    const currentModelName = activeModelInfo?.model || 'qwen3.5:4b';

    try {
      const token = authToken || getStoredToken();
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/ask/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          question: cleanQ,
          grade: authorizedGrade,
          subject: selectedSubject,
          chapter: selectedChapter,
          language,
          pure_llm: pureLlm,
          session_id: currentSid,
          history: historyPayload,
          model_id: currentModelId,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to get an answer.');
      }

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = '';
      let answerText = '';
      let collectedSources = [];
      let isFound = true;
      let shouldPromptPureLlm = false;
      let streamMetrics = null;

      setThinkingState('working');
      setThinkingText(pureLlm ? 'Composing AI answer…' : 'Composing answer…');

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines.filter(Boolean)) {
          try {
            const ev = JSON.parse(line);
            if (ev.type === 'token') {
              answerText += ev.text;
              setCurrentStreamAnswer(answerText);
            } else if (ev.type === 'done') {
              collectedSources = ev.sources || [];
              if (ev.found !== undefined) isFound = ev.found;
              if (ev.prompt_pure_llm) shouldPromptPureLlm = true;
              if (ev.metrics) streamMetrics = ev.metrics;
              setCurrentStreamSources(collectedSources);
            } else if (ev.type === 'error') {
              throw new Error(ev.message);
            }
          } catch (parseErr) {
            if (parseErr.message && !parseErr.message.includes('JSON')) {
              throw parseErr;
            }
          }
        }
      }

      // Add final assistant message to session
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSid) {
            return {
              ...s,
              updatedAt: Date.now(),
              messages: [
                ...s.messages,
                {
                  role: 'assistant',
                  text: answerText,
                  sources: collectedSources,
                  found: isFound,
                  pureLlm: pureLlm,
                  promptPureLlm: !pureLlm && (!isFound || shouldPromptPureLlm),
                  questionPrompt: cleanQ,
                  metrics: streamMetrics,
                  model_id: currentModelId,
                  model_name: currentModelName,
                },
              ],
            };
          }
          return s;
        })
      );
      setCurrentStreamAnswer('');
      setCurrentStreamSources([]);
    } catch (err) {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSid) {
            return {
              ...s,
              updatedAt: Date.now(),
              messages: [
                ...s.messages,
                {
                  role: 'assistant',
                  text: `⚠️ **Error**: ${err.message || 'Could not reach local AI.'}`,
                  sources: [],
                  found: false,
                },
              ],
            };
          }
          return s;
        })
      );
      setCurrentStreamAnswer('');
    } finally {
      setIsAsking(false);
      setThinkingState('idle');
      setThinkingText('');
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  };

  const handleDismissPureLlm = (messageIndex) => {
    const currentSid = getOrCreateActiveSessionId();
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === currentSid) {
          const updated = [...s.messages];
          if (updated[messageIndex]) {
            updated[messageIndex] = {
              ...updated[messageIndex],
              promptPureLlm: false,
              declinedPureLlm: true,
            };
          }
          return { ...s, messages: updated };
        }
        return s;
      })
    );
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    submitQuestion(question, false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFeedback = async (helpful, lastQuestionText, answerText) => {
    setFeedbackSent(true);
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: lastQuestionText || 'Question',
          answer: answerText || 'Answer',
          helpful,
          grade: selectedGrade,
          subject: selectedSubject,
        }),
      });
    } catch (err) {
      console.warn('Feedback could not be logged', err);
    }
  };

  const openPdf = (file, page, title) => {
    if (!file) return;
    setPdfPreview({
      isOpen: true,
      file,
      page: page || 1,
      title: title || 'PDF Preview',
    });
  };

  const closePdf = () => {
    setPdfPreview((prev) => ({ ...prev, isOpen: false }));
  };

  const authorizedGrade = studentUser?.grade || selectedGrade || 10;
  // If student is authorized for Class 10, strictly show only Class 10 subjects
  const availableGrades = [...new Set(subjects.map((s) => s.grade))].sort((a, b) => a - b);
  const availableSubjects = subjects.filter((s) => Number(s.grade) === Number(authorizedGrade));
  const currentBook = availableSubjects.find((s) => s.subject === selectedSubject);
  const availableChapters = currentBook?.chapters || [];
  const exampleQuestions = (selectedSubject && EXAMPLES[`${authorizedGrade}|${selectedSubject}`])
    || EXAMPLES[`${authorizedGrade}|English`]
    || EXAMPLES['10|Science']
    || ['What is a balanced chemical equation?', 'Why does the sky appear blue?'];

  // Merge static NCERT books with dynamic parent-uploaded custom curriculum books
  const allCatalogBooks = useMemo(() => {
    const list = [...TEXTBOOK_CATALOG];
    subjects.forEach((s) => {
      const exists = list.some(
        (b) => b.grade === s.grade && b.subject.toLowerCase() === s.subject.toLowerCase()
      );
      if (!exists) {
        list.push({
          grade: s.grade,
          subject: s.subject,
          title: s.book || `${s.subject} (Class ${s.grade})`,
          subtitle: `Parent-Approved Curriculum Textbook · ${s.chapters?.length || 1} chapter(s)`,
          chapters: s.chapters && s.chapters.length > 0 ? s.chapters : [{ number: 1, title: s.subject }],
          file: s.file,
          isCustom: true,
        });
      } else if (s.file) {
        const item = list.find((b) => b.grade === s.grade && b.subject.toLowerCase() === s.subject.toLowerCase());
        if (item && !item.file) {
          item.file = s.file;
        }
      }
    });
    return list;
  }, [subjects]);

  const uniqueCatalogGrades = useMemo(() => {
    return [...new Set(allCatalogBooks.map((b) => b.grade))].sort((a, b) => b - a);
  }, [allCatalogBooks]);

  return (
    <div className="app-container">
      {/* ── Sidebar (Official Google Gemini Dark System) ── */}
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${sidebarOpen ? 'open' : ''}`}>
        {/* Learnright Header */}
        <div className="gemini-header">
          <div className="gemini-brand" onClick={handleNewChat} title="Learnright - New chat">
            <BotAvatar
              type="clover"
              size={30}
              color="#8b5cf6"
              shading="fabric"
              state="default"
              interactive={true}
            />
            <span className="learnright-title">Learnright</span>
          </div>
          <div className="gemini-header-actions">
            <button
              className="gemini-icon-btn"
              type="button"
              onClick={() => setShowSearch(!showSearch)}
              title="Search chats"
              aria-label="Search chats"
            >
              <SearchIcon size={19} />
            </button>
            <button
              className="gemini-icon-btn"
              type="button"
              onClick={() => {
                setSidebarCollapsed(true);
                setSidebarOpen(false);
              }}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <SidebarToggleIcon size={20} />
            </button>
          </div>
        </div>

        {/* New chat Pill Button */}
        <button className="gemini-new-chat-btn" onClick={handleNewChat} type="button">
          <span className="new-chat-icon">
            <ComposeIcon size={18} />
          </span>
          New chat
        </button>

        {/* Quick Menu Items */}
        <button className="gemini-nav-item" type="button" onClick={() => setActiveModal('library')}>
          <span className="gemini-nav-icon"><LibraryIcon size={18} /></span>
          Library
        </button>

        <button className="gemini-nav-item" type="button" onClick={openActivityModal}>
          <span className="gemini-nav-icon"><ScheduledIcon size={18} /></span>
          Scheduled
        </button>

        <button className="gemini-nav-item" type="button" onClick={() => setActiveModal('customise')}>
          <span className="gemini-nav-icon"><CustomiseIcon size={18} /></span>
          Customise
        </button>

        <button
          className="gemini-nav-item"
          type="button"
          onClick={() => handleOpenParental('overview')}
          title="Parental Controls & Student Safety Portal"
        >
          <span className="gemini-nav-icon"><ShieldIcon size={18} /></span>
          Parental
          {unreviewedAlertCount > 0 && (
            <span className="gemini-nav-badge">{unreviewedAlertCount}</span>
          )}
        </button>

        {/* Notebooks Section */}
        <div className="gemini-section-header">
          <span>Notebooks</span>
        </div>
        <button className="gemini-nav-item" type="button" onClick={handleNewNotebook}>
          <span className="gemini-nav-icon"><PlusIcon size={16} /></span>
          New notebook
        </button>

        {/* All Section (History) */}
        <div className="gemini-section-header">
          <span>All</span>
          <button
            className="gemini-filter-btn"
            type="button"
            onClick={() => setShowSearch(!showSearch)}
            title="Filter chats"
          >
            <FilterIcon size={15} />
          </button>
        </div>

        {/* Search Input when toggled */}
        {showSearch && (
          <div className="gemini-search-wrap">
            <input
              type="text"
              className="gemini-search-input"
              placeholder="Search conversations…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
          </div>
        )}

        {/* Chat History List with single line, ellipsis, and active blue dot */}
        <nav className="gemini-history-list">
          {filteredSessions.length === 0 ? (
            <div className="history-empty-note">
              {searchQuery ? 'No matching conversations' : 'No chats yet'}
            </div>
          ) : (
            filteredSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  className={`gemini-history-item ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setActiveSessionId(s.id);
                    setSidebarOpen(false);
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <span className="history-text" title={s.title || 'New conversation'}>
                    {s.title || 'New conversation'}
                  </span>
                  {isActive && <span className="gemini-active-dot" />}
                  <button
                    className="history-delete-btn"
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(s.id);
                    }}
                    title="Delete chat"
                  >
                    ✕
                  </button>
                </div>
              );
            })
          )}
        </nav>

        {/* Sidebar Footer with Student Profile / Class Card */}
        <div className="sidebar-footer">
          {userMenuOpen && (
            <div className="user-menu-popover">
              <div className="user-menu-header">Profile &amp; Institution Roles</div>

              {/* Institution Actions */}
              <button
                type="button"
                className="user-menu-item"
                onClick={() => {
                  setUserMenuOpen(false);
                  setInstAdminModalOpen(true);
                }}
              >
                <span>🏛️ Manage Institution &amp; Classes</span>
              </button>

              <button
                type="button"
                className="user-menu-item"
                onClick={() => {
                  setUserMenuOpen(false);
                  setJoinInstModalOpen(true);
                }}
              >
                <span>🏫 Join an Institution (Invite)</span>
              </button>

              <button
                type="button"
                className="user-menu-item"
                onClick={() => {
                  setUserMenuOpen(false);
                  setTutorialModalOpen(true);
                }}
              >
                <span>✨ Welcome Tutorial &amp; Guide</span>
              </button>

              <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />

              {/* Demo Role Switcher */}
              <div className="user-menu-header" style={{ fontSize: 11 }}>Switch Role (Demo)</div>
              <button
                type="button"
                className={`user-menu-item ${studentUser?.role === 'student' && studentUser?.grade === 10 ? 'active' : ''}`}
                onClick={() => handleSwitchDemoRole('student', 10)}
              >
                <span>Student · Class 10</span>
                {studentUser?.role === 'student' && studentUser?.grade === 10 && <span>✓</span>}
              </button>

              <button
                type="button"
                className={`user-menu-item ${studentUser?.role === 'org_admin' ? 'active' : ''}`}
                onClick={() => handleSwitchDemoRole('org_admin')}
              >
                <span>Org Admin (Principal)</span>
                {studentUser?.role === 'org_admin' && <span>✓</span>}
              </button>

              <button
                type="button"
                className={`user-menu-item ${studentUser?.role === 'lecturer' ? 'active' : ''}`}
                onClick={() => handleSwitchDemoRole('lecturer')}
              >
                <span>Lecturer (Faculty)</span>
                {studentUser?.role === 'lecturer' && <span>✓</span>}
              </button>

              <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />

              <button
                type="button"
                className="user-menu-item"
                onClick={() => {
                  window.location.href = '/login';
                }}
              >
                <span>🔑 Switch Account / Sign In</span>
              </button>
            </div>
          )}

          <div
            className="sidebar-user-card"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            role="button"
            tabIndex={0}
          >
            <div className="user-avatar-wrap">
              <div className="user-avatar-placeholder">
                {(studentUser?.full_name || studentUser?.username || 'Abin Biju')
                  .split(' ')
                  .map((n) => n[0])
                  .join('')
                  .toUpperCase()
                  .slice(0, 2)}
              </div>
            </div>
            <div className="user-info">
              <span className="user-name" title={studentUser?.full_name || studentUser?.username || 'Abin Biju'}>
                {studentUser?.full_name || studentUser?.username || 'Abin Biju'}
              </span>
              <span className="user-role-badge">
                {studentUser?.role === 'org_admin'
                  ? 'Org Admin'
                  : studentUser?.role === 'lecturer'
                  ? 'Lecturer'
                  : `Class ${studentUser?.grade || 10}${studentUser?.section_name ? `-${studentUser.section_name}` : ''}`}
              </span>
            </div>
            <button
              type="button"
              className="user-settings-btn"
              title="Settings & Switch Class"
              onClick={(e) => {
                e.stopPropagation();
                setUserMenuOpen(!userMenuOpen);
              }}
            >
              <SettingsGearIcon size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Workspace ── */}
      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            {sidebarCollapsed && (
              <button
                className="gemini-topbar-expand-btn"
                onClick={() => setSidebarCollapsed(false)}
                type="button"
                title="Expand sidebar"
              >
                <SidebarToggleIcon size={20} />
                <span className="gemini-topbar-logo-wrap">
                  <BotAvatar
                    type="clover"
                    size={22}
                    color="#8b5cf6"
                    shading="fabric"
                    state="default"
                    interactive={true}
                  />
                </span>
                <span className="learnright-topbar-title">Learnright</span>
              </button>
            )}
            <button
              className="mobile-toggle"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              type="button"
              aria-label="Toggle menu"
            >
              ☰
            </button>
          </div>
          <div className="topbar-right">
            {/* Institution Badge / Join Action */}
            {studentUser?.institution_id ? (
              studentUser?.role === 'org_admin' ? (
                <button
                  type="button"
                  className="institution-badge-pill"
                  onClick={() => setInstAdminModalOpen(true)}
                  title="Manage School Institution, Classes & Faculty"
                >
                  <span>🏛️</span>
                  <span>{studentUser.institution_name || 'My Institution'}</span>
                  <span className="inst-badge-role">Admin Console ⚙️</span>
                </button>
              ) : studentUser?.role === 'lecturer' ? (
                <button
                  type="button"
                  className="institution-badge-pill"
                  onClick={() => setInstAdminModalOpen(true)}
                  title="Institution Faculty Portal"
                >
                  <span>🏛️</span>
                  <span>{studentUser.institution_name || 'My Institution'}</span>
                  <span className="inst-badge-role">Faculty</span>
                </button>
              ) : (
                <div className="institution-badge-pill" title="Enrolled School Institution">
                  <span>🏛️</span>
                  <span>{studentUser.institution_name || 'My Institution'}</span>
                  {studentUser.section_name && (
                    <span className="inst-badge-role">Sec {studentUser.section_name}</span>
                  )}
                </div>
              )
            ) : (
              <button
                type="button"
                className="institution-join-pill"
                onClick={() => setJoinInstModalOpen(true)}
                title="Connect with your school organization via invite code"
              >
                <span>🏫 Join your Institution</span>
              </button>
            )}

            {pdfPreview.isOpen && (
              <button className="pdf-toggle-btn" onClick={closePdf} type="button">
                Hide PDF
              </button>
            )}

            <button
              type="button"
              className="topbar-tutorial-btn"
              onClick={() => setTutorialModalOpen(true)}
              title="Learnright Tutorial & Quick Guide"
            >
              <span>✨</span>
              <span>Tutorial</span>
            </button>
          </div>
        </header>

        <div className="workspace-body">
          <section className="chat-panel">
            <div className="messages-container">
              {messages.length === 0 && !isAsking && (
                <div className="welcome-screen">
                  <div className="welcome-avatar-wrapper">
                    <BotAvatar
                      type="clover"
                      size={92}
                      color="#8b5cf6"
                      shading="fabric"
                      state="default"
                      interactive={true}
                    />
                  </div>
                  <h2 className="welcome-title metallic-font">What would you like to learn?</h2>
                  <p className="welcome-desc">
                    Ask a question about your selected textbook.
                  </p>

                  <button
                    type="button"
                    className="topbar-tutorial-btn"
                    onClick={() => setTutorialModalOpen(true)}
                    style={{ marginTop: 8, marginBottom: 16 }}
                  >
                    <span>✨</span>
                    <span>New to Learnright? Take the quick tour</span>
                  </button>

                  <div className="example-chips">
                    {exampleQuestions.map((eg, idx) => (
                      <button
                        key={idx}
                        className="chip-btn"
                        onClick={() => {
                          setQuestion(eg);
                          textareaRef.current?.focus();
                        }}
                        type="button"
                      >
                        {eg}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Render Saved Messages */}
              {messages.map((msg, index) => {
                const isUser = msg.role === 'user';
                return (
                  <div key={index} className={`message-row ${isUser ? 'user' : 'assistant'}`}>
                    <div className="message-avatar">
                      {isUser ? (
                        <div className="user-avatar-badge">Y</div>
                      ) : (
                        <BotAvatar
                          type="clover"
                          size={34}
                          color="#8b5cf6"
                          shading="fabric"
                          state="default"
                          interactive={true}
                        />
                      )}
                    </div>
                    <div className="message-content">
                      {msg.pureLlm && (
                        <div className="pure-llm-badge">
                          ✨ Pure AI Generation · General Knowledge (Not in Textbook)
                        </div>
                      )}

                      <div
                        className="message-bubble markdown-body"
                        dangerouslySetInnerHTML={{ __html: formatAnswer(msg.text) }}
                      />

                      {/* Conversation Turn Metrics Bar */}
                      {(msg.metrics || msg.model_id) && (
                        <div className="msg-metrics-bar">
                          {(msg.model_name || msg.model_id) && (
                            <span className="metric-tag model-tag" title={`Generated by ${msg.model_name || msg.model_id}`}>
                              🤖 {msg.model_name || msg.model_id}
                            </span>
                          )}
                          {msg.metrics?.total_latency_s !== undefined && (
                            <span className="metric-tag" title="Total response latency">⏱️ {msg.metrics.total_latency_s}s</span>
                          )}
                          {msg.metrics?.tokens_per_second > 0 && (
                            <span className="metric-tag" title="Generation speed">⚡ {msg.metrics.tokens_per_second} tok/s</span>
                          )}
                          {msg.metrics?.retrieval_time_s > 0 && (
                            <span className="metric-tag" title="Textbook retrieval time">🔍 {msg.metrics.retrieval_time_s}s search</span>
                          )}
                          {msg.metrics?.top_similarity_score !== undefined && msg.metrics?.top_similarity_score !== null && (
                            <span className="metric-tag" title="Top similarity score">🎯 Match: {(msg.metrics.top_similarity_score * 100).toFixed(0)}%</span>
                          )}
                        </div>
                      )}

                      {/* Sources block if available - open by default so retrieved chunk is visible below */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="sources-card">
                          <div className="sources-heading">
                            📚 Sources retrieved from your textbook ({msg.sources.length} {msg.sources.length === 1 ? 'page' : 'pages'})
                          </div>
                          {msg.sources.map((src, sIdx) => (
                            <div key={sIdx} className="source-item">
                              <details open className="source-details">
                                <summary className="source-summary">
                                  <span>
                                    Chapter {src.chapter}: {src.chapter_title} (Page {src.page})
                                  </span>
                                  <button
                                    type="button"
                                    className="source-preview-btn"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      openPdf(src.file, src.page, src.chapter_title);
                                    }}
                                  >
                                    Preview PDF ↗
                                  </button>
                                </summary>
                                <blockquote className="source-quote">{src.text}</blockquote>
                              </details>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Fallback Yes/No prompt when no textbook chunk is found */}
                      {!msg.found && msg.promptPureLlm && !msg.declinedPureLlm && !msg.pureLlmRequested && !isAsking && (
                        <div className="pure-llm-prompt-card">
                          <div className="pure-llm-prompt-body">
                            <div className="pure-llm-prompt-icon">💡</div>
                            <div className="pure-llm-prompt-content">
                              <div className="pure-llm-prompt-title">No relevant content found in textbook</div>
                              <div className="pure-llm-prompt-desc">
                                Would you like me to answer this question purely using the AI model's general knowledge?
                              </div>
                            </div>
                          </div>
                          <div className="pure-llm-prompt-actions">
                            <button
                              type="button"
                              className="pure-llm-btn pure-llm-btn-yes"
                              onClick={() => submitQuestion(msg.questionPrompt || (messages[index - 1]?.text), true, index)}
                            >
                              ✨ Yes, answer with AI
                            </button>
                            <button
                              type="button"
                              className="pure-llm-btn pure-llm-btn-no"
                              onClick={() => handleDismissPureLlm(index)}
                            >
                              ✕ No, thanks
                            </button>
                          </div>
                        </div>
                      )}

                      {msg.declinedPureLlm && (
                        <div className="pure-llm-declined-note">
                          ℹ️ Understood. Feel free to ask another question from your textbook.
                        </div>
                      )}

                      {msg.pureLlmRequested && (
                        <div className="pure-llm-requested-note">
                          ✨ Generated pure AI response below.
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Streaming Live In-Flight Assistant Message */}
              {isAsking && (
                <div className="message-row assistant">
                  <div className="message-avatar">
                    <BotAvatar
                      type="clover"
                      size={34}
                      color="#8b5cf6"
                      shading="fabric"
                      state="working"
                      interactive={true}
                    />
                  </div>
                  <div className="message-content">
                    {/* The Exact Thinking Capsule Pill (Screenshot media_1793287303136.png) */}
                    <div className="thinking-capsule">
                      <div className="thinking-orb-wrap">
                        <ThinkingOrb state={thinkingState} size={20} theme="dark" />
                      </div>
                      <span className="cursor-line">|</span>
                      <span className="thinking-text">{thinkingText}</span>
                    </div>

                    {currentStreamAnswer && (
                      <div
                        className="message-bubble markdown-body"
                        dangerouslySetInnerHTML={{ __html: formatAnswer(currentStreamAnswer) }}
                      />
                    )}

                    {currentStreamSources.length > 0 && (
                      <div className="sources-card">
                        <div className="sources-heading">
                          📚 Sources retrieved from your textbook ({currentStreamSources.length} {currentStreamSources.length === 1 ? 'page' : 'pages'})
                        </div>
                        {currentStreamSources.map((src, sIdx) => (
                          <div key={sIdx} className="source-item">
                            <details open className="source-details">
                              <summary className="source-summary">
                                <span>
                                  Chapter {src.chapter}: {src.chapter_title} (Page {src.page})
                                </span>
                                <button
                                  type="button"
                                  className="source-preview-btn"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    openPdf(src.file, src.page, src.chapter_title);
                                  }}
                                >
                                  Preview PDF ↗
                                </button>
                              </summary>
                              <blockquote className="source-quote">{src.text}</blockquote>
                            </details>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Thumbs up / down feedback row on latest completed assistant message */}
              {messages.length > 0 &&
                messages[messages.length - 1].role === 'assistant' &&
                !isAsking && (
                  <div className="feedback-row" style={{ marginLeft: 48 }}>
                    <span>Was this helpful?</span>
                    <button
                      type="button"
                      className="feedback-btn"
                      disabled={feedbackSent}
                      onClick={() =>
                        handleFeedback(
                          true,
                          messages[messages.length - 2]?.text,
                          messages[messages.length - 1]?.text
                        )
                      }
                      title="Yes, helpful"
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      className="feedback-btn"
                      disabled={feedbackSent}
                      onClick={() =>
                        handleFeedback(
                          false,
                          messages[messages.length - 2]?.text,
                          messages[messages.length - 1]?.text
                        )
                      }
                      title="No, not helpful"
                    >
                      👎
                    </button>
                    {feedbackSent && <span className="feedback-thanks">Thanks for your feedback! ✓</span>}
                  </div>
                )}

              <div ref={messagesEndRef} />
            </div>

            {/* ── Bottom Floating Unified Search Bar / Composer (Matching Image 2) ── */}
            <div className="composer-dock">
              <div className="composer-outer-wrap">
                {/* The box wrapped in BorderBeam from required_elements.md lines 119-125 */}
                <BorderBeam size="md" colorVariant="colorful" theme="dark" style={{ width: '100%', display: 'block' }}>
                  <form className="composer-box" onSubmit={handleSubmit}>
                    <textarea
                      ref={textareaRef}
                      className="composer-textarea"
                      rows={2}
                      maxLength={500}
                      placeholder="Ask anything about your textbook…"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={isAsking}
                    />

                    <div className="composer-footer">
                      {/* Left: + Action Button & Popover Menu */}
                      <div className="composer-plus-wrap">
                        <button
                          className={`composer-plus-btn ${plusMenuOpen ? 'active' : ''}`}
                          type="button"
                          onClick={() => setPlusMenuOpen(!plusMenuOpen)}
                          title="Options & Tools"
                          aria-haspopup="menu"
                          aria-expanded={plusMenuOpen}
                        >
                          <PlusIcon size={16} />
                        </button>

                        {plusMenuOpen && (
                          <div className="composer-plus-menu" role="menu">
                            <button
                              type="button"
                              className="composer-plus-item"
                              onClick={() => {
                                setPlusMenuOpen(false);
                                setActiveModal('library');
                              }}
                            >
                              <span className="composer-plus-left">📚 Textbook Library</span>
                            </button>

                            <button
                              type="button"
                              className="composer-plus-item"
                              onClick={() => {
                                const nextLang = language === 'English' ? 'Hindi' : 'English';
                                setLanguage(nextLang);
                                setPlusMenuOpen(false);
                              }}
                              title="Toggle response language"
                            >
                              <span className="composer-plus-left">🌐 Language</span>
                              <span className="composer-plus-value">{language}</span>
                            </button>

                            <button
                              type="button"
                              className="composer-plus-item"
                              onClick={() => {
                                setPlusMenuOpen(false);
                                setActiveModal('customise');
                              }}
                              title="Browse 10 handcrafted themes"
                            >
                              <span className="composer-plus-left">🎨 Theme</span>
                              <span className="composer-plus-value">{currentThemeObj.name}</span>
                            </button>

                            <button
                              type="button"
                              className="composer-plus-item"
                              onClick={() => {
                                setPlusMenuOpen(false);
                                setActiveModal('customise');
                              }}
                              title="Customise AI Tutor persona and grade"
                            >
                              <span className="composer-plus-left">⚙️ Customise Tutor</span>
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Right: Dropdown Pills + Circular Ask Button matching Image 2 */}
                      <div className="composer-right-actions">
                        {/* 1. Model Selector Dropdown (Replaces Class dropdown with Local & Cloud Model Selector) */}
                        <ModelSelectorDropdown
                          activeModel={activeModelInfo}
                          localModels={localModels}
                          cloudModels={cloudModels}
                          onSelectModel={handleSelectModel}
                          disabled={isAsking}
                          openUpward={true}
                        />

                        {/* 2. Subject Dropdown */}
                        <AppleGlassDropdown
                          id="subject-select"
                          value={selectedSubject}
                          placeholder="Choose subject"
                          options={[
                            { value: '', label: 'Choose subject' },
                            ...availableSubjects.map((s) => ({
                              value: s.subject,
                              label: s.subject,
                            })),
                          ]}
                          onChange={(val) => {
                            setSelectedSubject(val);
                            setSelectedGrade(authorizedGrade);
                            setSelectedChapter(null);
                          }}
                          disabled={isAsking}
                          menuWidth="190px"
                          openUpward={true}
                        />

                        {/* 3. Lesson Dropdown */}
                        <AppleGlassDropdown
                          id="chapter-select"
                          value={selectedChapter ?? ''}
                          placeholder="All Lessons"
                          options={[
                            { value: '', label: 'All Lessons' },
                            ...availableChapters.map((ch) => ({
                              value: ch.number,
                              label: `Ch ${ch.number}: ${ch.title}`,
                            })),
                          ]}
                          onChange={(val) => {
                            setSelectedChapter(val ? Number(val) : null);
                          }}
                          disabled={isAsking || !selectedSubject}
                          menuWidth="260px"
                          openUpward={true}
                        />

                        {/* Circular Ask Button with Robot Logo & Polished Metallic Steel Finish (MetalFx, No Rainbow) */}
                        <MetalFx
                          variant="circle"
                          preset="silver"
                          strength={1}
                          disableGlow={true}
                          normalizeHostStyles={false}
                        >
                          <button
                            className="circle-ask-btn"
                            type="submit"
                            disabled={isAsking || question.trim().length < 2 || !selectedSubject}
                            title={!selectedSubject ? 'Please choose a subject first' : 'Ask question'}
                          >
                            <RobotAskIcon size={20} />
                          </button>
                        </MetalFx>
                      </div>
                    </div>
                  </form>
                </BorderBeam>
              </div>
            </div>
          </section>

          {/* ── PDF Preview Drawer ── */}
          {pdfPreview.isOpen && (
            <aside className="pdf-preview-drawer">
              <div className="pdf-preview-header">
                <div className="pdf-title-box">
                  <strong className="pdf-header-title">{pdfPreview.title}</strong>
                  <span className="pdf-header-page">Page {pdfPreview.page}</span>
                </div>
                <button
                  className="pdf-close-btn"
                  onClick={closePdf}
                  type="button"
                  aria-label="Close PDF preview"
                >
                  ✕
                </button>
              </div>
              <iframe
                className="pdf-iframe"
                title="Textbook PDF preview"
                src={`/pdfs/${pdfPreview.file.split('/').map(encodeURIComponent).join('/')}#page=${encodeURIComponent(pdfPreview.page)}`}
              />
            </aside>
          )}
        </div>
      </main>

      {/* ── Gemini Feature Modals (Library, Activity, Customise, Videos, Notebooks) ── */}
      {/* 1. Library Modal */}
      {activeModal === 'library' && (
        <div className="gemini-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="gemini-modal-card gemini-library-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="gemini-modal-header">
              <div className="gemini-modal-title">
                <LibraryIcon size={20} />
                <span>Textbook Library</span>
                <span className="library-header-sub">{allCatalogBooks.length} Books · {allCatalogBooks.reduce((acc, b) => acc + (b.chapters?.length || 0), 0)} Chapters</span>
              </div>
              <button className="gemini-modal-close" onClick={() => setActiveModal(null)} type="button" aria-label="Close library">✕</button>
            </div>

            <div className="gemini-modal-body library-modal-body">
              {/* Filter Tabs, Search Bar & Parental Upload Button */}
              <div className="library-toolbar">
                <div className="library-tabs">
                  {[
                    { key: 'all', label: `All Textbooks (${allCatalogBooks.length})` },
                    ...uniqueCatalogGrades.map((g) => ({
                      key: String(g),
                      label: `Class ${g} (${allCatalogBooks.filter((b) => b.grade === g).length})`,
                    })),
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      className={`library-tab ${libraryGradeFilter === tab.key ? 'active' : ''}`}
                      onClick={() => setLibraryGradeFilter(tab.key)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="library-toolbar-actions">
                  <div className="library-search-box">
                    <SearchIcon size={14} />
                    <input
                      type="text"
                      className="library-search-input"
                      placeholder="Search chapters or topics…"
                      value={librarySearch}
                      onChange={(e) => setLibrarySearch(e.target.value)}
                    />
                    {librarySearch && (
                      <button
                        type="button"
                        className="library-search-clear"
                        onClick={() => setLibrarySearch('')}
                        aria-label="Clear search"
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    className="library-upload-trigger-btn"
                    onClick={() => {
                      setActiveModal(null);
                      handleOpenParental('upload');
                    }}
                    title="Upload a new textbook (Requires Parental Authorization)"
                  >
                    <ShieldIcon size={14} />
                    <span>Upload Textbook</span>
                  </button>
                </div>
              </div>

              {/* Books & Chapters List */}
              <div className="library-book-list">
                {allCatalogBooks
                  .filter((b) => {
                    if (libraryGradeFilter !== 'all' && String(b.grade) !== libraryGradeFilter) return false;
                    if (!librarySearch.trim()) return true;
                    const q = librarySearch.toLowerCase();
                    const matchesBook = b.title.toLowerCase().includes(q) || b.subject.toLowerCase().includes(q) || (b.subtitle && b.subtitle.toLowerCase().includes(q));
                    const matchesChapter = b.chapters.some((ch) => ch.title.toLowerCase().includes(q) || String(ch.number).includes(q));
                    return matchesBook || matchesChapter;
                  })
                  .map((b) => {
                    const bookKey = `${b.grade}|${b.subject}`;
                    const isExpanded = expandedBookKey === bookKey || Boolean(librarySearch.trim());
                    const filteredChapters = librarySearch.trim()
                      ? b.chapters.filter((ch) => ch.title.toLowerCase().includes(librarySearch.toLowerCase()) || String(ch.number).includes(librarySearch.trim()))
                      : b.chapters;

                    return (
                      <div key={bookKey} className={`library-book-card ${isExpanded ? 'expanded' : ''}`}>
                        {/* Book Card Header */}
                        <div
                          className="library-book-header"
                          onClick={() => setExpandedBookKey(isExpanded && !librarySearch.trim() ? null : bookKey)}
                        >
                          <div className="library-book-meta">
                            <div className="library-book-badges">
                              <span className="library-badge-grade">Class {b.grade}</span>
                              <span className="library-badge-subject">{b.subject}</span>
                              <span className="library-badge-count">{b.chapters.length} Chapters</span>
                              {b.isCustom && <span className="library-badge-custom">Parent Approved</span>}
                            </div>
                            <h3 className="library-book-name">{b.title}</h3>
                            <p className="library-book-desc">{b.subtitle}</p>
                          </div>

                          <div className="library-book-actions" onClick={(e) => e.stopPropagation()}>
                            {/* Preview Book Option */}
                            <button
                              type="button"
                              className="library-preview-book-btn"
                              onClick={() => {
                                const pdfPath = b.file || getChapterPdfPath(b.grade, b.subject, 1);
                                openPdf(pdfPath, 1, `${b.title} (Class ${b.grade})`);
                                setActiveModal(null);
                              }}
                              title={`Preview ${b.title}`}
                            >
                              <BookOpenIcon size={14} />
                              <span>Preview book</span>
                            </button>

                            {/* Show/Hide Chapters Toggle */}
                            <button
                              type="button"
                              className="library-expand-toggle-btn"
                              onClick={() => setExpandedBookKey(isExpanded && !librarySearch.trim() ? null : bookKey)}
                              title={isExpanded ? 'Collapse chapters' : 'Show all chapters'}
                            >
                              <span>{isExpanded ? 'Hide' : 'Chapters'}</span>
                              <span className={`expand-chevron ${isExpanded ? 'open' : ''}`}>
                                <ChevronDownIcon size={14} />
                              </span>
                            </button>
                          </div>
                        </div>

                        {/* List of Chapters */}
                        {isExpanded && (
                          <div className="library-chapter-container">
                            <div className="library-chapter-header-row">
                              <span>Chapters & Lessons ({filteredChapters.length})</span>
                              <span className="library-hint">Click Preview to view PDF, or Ask Tutor to study</span>
                            </div>
                            <div className="library-chapter-list">
                              {filteredChapters.map((ch) => (
                                <div key={ch.number} className="library-chapter-item">
                                  <div
                                    className="library-chapter-info"
                                    onClick={() => {
                                      setSelectedGrade(b.grade);
                                      setSelectedSubject(b.subject);
                                      setSelectedChapter(ch.number);
                                      setActiveModal(null);
                                    }}
                                  >
                                    <span className="library-ch-number">Ch {ch.number}</span>
                                    <span className="library-ch-title">{ch.title}</span>
                                  </div>
                                  <div className="library-ch-actions">
                                    <button
                                      type="button"
                                      className="library-ch-action-btn preview"
                                      onClick={() => {
                                        const pdfPath = b.file || getChapterPdfPath(b.grade, b.subject, ch.number);
                                        openPdf(pdfPath, 1, `Class ${b.grade} ${b.subject} · Ch ${ch.number}: ${ch.title}`);
                                        setActiveModal(null);
                                      }}
                                      title={`Preview Chapter ${ch.number} PDF`}
                                    >
                                      <BookOpenIcon size={12} />
                                      <span>Preview</span>
                                    </button>
                                    <button
                                      type="button"
                                      className="library-ch-action-btn select"
                                      onClick={() => {
                                        setSelectedGrade(b.grade);
                                        setSelectedSubject(b.subject);
                                        setSelectedChapter(ch.number);
                                        setActiveModal(null);
                                      }}
                                      title={`Ask AI tutor about Chapter ${ch.number}`}
                                    >
                                      <span>Ask Tutor →</span>
                                    </button>
                                  </div>
                                </div>
                              ))}
                              {filteredChapters.length === 0 && (
                                <div className="library-no-chapters">
                                  No chapters match "{librarySearch}" in this textbook.
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Activity & Scheduled Metrics Modal */}
      {activeModal === 'activity' && (
        <div className="gemini-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="gemini-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="gemini-modal-header">
              <div className="gemini-modal-title">
                <ScheduledIcon size={20} />
                <span>Conversation Metrics & Activity</span>
              </div>
              <button className="gemini-modal-close" onClick={() => setActiveModal(null)} type="button">✕</button>
            </div>
            <div className="gemini-modal-body">
              <div className="modal-stat-grid">
                <div className="modal-stat-box">
                  <span className="stat-label">Total Queries</span>
                  <span className="stat-val">{metricsData?.total_records || sessions.length}</span>
                </div>
                <div className="modal-stat-box">
                  <span className="stat-label">Avg Latency</span>
                  <span className="stat-val">{metricsData?.aggregates?.avg_latency_s ? `${metricsData.aggregates.avg_latency_s}s` : '1.2s'}</span>
                </div>
                <div className="modal-stat-box">
                  <span className="stat-label">Avg Speed</span>
                  <span className="stat-val">{metricsData?.aggregates?.avg_tokens_per_second ? `${metricsData.aggregates.avg_tokens_per_second} t/s` : '68 t/s'}</span>
                </div>
              </div>
              <div>
                <span className="modal-item-title" style={{ display: 'block', marginBottom: '10px' }}>Recent Logged Queries</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(metricsData?.records || []).slice(0, 5).map((rec, rIdx) => (
                    <div key={rIdx} className="modal-card-item" style={{ cursor: 'default' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span className="modal-item-badge">Class {rec.grade} {rec.subject} {rec.pure_llm ? '· Pure AI' : '· Textbook'}</span>
                        <span style={{ color: '#8e918f' }}>⏱️ {rec.total_latency_s}s</span>
                      </div>
                      <span className="modal-item-title">{rec.question}</span>
                      {rec.tokens_per_second > 0 && (
                        <span className="modal-item-desc">⚡ {rec.tokens_per_second} tok/s · {rec.tokens_generated} tokens</span>
                      )}
                    </div>
                  ))}
                  {(!metricsData?.records || metricsData.records.length === 0) && (
                    <p className="modal-item-desc">No queries logged yet in this session.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Customise Modal */}
      {activeModal === 'customise' && (
        <div className="gemini-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="gemini-modal-card gemini-library-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="gemini-modal-header">
              <div className="gemini-modal-title">
                <CustomiseIcon size={20} />
                <span>Customise AI Tutor & Appearance</span>
              </div>
              <button className="gemini-modal-close" onClick={() => setActiveModal(null)} type="button">✕</button>
            </div>
            <div className="gemini-modal-body">
              {/* 1. Theme Option: 10 Predefined Themes */}
              <div className="theme-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div>
                    <span className="modal-item-title" style={{ display: 'block' }}>Theme & Appearance</span>
                    <span className="modal-item-desc">Choose from 10 handcrafted light and dark modes</span>
                  </div>
                  <div className="theme-filter-row">
                    {[
                      { id: 'all', label: 'All Themes (10)' },
                      { id: 'dark', label: '🌙 Dark (5)' },
                      { id: 'light', label: '☀️ Light (5)' },
                    ].map((f) => (
                      <button
                        key={f.id}
                        type="button"
                        className={`theme-filter-btn ${themeModeFilter === f.id ? 'active' : ''}`}
                        onClick={() => setThemeModeFilter(f.id)}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="theme-grid">
                  {THEMES.filter((t) => themeModeFilter === 'all' || t.mode === themeModeFilter).map((thm) => {
                    const isActive = thm.id === currentThemeId;
                    return (
                      <div
                        key={thm.id}
                        className={`theme-card ${isActive ? 'active' : ''}`}
                        onClick={() => setCurrentThemeId(thm.id)}
                      >
                        <div className="theme-card-top">
                          <div className="theme-swatches">
                            {thm.preview.map((clr, idx) => (
                              <span key={idx} className="theme-swatch" style={{ background: clr }} />
                            ))}
                          </div>
                          <span className="theme-mode-badge">{thm.mode} · {thm.tag}</span>
                        </div>
                        <div className="theme-card-title">
                          <span>{thm.name}</span>
                          {isActive && <span className="theme-active-check">✓ Active</span>}
                        </div>
                        <span className="theme-card-desc">{thm.description}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. Response Language */}
              <div>
                <span className="modal-item-title" style={{ display: 'block', marginBottom: '4px' }}>Response Language</span>
                <span className="modal-item-desc" style={{ display: 'block', marginBottom: '10px' }}>
                  Language used by the tutor for explanations, summaries, and textbook references.
                </span>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {[
                    { id: 'English', label: '🇬🇧 English' },
                    { id: 'Hindi', label: '🇮🇳 Hindi (हिन्दी)' },
                  ].map((lng) => (
                    <button
                      key={lng.id}
                      type="button"
                      className={`pill-select ${language === lng.id ? 'active' : ''}`}
                      onClick={() => setLanguage(lng.id)}
                    >
                      {lng.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 3. Target Class & Grade */}
              <div>
                <span className="modal-item-title" style={{ display: 'block', marginBottom: '8px' }}>Target Class & Grade</span>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {[5, 10].map((gr) => (
                    <button
                      key={gr}
                      type="button"
                      className={`pill-select ${selectedGrade === gr ? 'active' : ''}`}
                      onClick={() => setSelectedGrade(gr)}
                    >
                      Class {gr}
                    </button>
                  ))}
                </div>
              </div>

              {/* 4. Tutor Persona */}
              <div>
                <span className="modal-item-title" style={{ display: 'block', marginBottom: '8px' }}>Tutor Persona</span>
                <div className="modal-grid">
                  <div
                    className={`modal-card-item ${tutorPersona === 'friendly' ? 'active' : ''}`}
                    onClick={() => setTutorPersona('friendly')}
                  >
                    <span className="modal-item-badge">Encouraging</span>
                    <span className="modal-item-title">Friendly NCERT Tutor</span>
                    <span className="modal-item-desc">Patient, encouraging, explains concepts with relatable analogies.</span>
                  </div>
                  <div
                    className={`modal-card-item ${tutorPersona === 'exam' ? 'active' : ''}`}
                    onClick={() => setTutorPersona('exam')}
                  >
                    <span className="modal-item-badge">Exam-Focused</span>
                    <span className="modal-item-title">Board Exam Coach</span>
                    <span className="modal-item-desc">Focused on marks, scoring definitions, and textbook keywords.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* 5. Notebooks Modal */}
      {activeModal === 'notebooks' && (
        <div className="gemini-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="gemini-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="gemini-modal-header">
              <div className="gemini-modal-title">
                <NotebookIcon size={20} />
                <span>My Study Notebooks</span>
              </div>
              <button className="gemini-modal-close" onClick={() => setActiveModal(null)} type="button">✕</button>
            </div>
            <div className="gemini-modal-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="modal-item-desc">Study notes and saved summaries:</span>
                <button
                  type="button"
                  className="pill-select active"
                  onClick={handleNewNotebook}
                  style={{ cursor: 'pointer' }}
                >
                  + New notebook
                </button>
              </div>
              <div className="modal-grid">
                {notebooks.map((nb) => (
                  <div key={nb.id} className="modal-card-item">
                    <span className="modal-item-badge">Notebook</span>
                    <span className="modal-item-title">{nb.title}</span>
                    <span className="modal-item-desc">Created {new Date(nb.createdAt).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. Parental Authentication Modal */}
      <ParentalAuthModal
        isOpen={parentAuthOpen}
        onClose={() => setParentAuthOpen(false)}
        onSuccess={handleParentAuthSuccess}
      />

      {/* 7. Parental Portal Management Modal */}
      <ParentalPortalModal
        isOpen={parentPortalOpen}
        onClose={() => setParentPortalOpen(false)}
        token={parentSessionToken}
        onLogout={handleParentLogout}
        initialTab={parentPortalTab}
        onBookUploaded={reloadSubjects}
      />

      {/* 8. Institution Administration & Management Modal (Org Admin) */}
      <InstitutionAdminModal
        isOpen={instAdminModalOpen}
        onClose={() => setInstAdminModalOpen(false)}
        token={isValidJwt(authToken) ? authToken : getStoredToken()}
        currentUser={studentUser}
        onInstitutionUpdated={() => {
          refreshUserProfile();
          reloadSubjects();
        }}
      />

      {/* 9. Join Institution Modal (Invite Code / Link Acceptance) */}
      <JoinInstitutionModal
        isOpen={joinInstModalOpen}
        onClose={() => {
          setJoinInstModalOpen(false);
          setUrlInviteToken('');
        }}
        token={isValidJwt(authToken) ? authToken : getStoredToken()}
        initialInviteToken={urlInviteToken}
        onJoinedSuccess={handleJoinedInstitutionSuccess}
      />

      {/* 10. Claude-Style Onboarding Tutorial Modal */}
      <TutorialModal
        isOpen={tutorialModalOpen}
        onClose={() => setTutorialModalOpen(false)}
        currentUser={studentUser}
        onSelectPrompt={(text) => {
          setQuestion(text);
          setTimeout(() => {
            textareaRef.current?.focus();
          }, 100);
        }}
      />
    </div>
  );
}
