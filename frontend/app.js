(function () {
  const tabs = document.querySelectorAll('.tab');
  const chatContainers = document.querySelectorAll('.chat-messages');
  const messageInput = document.getElementById('message-input');
  let activeTab = 'world';
  let evtSource = null; // one SSE per tab; closed when switching
  let lastSentHumanContent = null;
  let lastSentHumanTime = 0;
  let audioContext = null;

  // Avatar colors for different personas
  const avatarColors = {
    'Gaurav': '#D4A574',
    'Anagha': '#C49A6C',
    'Kanishkha': '#B8935F',
    'Nirbhay': '#A67C52',
    'Human': '#6B8E23',
  };

  const avatarInitials = {
    'Gaurav': 'G',
    'Anagha': 'A',
    'Kanishkha': 'K',
    'Nirbhay': 'N',
    'Human': 'H',
  };

  function get(path) {
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    });
  }

  function escapeHtml(s) {
    if (s == null) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    try {
      const date = new Date(timestamp);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${month}-${day}-${year} ${hours}:${minutes}`;
    } catch (e) {
      return timestamp;
    }
  }

  function getAvatarColor(role) {
    return avatarColors[role] || '#D4A574';
  }

  function getAvatarInitial(role) {
    return avatarInitials[role] || role.charAt(0).toUpperCase();
  }

  function getFlagEmoji(role) {
    // Simple mapping - can be enhanced
    const flagMap = {
      'Gaurav': '🇺🇸',
      'Anagha': '🇺🇸',
      'Kanishkha': '🇺🇸',
      'Nirbhay': '🇺🇸',
    };
    return flagMap[role] || '🌍';
  }

  const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '👏', '🔥', '🎉', '👎'];
  const REACTIONS_STORAGE_KEY = 'chat-message-reactions';

  function getMessageId(role, content, timestamp) {
    const str = (role || '') + '|' + (content || '') + '|' + (timestamp || '');
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = ((h << 5) - h) + str.charCodeAt(i);
      h = h & h;
    }
    return 'msg_' + Math.abs(h).toString(36);
  }

  function getStoredReactions() {
    try {
      const raw = localStorage.getItem(REACTIONS_STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function setStoredReactions(data) {
    try {
      localStorage.setItem(REACTIONS_STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function addReaction(messageId, emoji) {
    const data = getStoredReactions();
    if (!data[messageId]) data[messageId] = {};
    data[messageId][emoji] = (data[messageId][emoji] || 0) + 1;
    setStoredReactions(data);
  }

  function getReactionsForMessage(messageId) {
    const data = getStoredReactions();
    return data[messageId] || {};
  }

  function renderReactions(messageId, containerEl) {
    const reactions = getReactionsForMessage(messageId);
    const keys = Object.keys(reactions).filter(function (k) { return reactions[k] > 0; });
    containerEl.innerHTML = '';
    keys.forEach(function (emoji) {
      const count = reactions[emoji];
      const span = document.createElement('span');
      span.className = 'message-reaction';
      span.textContent = emoji + (count > 1 ? ' ' + count : '');
      span.title = 'Reaction: ' + emoji;
      containerEl.appendChild(span);
    });
  }

  function openReactionPicker(messageId, bubbleWrapper, role, content, timestamp) {
    // Close any existing picker
    const existing = document.querySelector('.emoji-picker-open');
    if (existing) existing.remove();

    const picker = document.createElement('div');
    picker.className = 'emoji-picker emoji-picker-open';
    REACTION_EMOJIS.forEach(function (emoji) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'emoji-picker-btn';
      btn.textContent = emoji;
      btn.title = 'Add reaction';
      btn.addEventListener('click', function () {
        addReaction(messageId, emoji);
        renderReactions(messageId, bubbleWrapper.querySelector('.message-reactions'));
        picker.remove();
      });
      picker.appendChild(btn);
    });

    document.body.appendChild(picker);
    var rect = bubbleWrapper.getBoundingClientRect();
    var pickerW = picker.offsetWidth;
    var pickerH = picker.offsetHeight;
    var left = rect.right - pickerW;
    if (left < 8) left = 8;
    picker.style.left = left + 'px';
    picker.style.top = (rect.top - pickerH - 6) + 'px';

    function closePicker(e) {
      if (picker.parentNode && !picker.contains(e.target) && !bubbleWrapper.contains(e.target)) {
        picker.remove();
        document.removeEventListener('click', closePicker);
      }
    }
    setTimeout(function () {
      document.addEventListener('click', closePicker);
    }, 0);
  }

  function initAudioContext() {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume();
    }
  }

  function playChime() {
    try {
      const enabled = document.getElementById('sound-enabled');
      if (enabled && !enabled.checked) return;
      
      // Initialize/resume audio context
      if (!audioContext) {
        try {
          audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
          console.error('Failed to create audio context:', e);
          return;
        }
      }
      
      if (audioContext.state === 'suspended') {
        audioContext.resume().then(function() {
          playChimeSound();
        }).catch(function(e) {
          console.error('Failed to resume audio context:', e);
        });
        return;
      }
      
      if (audioContext.state === 'running') {
        playChimeSound();
      }
    } catch (e) {
      console.error('Sound error:', e);
    }
  }

  function playChimeSound() {
    if (!audioContext) {
      return;
    }
    
    try {
      // Resume if suspended
      if (audioContext.state === 'suspended') {
        audioContext.resume().then(function() {
          playChimeSound();
        });
        return;
      }
      
      if (audioContext.state !== 'running') {
        return;
      }
      
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();
      osc.connect(gain);
      gain.connect(audioContext.destination);
      osc.frequency.value = 880; // A5 note - pleasant chime
      osc.type = 'sine';
      gain.gain.setValueAtTime(0.2, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
      osc.start(audioContext.currentTime);
      osc.stop(audioContext.currentTime + 0.2);
    } catch (e) {
      console.error('Chime sound error:', e);
    }
  }

  function appendOneMessage(container, role, content, timestamp, playSound) {
    const messageRow = document.createElement('div');
    messageRow.className = 'message-row';

    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'avatar-container';

    const avatarFrame = document.createElement('div');
    avatarFrame.className = 'avatar-frame';

    const avatarImg = document.createElement('div');
    avatarImg.className = 'avatar-img';
    avatarImg.style.background = `linear-gradient(135deg, ${getAvatarColor(role)} 0%, ${getAvatarColor(role)}dd 100%)`;
    avatarImg.textContent = getAvatarInitial(role);

    // Add flag emoji (simplified - using country flags based on name)
    const flagEmoji = getFlagEmoji(role);
    if (flagEmoji) {
      const flagEl = document.createElement('span');
      flagEl.className = 'avatar-flag';
      flagEl.textContent = flagEmoji;
      avatarFrame.appendChild(flagEl);
    }

    // Add level badge
    const levelEl = document.createElement('span');
    levelEl.className = 'avatar-level';
    levelEl.textContent = 'Lv.' + (Math.floor(Math.random() * 50) + 50); // Random level 50-99
    avatarContainer.appendChild(levelEl);

    avatarFrame.appendChild(avatarImg);
    avatarContainer.appendChild(avatarFrame);

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    const messageHeader = document.createElement('div');
    messageHeader.className = 'message-header';
    const ts = formatTimestamp(timestamp);
    messageHeader.innerHTML = `<span class="message-username">${escapeHtml(role)}</span><span class="message-timestamp">${escapeHtml(ts)}</span>`;

    const messageId = getMessageId(role, content, timestamp);
    const bubbleWrapper = document.createElement('div');
    bubbleWrapper.className = 'message-bubble-wrapper';

    const messageBubble = document.createElement('div');
    messageBubble.className = 'message-bubble';
    messageBubble.textContent = escapeHtml(content || '');

    const reactionIconBtn = document.createElement('button');
    reactionIconBtn.type = 'button';
    reactionIconBtn.className = 'message-reaction-icon';
    reactionIconBtn.title = 'Add reaction';
    reactionIconBtn.innerHTML = '😊';
    reactionIconBtn.setAttribute('aria-label', 'Add reaction');
    reactionIconBtn.addEventListener('click', function (e) {
      e.preventDefault();
      openReactionPicker(messageId, bubbleWrapper, role, content, timestamp);
    });

    const reactionsContainer = document.createElement('div');
    reactionsContainer.className = 'message-reactions';
    renderReactions(messageId, reactionsContainer);

    bubbleWrapper.appendChild(messageBubble);
    bubbleWrapper.appendChild(reactionIconBtn);
    bubbleWrapper.appendChild(reactionsContainer);

    messageContent.appendChild(messageHeader);
    messageContent.appendChild(bubbleWrapper);

    messageRow.appendChild(avatarContainer);
    messageRow.appendChild(messageContent);
    container.appendChild(messageRow);
    container.scrollTop = container.scrollHeight;
    if (playSound) playChime();
  }

  function renderAll(container, messages) {
    if (!messages || messages.length === 0) return;
    let lastTimestamp = null;
    messages.forEach(function (m) {
      const timestamp = m.timestamp || new Date().toISOString();
      const date = new Date(timestamp);
      const dateStr = date.toDateString();
      if (lastTimestamp && new Date(lastTimestamp).toDateString() !== dateStr) {
        const divider = document.createElement('div');
        divider.className = 'timestamp-divider';
        divider.textContent = formatTimestamp(timestamp);
        container.appendChild(divider);
      }
      appendOneMessage(container, m.role || m.speaker, m.content || m.text, timestamp, false);
      lastTimestamp = timestamp;
    });
  }

  const CHANNELS_WITH_HISTORY = ['world', 'sports', 'technology', 'human'];
  const EMPTY_MSG_BY_CHANNEL = {
    world: 'Waiting for messages… run.py is writing to conversational_history.txt.',
    sports: 'No messages in Sports yet. Agents will write to sports_convers_history.txt.',
    technology: 'No messages in Technology yet. Agents will write to tech_convers_history.txt.',
    human: 'Type a message below to join the conversation.',
  };

  function setMessageInputEnabled(enabled) {
    if (!messageInput) return;
    messageInput.disabled = !enabled;
    messageInput.placeholder = enabled ? 'Tap to enter...' : 'Select Human tab to type a message';
  }

  function switchTab(tabName) {
    activeTab = tabName;
    tabs.forEach(function (tab) {
      tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    chatContainers.forEach(function (container) {
      container.classList.toggle('active', container.dataset.tab === tabName);
    });

    setMessageInputEnabled(tabName === 'human');

    const activeContainer = document.getElementById(`chat-messages-${tabName}`);
    if (CHANNELS_WITH_HISTORY.indexOf(tabName) !== -1) {
      loadChannelChat(tabName, activeContainer);
    } else {
      activeContainer.innerHTML = '<p class="empty-msg">No messages in this channel yet.</p>';
    }
  }

  function loadChannelChat(channel, container) {
    container.innerHTML = 'Loading…';
    if (evtSource) {
      evtSource.close();
      evtSource = null;
    }
    get('/api/history?channel=' + encodeURIComponent(channel))
      .then(function (data) {
        const messages = (data && data.messages) || [];
        container.innerHTML = '';
        if (messages.length === 0) {
          container.innerHTML = '<p class="empty-msg">' + (EMPTY_MSG_BY_CHANNEL[channel] || 'No messages yet.') + '</p>';
        } else {
          renderAll(container, messages);
        }
        evtSource = new EventSource('/api/history/stream?channel=' + encodeURIComponent(channel));
        evtSource.onmessage = function (e) {
          const empty = container.querySelector('.empty-msg');
          if (empty) empty.remove();
          try {
            const ev = JSON.parse(e.data);
            if (ev.type === 'message' && (ev.role || ev.content)) {
              // Dedupe: skip if this is our own human message just sent (SSE echo)
              if (channel === 'human' && ev.role === 'Human' && lastSentHumanContent !== null &&
                  ev.content === lastSentHumanContent && (Date.now() - lastSentHumanTime) < 3000) {
                lastSentHumanContent = null;
                return;
              }
              appendOneMessage(container, ev.role, ev.content, ev.timestamp || new Date().toISOString(), true);
            }
          } catch (err) {}
        };
        evtSource.onerror = function () {
          if (evtSource) evtSource.close();
        };
      })
      .catch(function (err) {
        container.innerHTML = '<p class="empty-msg">Error: ' + escapeHtml(err.message) + '</p>';
      });
  }

  // Initialize audio context on any user interaction (required for autoplay policy)
  let audioInitialized = false;
  function initAudioOnInteraction() {
    if (!audioInitialized) {
      initAudioContext();
      audioInitialized = true;
    }
  }
  // Initialize on any click/touch anywhere on the page
  document.addEventListener('click', initAudioOnInteraction, { once: true });
  document.addEventListener('touchstart', initAudioOnInteraction, { once: true });

  // Sound preference: persist in localStorage
  const soundCheckbox = document.getElementById('sound-enabled');
  if (soundCheckbox) {
    const saved = localStorage.getItem('chat-sound-enabled');
    // if (saved !== null) soundCheckbox.checked = saved === 'true';
    soundCheckbox.checked = saved === 'true'; // Will be false by default
    soundCheckbox.addEventListener('change', function () {
      localStorage.setItem('chat-sound-enabled', soundCheckbox.checked);
      // Initialize audio context on first user interaction (toggle click)
      if (soundCheckbox.checked) {
        initAudioOnInteraction();
      }
    });
    // Also initialize when sound toggle is clicked
    soundCheckbox.addEventListener('click', initAudioOnInteraction, { once: true });
  }

  // Tab switching
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      switchTab(tab.dataset.tab);
    });
  });

  // Human tab: send message on Enter or button
  function sendHumanMessage() {
    if (activeTab !== 'human' || !messageInput) return;
    const content = (messageInput.value || '').trim();
    if (!content) return;
    messageInput.value = '';
    lastSentHumanContent = content;
    lastSentHumanTime = Date.now();
    const humanContainer = document.getElementById('chat-messages-human');
    appendOneMessage(humanContainer, 'Human', content, new Date().toISOString(), false);

    fetch('/api/history/human', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content }),
    }).then(function (r) {
      return r.json();
    }).then(function (data) {
      if (!data.ok) {
        console.error('Send failed:', data.error);
      }
    }).catch(function (err) {
      console.error('Send error:', err);
    });
  }

  if (messageInput) {
    messageInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendHumanMessage();
      }
    });
  }

  var sendBtn = document.querySelector('.input-bar .plus-btn');
  if (sendBtn) {
    sendBtn.addEventListener('click', function () {
      if (activeTab === 'human') {
        sendHumanMessage();
      }
    });
  }

  // Hamburger menu / push sidebar toggle
  const hamburgerBtn = document.getElementById('hamburger-btn');
  const sidebarDrawer = document.getElementById('sidebar-drawer');
  const sidebarClose = document.getElementById('sidebar-close');

  function openSidebar() {
    if (sidebarDrawer) sidebarDrawer.classList.add('open');
  }

  function closeSidebar() {
    if (sidebarDrawer) sidebarDrawer.classList.remove('open');
  }

  function toggleSidebar() {
    const isOpen = sidebarDrawer && sidebarDrawer.classList.contains('open');
    if (isOpen) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  if (hamburgerBtn) {
    hamburgerBtn.addEventListener('click', toggleSidebar);
  }
  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  // Initial load: world tab, input disabled until Human tab
  setMessageInputEnabled(false);
  switchTab('world');
})();
