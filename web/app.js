/**
 * Serendipity — Card reader app
 *
 * Client-side shuffle with skip weights, saves, and lazy shard loading.
 * All state persisted to localStorage.
 */

(function() {
    'use strict';

    // --- State ---
    const state = {
        manifest: null,
        loadedShards: new Map(),    // shard name -> cards[]
        cardPool: [],               // available cards for current session
        currentCard: null,
        cardHistory: [],            // history of viewed cards for going back
        historyIndex: -1,           // current position in history (-1 = not in history)
        seenIds: new Set(),
        savedCards: [],             // full card objects
        skipWeights: {},            // author/topic -> weight (0-1, lower = less likely)
        topicFilters: {},           // topic -> enabled
        settings: {
            fontSize: 18,
            lightMode: false
        }
    };

    // --- Constants ---
    const STORAGE_KEYS = {
        SEEN: 'serendipity_seen',
        SAVED: 'serendipity_saved',
        SKIP_WEIGHTS: 'serendipity_skip_weights',
        TOPIC_FILTERS: 'serendipity_topic_filters',
        SETTINGS: 'serendipity_settings',
        WELCOMED: 'serendipity_welcomed'
    };

    const SKIP_WEIGHT_DECAY = 0.1;      // How much each skip reduces weight
    const SKIP_WEIGHT_RECOVERY = 0.02;  // Weight recovery per card seen
    const MIN_POOL_SIZE = 20;           // Load more shards when pool drops below

    // --- DOM refs ---
    const $ = (sel) => document.querySelector(sel);
    const card = $('#card');
    const cardHeader = $('#cardHeader');
    const cardText = $('#cardText');
    const cardMeta = $('#cardMeta');
    const emptyState = $('#emptyState');
    const menuPanel = $('#menuPanel');
    const savedPanel = $('#savedPanel');
    const overlay = $('#overlay');
    const topicFiltersContainer = $('#topicFilters');
    const savedList = $('#savedList');

    // --- Storage ---
    function loadState() {
        try {
            const seen = localStorage.getItem(STORAGE_KEYS.SEEN);
            if (seen) state.seenIds = new Set(JSON.parse(seen));

            const saved = localStorage.getItem(STORAGE_KEYS.SAVED);
            if (saved) state.savedCards = JSON.parse(saved);

            const weights = localStorage.getItem(STORAGE_KEYS.SKIP_WEIGHTS);
            if (weights) state.skipWeights = JSON.parse(weights);

            const filters = localStorage.getItem(STORAGE_KEYS.TOPIC_FILTERS);
            if (filters) state.topicFilters = JSON.parse(filters);

            const settings = localStorage.getItem(STORAGE_KEYS.SETTINGS);
            if (settings) state.settings = { ...state.settings, ...JSON.parse(settings) };
        } catch (e) {
            console.warn('Failed to load state:', e);
        }
    }

    function saveState() {
        try {
            localStorage.setItem(STORAGE_KEYS.SEEN, JSON.stringify([...state.seenIds]));
            localStorage.setItem(STORAGE_KEYS.SAVED, JSON.stringify(state.savedCards));
            localStorage.setItem(STORAGE_KEYS.SKIP_WEIGHTS, JSON.stringify(state.skipWeights));
            localStorage.setItem(STORAGE_KEYS.TOPIC_FILTERS, JSON.stringify(state.topicFilters));
            localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(state.settings));
        } catch (e) {
            console.warn('Failed to save state:', e);
        }
    }

    // --- Manifest & Shards ---
    async function loadManifest() {
        const res = await fetch('data/manifest.json');
        if (!res.ok) throw new Error('Failed to load manifest');
        state.manifest = await res.json();

        // Initialize topic filters
        for (const topic of state.manifest.topics) {
            if (!(topic in state.topicFilters)) {
                state.topicFilters[topic] = true;
            }
        }
    }

    async function loadShard(shardInfo) {
        if (state.loadedShards.has(shardInfo.file)) return;

        const res = await fetch(`data/${shardInfo.file}`);
        if (!res.ok) throw new Error(`Failed to load shard: ${shardInfo.file}`);
        const cards = await res.json();

        state.loadedShards.set(shardInfo.file, cards);

        // Add eligible cards to pool
        for (const card of cards) {
            if (!state.seenIds.has(card.id) && isCardEligible(card)) {
                state.cardPool.push(card);
            }
        }
    }

    async function ensurePoolSize() {
        if (state.cardPool.length >= MIN_POOL_SIZE) return;
        if (!state.manifest) return;

        // Find unloaded shards with enabled topics
        const enabledTopics = new Set(
            Object.entries(state.topicFilters)
                .filter(([_, enabled]) => enabled)
                .map(([topic, _]) => topic)
        );

        for (const shard of state.manifest.shards) {
            if (state.loadedShards.has(shard.file)) continue;
            if (!shard.topics.some(t => enabledTopics.has(t))) continue;

            await loadShard(shard);
            if (state.cardPool.length >= MIN_POOL_SIZE) break;
        }
    }

    // --- Card selection ---
    function isCardEligible(card) {
        // Check topic filter
        if (!state.topicFilters[card.topic]) return false;
        return true;
    }

    function getCardWeight(card) {
        let weight = 1.0;

        // Heavily prefer standalone content (works without context)
        if (card.standalone) {
            weight *= 3.0;
        }

        // Prefer openings for linear narratives (natural hooks)
        if (card.content_type === 'opening') {
            weight *= 2.0;
        }

        // Sections from standalone texts are gold
        if (card.content_type === 'section') {
            weight *= 2.5;
        }

        // Apply author weight
        const authorKey = `author:${card.author}`;
        if (authorKey in state.skipWeights) {
            weight *= state.skipWeights[authorKey];
        }

        // Apply topic weight
        const topicKey = `topic:${card.topic}`;
        if (topicKey in state.skipWeights) {
            weight *= state.skipWeights[topicKey];
        }

        return Math.max(0.05, weight);  // Floor to prevent total exclusion
    }

    function selectNextCard() {
        // Filter eligible cards
        let eligible = state.cardPool.filter(c =>
            !state.seenIds.has(c.id) && isCardEligible(c)
        );

        if (eligible.length === 0) return null;

        // Avoid same book as current card (variety)
        if (state.currentCard && eligible.length > 1) {
            const currentBookId = state.currentCard.book_id;
            const otherBooks = eligible.filter(c => c.book_id !== currentBookId);
            // Only switch if we have other options
            if (otherBooks.length > 0) {
                eligible = otherBooks;
            }
        }

        // Weighted random selection
        const totalWeight = eligible.reduce((sum, c) => sum + getCardWeight(c), 0);
        let random = Math.random() * totalWeight;

        for (const card of eligible) {
            random -= getCardWeight(card);
            if (random <= 0) return card;
        }

        return eligible[eligible.length - 1];
    }

    // --- Display ---
    function renderCard(cardData) {
        if (!cardData) {
            card.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        card.classList.remove('hidden');

        // Build header
        cardHeader.innerHTML = '';

        // Title line
        const titleDiv = document.createElement('div');
        titleDiv.className = 'card-header-title';
        titleDiv.textContent = `${cardData.source_title} — ${cardData.author}`;
        cardHeader.appendChild(titleDiv);

        // Section info (if available)
        if (cardData.section) {
            const sectionDiv = document.createElement('div');
            sectionDiv.className = 'card-header-section';
            sectionDiv.textContent = `Section ${cardData.section}`;
            cardHeader.appendChild(sectionDiv);
        }

        // Era and content type badge
        const metaLine = document.createElement('div');
        metaLine.className = 'card-header-meta';

        if (cardData.era) {
            const eraSpan = document.createElement('span');
            eraSpan.className = 'card-header-era';
            eraSpan.textContent = cardData.era;
            metaLine.appendChild(eraSpan);
        }

        // Show content type badge for context
        if (cardData.content_type === 'opening') {
            const badge = document.createElement('span');
            badge.className = 'card-badge opening';
            badge.textContent = 'Opening';
            metaLine.appendChild(badge);
        }

        if (metaLine.children.length > 0) {
            cardHeader.appendChild(metaLine);
        }

        // Set text using textContent (XSS safe)
        cardText.textContent = cardData.text;

        // Build meta with description and link
        cardMeta.innerHTML = '';

        // Description
        if (cardData.description) {
            const descDiv = document.createElement('div');
            descDiv.className = 'card-meta-desc';
            descDiv.textContent = cardData.description;
            cardMeta.appendChild(descDiv);
        }

        // Source link
        const url = cardData.source_url;
        const isValidUrl = url && url.startsWith('https://');

        if (isValidUrl) {
            const linkDiv = document.createElement('div');
            linkDiv.className = 'card-meta-link';
            const link = document.createElement('a');
            link.href = url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = 'Read full text →';
            linkDiv.appendChild(link);
            cardMeta.appendChild(linkDiv);
        }

        // Animate in
        card.classList.remove('exit-up', 'exit-down', 'swiping-up', 'swiping-down');
        card.classList.add('entering');
        setTimeout(() => card.classList.remove('entering'), 250);
    }

    async function showNextCard() {
        await ensurePoolSize();

        // If we're in history and moving forward, go to next in history
        if (state.historyIndex >= 0 && state.historyIndex < state.cardHistory.length - 1) {
            state.historyIndex++;
            state.currentCard = state.cardHistory[state.historyIndex];
            renderCard(state.currentCard);
            return;
        }

        // Otherwise get a new card
        state.historyIndex = -1;  // Reset history navigation
        state.currentCard = selectNextCard();

        // Add to history
        if (state.currentCard) {
            state.cardHistory.push(state.currentCard);
            // Keep history reasonable size
            if (state.cardHistory.length > 50) {
                state.cardHistory.shift();
            }
        }

        renderCard(state.currentCard);
    }

    function showPreviousCard() {
        if (state.cardHistory.length === 0) return;

        // If not in history mode, start from end
        if (state.historyIndex < 0) {
            state.historyIndex = state.cardHistory.length - 1;
        }

        // Go back one
        if (state.historyIndex > 0) {
            state.historyIndex--;
            state.currentCard = state.cardHistory[state.historyIndex];
            renderCard(state.currentCard);
        }
    }

    // --- Actions ---
    function dislikeCard() {
        if (!state.currentCard) return;

        const cardData = state.currentCard;

        // Mark seen
        state.seenIds.add(cardData.id);

        // Update skip weights (penalize author/topic)
        const authorKey = `author:${cardData.author}`;
        const topicKey = `topic:${cardData.topic}`;

        state.skipWeights[authorKey] = (state.skipWeights[authorKey] || 1.0) - SKIP_WEIGHT_DECAY;
        state.skipWeights[topicKey] = (state.skipWeights[topicKey] || 1.0) - SKIP_WEIGHT_DECAY;

        // Clamp
        state.skipWeights[authorKey] = Math.max(0.1, state.skipWeights[authorKey]);
        state.skipWeights[topicKey] = Math.max(0.1, state.skipWeights[topicKey]);

        // Remove from pool
        const idx = state.cardPool.indexOf(cardData);
        if (idx > -1) state.cardPool.splice(idx, 1);

        saveState();

        // Animate and show next
        card.classList.add('exit-up');
        setTimeout(() => showNextCard(), 300);
    }

    function nextCard() {
        if (!state.currentCard) return;

        const cardData = state.currentCard;

        // Mark seen but NO weight penalty
        state.seenIds.add(cardData.id);

        // Remove from pool
        const idx = state.cardPool.indexOf(cardData);
        if (idx > -1) state.cardPool.splice(idx, 1);

        saveState();

        // Animate up and show next
        card.classList.add('exit-up');
        setTimeout(() => showNextCard(), 300);
    }

    function saveCard() {
        if (!state.currentCard) return;

        const cardData = state.currentCard;

        // Mark seen
        state.seenIds.add(cardData.id);

        // Add to saved if not already
        if (!state.savedCards.find(c => c.id === cardData.id)) {
            state.savedCards.unshift(cardData);
        }

        // Recover weights slightly (positive signal)
        const authorKey = `author:${cardData.author}`;
        const topicKey = `topic:${cardData.topic}`;

        state.skipWeights[authorKey] = Math.min(1.0, (state.skipWeights[authorKey] || 1.0) + SKIP_WEIGHT_RECOVERY);
        state.skipWeights[topicKey] = Math.min(1.0, (state.skipWeights[topicKey] || 1.0) + SKIP_WEIGHT_RECOVERY);

        // Remove from pool
        const idx = state.cardPool.indexOf(cardData);
        if (idx > -1) state.cardPool.splice(idx, 1);

        saveState();

        // Animate down (positive) and show next
        card.classList.add('exit-down');
        setTimeout(() => showNextCard(), 300);
    }

    // --- Panels ---
    function openMenu() {
        menuPanel.classList.remove('hidden');
        overlay.classList.remove('hidden');
        renderTopicFilters();
    }

    function closeMenu() {
        menuPanel.classList.add('hidden');
        overlay.classList.add('hidden');
    }

    function openSaved() {
        savedPanel.classList.remove('hidden');
        overlay.classList.remove('hidden');
        renderSavedList();
    }

    function closeSaved() {
        savedPanel.classList.add('hidden');
        overlay.classList.add('hidden');
    }

    function renderTopicFilters() {
        topicFiltersContainer.innerHTML = '';

        if (!state.manifest) return;

        for (const topic of state.manifest.topics.sort()) {
            const count = state.manifest.shards
                .filter(s => s.topics.includes(topic))
                .reduce((sum, s) => sum + s.cards, 0);

            const div = document.createElement('div');
            div.className = 'topic-filter';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `topic-${topic}`;
            checkbox.checked = state.topicFilters[topic] !== false;
            checkbox.addEventListener('change', () => {
                state.topicFilters[topic] = checkbox.checked;
                saveState();
                rebuildPool();
            });

            const label = document.createElement('label');
            label.htmlFor = `topic-${topic}`;
            label.textContent = topic.charAt(0).toUpperCase() + topic.slice(1);

            const countSpan = document.createElement('span');
            countSpan.textContent = count;

            div.appendChild(checkbox);
            div.appendChild(label);
            div.appendChild(countSpan);
            topicFiltersContainer.appendChild(div);
        }
    }

    function renderSavedList() {
        savedList.innerHTML = '';

        if (state.savedCards.length === 0) {
            savedList.innerHTML = '<div class="saved-empty">No saved cards yet</div>';
            return;
        }

        for (const card of state.savedCards) {
            const div = document.createElement('div');
            div.className = 'saved-card';

            const text = document.createElement('div');
            text.className = 'saved-card-text';
            text.textContent = card.text.slice(0, 200) + (card.text.length > 200 ? '...' : '');

            const meta = document.createElement('div');
            meta.className = 'saved-card-meta';

            if (card.source_url && card.source_url.startsWith('https://')) {
                const link = document.createElement('a');
                link.href = card.source_url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = card.source_title;
                meta.appendChild(link);
                meta.appendChild(document.createTextNode(` — ${card.author}`));
            } else {
                meta.textContent = `${card.source_title} — ${card.author}`;
            }

            div.appendChild(text);
            div.appendChild(meta);
            savedList.appendChild(div);
        }
    }

    function rebuildPool() {
        // Rebuild pool from loaded shards with current filters
        state.cardPool = [];
        for (const [_, cards] of state.loadedShards) {
            for (const card of cards) {
                if (!state.seenIds.has(card.id) && isCardEligible(card)) {
                    state.cardPool.push(card);
                }
            }
        }
        showNextCard();
    }

    // --- Settings ---
    function applySettings() {
        document.documentElement.style.setProperty('--font-size', `${state.settings.fontSize}px`);

        if (state.settings.lightMode) {
            document.body.classList.add('light-mode');
        } else {
            document.body.classList.remove('light-mode');
        }
    }

    // --- Export/Import ---
    function exportSaves() {
        const data = {
            savedCards: state.savedCards,
            exportDate: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `serendipity-saves-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();

        URL.revokeObjectURL(url);
    }

    function importSaves(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                if (data.savedCards && Array.isArray(data.savedCards)) {
                    // Merge, avoiding duplicates
                    const existingIds = new Set(state.savedCards.map(c => c.id));
                    for (const card of data.savedCards) {
                        if (!existingIds.has(card.id)) {
                            state.savedCards.push(card);
                        }
                    }
                    saveState();
                    alert(`Imported ${data.savedCards.length} cards`);
                }
            } catch (err) {
                alert('Invalid file format');
            }
        };
        reader.readAsText(file);
    }

    // --- Touch/swipe (vertical TikTok-style) ---
    let touchStartX = 0;
    let touchStartY = 0;
    let isSwiping = false;

    function handleTouchStart(e) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        isSwiping = false;
    }

    function handleTouchMove(e) {
        const dx = e.touches[0].clientX - touchStartX;
        const dy = e.touches[0].clientY - touchStartY;

        // Only track vertical swipes
        if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 20) {
            isSwiping = true;
            card.classList.remove('swiping-up', 'swiping-down');
            if (dy < 0) {
                card.classList.add('swiping-up');
            } else {
                card.classList.add('swiping-down');
            }
        }
    }

    function handleTouchEnd(e) {
        const dy = e.changedTouches[0].clientY - touchStartY;

        card.classList.remove('swiping-up', 'swiping-down');

        if (isSwiping && Math.abs(dy) > 80) {
            if (dy < 0) {
                // Swipe up = next card
                nextCard();
            } else {
                // Swipe down = go back to previous card
                showPreviousCard();
            }
        }

        isSwiping = false;
    }

    // --- Event listeners ---
    function bindEvents() {
        // Buttons
        $('#dislikeBtn').addEventListener('click', dislikeCard);
        $('#nextBtn').addEventListener('click', nextCard);
        $('#saveBtn').addEventListener('click', saveCard);
        $('#menuBtn').addEventListener('click', openMenu);
        $('#savedBtn').addEventListener('click', openSaved);
        $('#closeMenuBtn').addEventListener('click', closeMenu);
        $('#closeSavedBtn').addEventListener('click', closeSaved);
        overlay.addEventListener('click', () => {
            closeMenu();
            closeSaved();
        });

        // Reset filters
        $('#resetFiltersBtn').addEventListener('click', () => {
            for (const topic in state.topicFilters) {
                state.topicFilters[topic] = true;
            }
            state.skipWeights = {};
            saveState();
            rebuildPool();
        });

        // Settings
        $('#fontSizeRange').addEventListener('input', (e) => {
            state.settings.fontSize = parseInt(e.target.value, 10);
            applySettings();
            saveState();
        });

        $('#lightModeToggle').addEventListener('change', (e) => {
            state.settings.lightMode = e.target.checked;
            applySettings();
            saveState();
        });

        // Export/Import
        $('#exportBtn').addEventListener('click', exportSaves);
        $('#importBtn').addEventListener('click', () => $('#importFile').click());
        $('#importFile').addEventListener('change', (e) => {
            if (e.target.files[0]) {
                importSaves(e.target.files[0]);
                e.target.value = '';
            }
        });

        // Welcome
        $('#welcomeBtn').addEventListener('click', dismissWelcome);

        // Touch handling on entire screen (TikTok-style)
        document.body.addEventListener('touchstart', handleTouchStart, { passive: true });
        document.body.addEventListener('touchmove', handleTouchMove, { passive: true });
        document.body.addEventListener('touchend', handleTouchEnd);

        // Tap on card area = next (simple, use buttons for other actions)
        $('#cardContainer').addEventListener('click', (e) => {
            if (isSwiping) return;
            // Don't trigger if clicking on a link or button
            if (e.target.closest('a, button')) return;
            nextCard();
        });

        // Keyboard (vertical navigation - down = next, up = previous)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown' || e.key === ' ' || e.key === 'j') {
                e.preventDefault();
                nextCard();
            }
            if (e.key === 'ArrowUp' || e.key === 'k') {
                e.preventDefault();
                showPreviousCard();
            }
            if (e.key === 'x') dislikeCard();
            if (e.key === 's' || e.key === 'l') saveCard();
            if (e.key === 'Escape') {
                closeMenu();
                closeSaved();
            }
        });

        // Mouse wheel scrolling (TikTok desktop style)
        let wheelTimeout = null;
        let wheelAccumulator = 0;
        const WHEEL_THRESHOLD = 50;

        document.addEventListener('wheel', (e) => {
            // Ignore if scrolling inside the card text
            if (card.scrollHeight > card.clientHeight) {
                const atTop = card.scrollTop === 0;
                const atBottom = card.scrollTop + card.clientHeight >= card.scrollHeight - 5;

                // Allow natural scroll within card unless at edges
                if ((e.deltaY < 0 && !atTop) || (e.deltaY > 0 && !atBottom)) {
                    return;
                }
            }

            e.preventDefault();
            wheelAccumulator += e.deltaY;

            // Debounce and threshold to prevent accidental triggers
            clearTimeout(wheelTimeout);
            wheelTimeout = setTimeout(() => {
                if (Math.abs(wheelAccumulator) > WHEEL_THRESHOLD) {
                    if (wheelAccumulator > 0) {
                        nextCard();  // Scroll down = next
                    } else {
                        showPreviousCard();  // Scroll up = previous
                    }
                }
                wheelAccumulator = 0;
            }, 50);
        }, { passive: false });
    }

    // --- Welcome ---
    function showWelcome() {
        $('#welcome').classList.remove('hidden');
    }

    function dismissWelcome() {
        $('#welcome').classList.add('hidden');
        localStorage.setItem(STORAGE_KEYS.WELCOMED, 'true');
    }

    // --- Init ---
    async function init() {
        loadState();
        applySettings();

        // Sync UI with state
        $('#fontSizeRange').value = state.settings.fontSize;
        $('#lightModeToggle').checked = state.settings.lightMode;

        bindEvents();

        // Show welcome on first visit
        if (!localStorage.getItem(STORAGE_KEYS.WELCOMED)) {
            showWelcome();
        }

        try {
            await loadManifest();
            await showNextCard();
        } catch (e) {
            console.error('Init failed:', e);
            cardText.textContent = 'Failed to load cards. Make sure data files exist.';
        }

        // Register service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('sw.js').catch(console.warn);
        }
    }

    init();
})();
