/* Player-scoped adventure board. All game actions are resolved by World. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const tabs = [...document.querySelectorAll('[data-tab]')];
  const numbers = new Intl.NumberFormat('en-US');
  const storage = {
    get(key) { try { return sessionStorage.getItem(key); } catch (_) { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, value); } catch (_) { /* Memory-only sessions work in restricted frames. */ } },
    remove(key) { try { sessionStorage.removeItem(key); } catch (_) { /* No stored credential. */ } },
  };
  let credential = storage.get('wakemu.adventures.session');
  let activeTab = storage.get('wakemu.adventures.tab') || 'board';
  let snapshot = null;
  let lastSignature = '';
  let refreshing = false;
  let expired = false;
  let pollTimer;
  let failures = 0;
  const pending = new Map();
  const zoneExpansion = new Map();
  const apiRoot = location.pathname.replace(/\/player\/?$/, '') + '/player-api';

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }
  function message(text, error = false) {
    $('notice').textContent = text;
    $('notice').classList.toggle('error', error);
    $('notice').hidden = !text;
  }
  function stop(messageText, title = 'Open Adventures again') {
    expired = true;
    credential = null;
    storage.remove('wakemu.adventures.session');
    clearTimeout(pollTimer);
    $('panels').hidden = true;
    $('live').hidden = true;
    $('connection').textContent = '';
    $('fatal').replaceChildren(node('h2', '', title), node('p', '', messageText));
    $('fatal').hidden = false;
  }
  async function api(path, options = {}) {
    const headers = { Accept: 'application/json', ...options.headers };
    if (credential) headers.Authorization = `Bearer ${credential}`;
    if (options.body) headers['Content-Type'] = 'application/json';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(apiRoot + path, { ...options, headers, signal: controller.signal, credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer' });
      let data;
      try { data = await response.json(); } catch (_) { data = {}; }
      if (!response.ok) {
        const error = new Error(typeof data.error === 'string' ? data.error : `Request failed (${response.status}).`);
        error.status = response.status;
        if (response.status === 401) stop('This Adventures link has expired or is no longer available. Run !adventures in the game or ask an administrator for a new link.');
        throw error;
      }
      return data;
    } finally { clearTimeout(timeout); }
  }
  function selectTab(key, focus = false) {
    if (!tabs.some(tab => tab.dataset.tab === key)) key = 'board';
    activeTab = key;
    storage.set('wakemu.adventures.tab', key);
    tabs.forEach(tab => {
      const selected = tab.dataset.tab === key;
      tab.classList.toggle('selected', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      $(`panel-${tab.dataset.tab}`).hidden = !selected;
      if (selected && focus) tab.focus();
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); selectTab(tabs[next].dataset.tab, true); }
    });
  });
  function count(value) { return numbers.format(Number(value) || 0); }
  function progressValue(card) {
    if (typeof card.progress === 'number') return Math.max(0, Math.min(1, card.progress));
    const objectives = card.objectives || [];
    const target = objectives.reduce((sum, item) => sum + (Number(item.target) || 0), 0);
    return target ? Math.min(1, objectives.reduce((sum, item) => sum + Math.min(Number(item.current) || 0, Number(item.target) || 0), 0) / target) : 0;
  }
  function rewardText(reward) {
    if (typeof reward === 'string') return { item: false, text: reward };
    if (!reward || typeof reward !== 'object') return null;
    if (reward.label || reward.name) return { item: reward.kind === 'item' || reward.kind === 'random_item' || reward.aeV === 5, text: reward.label || `${count(reward.quantity ?? reward.ckl?.[1] ?? 1)}× ${reward.name}` };
    if (reward.kind === 'random_item') return { item: true, text: `${count(reward.quantity || 1)}× random ${reward.category || 'reward item'}` };
    if (reward.kind === 'scaled') return { item: true, text: 'Rewards matched to your level' };
    if (reward.kind === 'kamas') return { item: false, text: `${count(reward.quantity ?? reward.amount)} kamas` };
    if (reward.kind === 'xp') return { item: false, text: `${count(reward.quantity ?? reward.amount)} XP` };
    if (reward.aeV === 6 && Array.isArray(reward.ckl)) return { item: false, text: `${count(reward.ckl[0])} XP` };
    if (reward.aeV === 3 && Array.isArray(reward.ckl)) return { item: true, text: reward.emote_name || `Emote #${reward.ckl[0]}` };
    if (reward.aeV === 2 && Array.isArray(reward.ckl)) return { item: true, text: reward.title_name || 'Adventure title' };
    if (reward.aeV === 5 && Array.isArray(reward.ckl)) return { item: true, text: `${count(reward.ckl[1])}× item #${reward.ckl[0]}` };
    // Native reward previews may include a human-readable description from the service.
    if (reward.description) return { item: false, text: reward.description };
    return null;
  }
  function rewardLine(card) {
    const line = node('div', 'reward-line');
    const rewards = (card.rewards || []).map(rewardText).filter(Boolean);
    const ordinary = rewards.filter(reward => !reward.item).map(reward => reward.text);
    const items = rewards.filter(reward => reward.item).map(reward => reward.text);
    if (ordinary.length) line.append(node('span', '', ordinary.join(' · ')));
    if (items.length) line.append(node('span', 'items', items.join(' · ')));
    if (!rewards.length) line.append(node('span', '', card.state === 'completed' ? 'Completed' : 'Progress saved automatically'));
    return line;
  }
  function actionButton(action) {
    const label = (action.label || 'Continue') + (action.cost_kamas ? ` · ${count(action.cost_kamas)} kamas` : '');
    const button = node('button', `action${action.kind === 'travel' || action.kind === 'return' ? ' secondary' : ''}`, label);
    button.type = 'button';
    button.dataset.actionKey = action.key;
    const running = [...pending.values()].some(receipt => receipt.action_key === action.key);
    button.disabled = action.enabled === false || running;
    if (action.enabled === false && action.reason) button.title = action.reason;
    if (running) button.textContent = 'Waiting for World…';
    button.addEventListener('click', () => queueAction(action));
    return button;
  }
  function actionList(actions, recovery = false) {
    const list = node('div', 'card-actions');
    const published = (actions || []).filter(action => typeof action.key === 'string' && (!action.key.startsWith('weekly.') || recovery && ['weekly.return', 'weekly.abandon'].includes(action.key)));
    published.forEach(action => list.append(actionButton(action)));
    const reasons = [...new Set(published.filter(action => action.enabled === false && action.reason).map(action => action.reason))];
    reasons.forEach(reason => list.append(node('p', 'action-reason', reason)));
    return list;
  }
  function objectiveDetails(card) {
    const details = node('div', 'progress-details');
    for (const objective of card.objectives || []) {
      const entry = node('span');
      entry.append(node('strong', '', `${count(objective.current)}/${count(objective.target)}`));
      const label = objective.label || objective.title || objective.name;
      if (label) entry.append(document.createTextNode(` ${label}`));
      details.append(entry);
    }
    return details;
  }
  function cardElement(card, step = null) {
    const article = node('article', `card${card.state === 'completed' ? ' completed' : ''}${card.state === 'locked' ? ' locked' : ''}${step !== null && ['in_progress', 'available'].includes(card.state) ? ' current' : ''}`);
    let content = article;
    if (step !== null) {
      const layout = node('div', 'step-layout');
      layout.append(node('span', 'step-marker', card.state === 'completed' ? '✓' : String(step + 1)));
      content = node('div', 'step-content');
      layout.append(content);
      article.append(layout);
    }
    const top = node('div', 'card-top');
    const names = { daily: 'Daily', weekly: 'Weekly', once: 'Permanent' };
    const stateLabel = card.state === 'completed' ? 'Completed' : card.state === 'locked' ? `Stage ${step === null ? 'locked' : step + 1}` : step !== null ? 'Current mission' : names[card.schedule_type] || card.kind || 'Mission';
    top.append(node('p', 'eyebrow', stateLabel));
    if (typeof card.points === 'number') top.append(node('strong', '', `+${count(card.points)} pts`));
    content.append(top, node('h3', '', card.title), node('p', 'card-description', card.description));
    if (card.state !== 'locked') {
      content.append(objectiveDetails(card));
      const progress = node('progress', 'progress');
      progress.max = 1;
      progress.value = progressValue(card);
      progress.setAttribute('aria-label', `${card.title || 'Mission'} progress`);
      content.append(progress);
    }
    content.append(rewardLine(card));
    if (card.actions && card.actions.length) content.append(actionList(card.actions));
    return article;
  }
  function heading(title, subtitle, eyebrow, tally) {
    const row = node('div', 'panel-heading');
    const text = node('div');
    if (eyebrow) text.append(node('p', 'eyebrow', eyebrow));
    text.append(node('h1', '', title));
    if (subtitle) text.append(node('p', 'lede', subtitle));
    row.append(text);
    if (tally) row.append(node('span', 'count', tally));
    return row;
  }
  function empty(title, text) { const box = node('div', 'empty'); box.append(node('h3', '', title), node('p', '', text)); return box; }
  function cardsSection(container, title, cards, className = '') {
    if (!cards.length) return;
    container.append(node('h2', 'section-label', title));
    const grid = node('div', `grid ${className}`);
    cards.forEach(card => grid.append(cardElement(card)));
    container.append(grid);
  }
  function renderBoard(data) {
    const panel = $('panel-board');
    panel.replaceChildren();
    const hunt = data.hunt;
    const banner = node('div', 'board-banner');
    banner.append(node('div', 'banner-icon', '⌖'));
    const copy = node('div', 'banner-copy');
    const bannerTop = node('div', 'card-top');
    bannerTop.append(node('p', 'eyebrow', 'World hunt'));
    if (hunt && typeof hunt.points === 'number') bannerTop.append(node('strong', 'hunt-points', `+${count(hunt.points)} pts`));
    copy.append(bannerTop, node('h2', '', hunt ? hunt.monster_name : 'The world is quiet'));
    if (hunt) {
      const statusText = { alive: 'Available now', in_fight: 'In combat', defeated: 'Defeated', expired: 'Hunt ended' };
      const details = [hunt.level ? `Level ${count(hunt.level)}` : '', hunt.location || hunt.map_name || (hunt.map_id ? `Map #${hunt.map_id}` : ''), statusText[hunt.status] || ''].filter(Boolean);
      copy.append(node('p', 'hunt-location', details.join(' · ')));
      const fallback = hunt.status === 'in_fight' ? 'A group is fighting this creature now.' : hunt.status === 'alive' ? 'Search this area and defeat the creature in the public world.' : 'This hunt has ended. The next rare creature will appear when players are connected.';
      copy.append(node('p', 'lede', hunt.clue || fallback));
      if (Array.isArray(hunt.rewards) && hunt.rewards.length) copy.append(rewardLine({ rewards: hunt.rewards }));
    } else copy.append(node('p', 'lede', 'The next rare creature will appear when players are connected.'));
    banner.append(copy);
    panel.append(banner);
    const recovery = (data.recovery_actions || []).filter(action => ['weekly.return', 'weekly.abandon'].includes(action.key));
    if (recovery.length) {
      const recoveryBox = node('div', 'recovery');
      recoveryBox.append(node('p', '', 'You are still inside a previous challenge. Leave it to return to the public world.'));
      recoveryBox.append(actionList(recovery.map(action => ({ ...action, label: 'Leave previous challenge' })), true));
      panel.append(recoveryBox);
    }
    const layout = node('div', 'board-layout');
    const primary = node('div');
    const sections = data.sections || {};
    cardsSection(primary, 'Daily challenges', sections.daily || []);
    cardsSection(primary, 'Almanax', sections.almanax || []);
    cardsSection(primary, 'Weekly challenges', sections.weekly || []);
    if (!primary.children.length) primary.append(empty('Your board is clear', 'Your assigned challenges will appear here when they become available.'));
    const aside = node('aside', 'board-sidebar');
    aside.append(node('h2', 'section-title', 'Weekly ranking'));
    if ((data.ranking || []).length) {
      const ranking = node('div', 'ranking');
      for (const entry of data.ranking) {
        const row = node('div', `ranking-row${entry.is_self ? ' self' : ''}`);
        const name = node('span', 'ranking-name', entry.character_name || entry.name || 'Adventurer');
        if (entry.bracket && entry.bracket !== 'all') name.append(node('small', 'ranking-sub', entry.bracket));
        row.append(node('span', 'ranking-position', count(entry.rank)), name, node('span', 'ranking-score', count(entry.points)));
        ranking.append(row);
      }
      aside.append(ranking);
    } else aside.append(empty('The week is yours', 'Complete a weekly challenge to set the first score in your bracket.'));
    const note = node('div', 'ranking-note');
    note.append(node('h3', '', 'Every objective counts'), node('p', '', 'Complete assigned challenges, world hunts and achievements to earn points. The weekly ranking adds the points you earn during the week.'));
    aside.append(note);
    layout.append(primary, aside);
    panel.append(layout);
  }
  function achievementGroup(card) {
    const labels = { dungeons: 'Dungeons', places: 'Places', monsters: 'Monsters', characters: 'Characters', professions: 'Professions', crafting: 'Crafting', gathering: 'Gathering', pvp: 'PvP', combat: 'Combat', account: 'Account achievements', other: 'Other achievements' };
    const key = Object.prototype.hasOwnProperty.call(labels, card.achievement_type) ? card.achievement_type : 'other';
    return { key, name: labels[key] };
  }
  function renderAchievements(data) {
    const panel = $('panel-achievements');
    const cards = data.sections?.achievements || [];
    const completed = cards.filter(card => card.state === 'completed').length;
    panel.replaceChildren(heading('Achievements', 'Explore the world, discover special places and conquer dungeons. Open a category to view its achievements.', 'Permanent account progress', `${count(completed)}/${count(cards.length)} completed`));
    const groups = new Map();
    for (const card of cards) {
      const zone = achievementGroup(card);
      if (!groups.has(zone.key)) groups.set(zone.key, { ...zone, cards: [] });
      groups.get(zone.key).cards.push(card);
    }
    const order = ['dungeons', 'places', 'monsters', 'characters', 'professions', 'crafting', 'gathering', 'pvp', 'combat', 'account', 'other'];
    const orderedGroups = [...groups.values()].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
    for (const [index, group] of orderedGroups.entries()) {
      const area = node('details', 'zone-group');
      area.dataset.zoneKey = group.key;
      area.open = zoneExpansion.has(group.key) ? zoneExpansion.get(group.key) : index === 0;
      zoneExpansion.set(group.key, area.open);
      area.addEventListener('toggle', () => zoneExpansion.set(group.key, area.open));
      const summary = node('summary', 'zone-summary');
      const completedInArea = group.cards.filter(card => card.state === 'completed').length;
      summary.append(node('span', 'zone-name', group.name), node('span', 'zone-count', `${count(completedInArea)}/${count(group.cards.length)} completed`));
      const grid = node('div', 'grid achievement-grid');
      group.cards.forEach(card => grid.append(cardElement(card)));
      area.append(summary, grid);
      panel.append(area);
    }
    if (!groups.size) panel.append(empty('A world to discover', 'Achievements will appear here when they are published.'));
  }
  function renderFirstSteps(data) {
    const panel = $('panel-first_steps');
    const cards = data.sections?.first_steps || [];
    const completed = cards.filter(card => card.state === 'completed').length;
    panel.replaceChildren(heading('Your first great adventure', 'Follow the missions in order. Each stage opens the next step and helps you discover the world.', 'First steps', `${completed}/${cards.length}`));
    const grid = node('div', 'grid first-steps-grid');
    cards.forEach((card, index) => grid.append(cardElement(card, index)));
    panel.append(cards.length ? grid : empty('Your story starts here', 'The new-player route will appear here when it is available.'));
  }
  function pvpPerson(person, winner) {
    const box = node('div', 'pvp-person');
    box.append(node('h3', '', person?.name || 'Adventurer'), node('p', '', `Level ${count(person?.level)}`));
    if (winner && winner.account_id === person?.account_id) box.append(node('p', 'eyebrow', 'Winner'));
    return box;
  }
  function updatePvpCountdown(data) {
    const timer = $('pvp-countdown');
    const event = data.pvp?.current;
    if (!timer || !event || !['open', 'in_fight'].includes(event.status)) return;
    const end = new Date(event.ends_at).getTime();
    if (!Number.isFinite(end)) { timer.textContent = ''; return; }
    const seconds = Math.max(0, Math.ceil((end - Date.now()) / 1000));
    timer.textContent = seconds ? `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s remaining` : 'Awaiting the final result';
  }
  function renderPvp(data) {
    const panel = $('panel-pvp');
    panel.replaceChildren(heading('PvP', 'An hourly encounter between two connected accounts. Meet your opponent or watch the duel as it happens.'));
    const event = data.pvp?.current;
    if (event) {
      const match = node('section', 'pvp-event');
      match.dataset.status = event.status;
      const top = node('div', 'pvp-event-header');
      const text = node('div');
      const titles = { open: 'The challenge is open', in_fight: 'The duel is underway', completed: 'The duel is complete', expired: 'The challenge has ended' };
      text.append(node('p', 'eyebrow', 'Hourly challenge'), node('h2', '', titles[event.status] || 'Hourly PvP encounter'));
      top.append(text);
      if (['open', 'in_fight'].includes(event.status)) {
        const timer = node('span', 'pvp-countdown');
        timer.id = 'pvp-countdown';
        timer.setAttribute('role', 'timer');
        top.append(timer);
      }
      match.append(top);
      const people = node('div', 'pvp-participants');
      people.append(pvpPerson(event.participant_one, event.winner), node('span', 'pvp-versus', '⚔'), pvpPerson(event.participant_two, event.winner));
      match.append(people);
      if (event.rewards) {
        const rewards = node('div', 'pvp-rewards');
        for (const [key, label] of [['participation', 'Participation reward'], ['winner', 'Winner reward']]) {
          const preview = event.rewards[key] || [];
          const points = event[`${key}_points`];
          if (!preview.length && typeof points !== 'number') continue;
          const block = node('div');
          block.append(node('p', 'eyebrow', label));
          if (typeof points === 'number') block.append(node('strong', 'hunt-points', `+${count(points)} pts`));
          if (preview.length) block.append(rewardLine({ rewards: preview }));
          rewards.append(block);
        }
        if (rewards.children.length) match.append(rewards);
      }
      const stateCopy = event.status === 'open' ? (event.participating ? `You have been selected${event.opponent_name ? ` to face ${event.opponent_name}` : ''}. Meet your opponent to begin the duel.` : 'These accounts have been selected for this hour. You can watch once their duel begins.') : event.status === 'in_fight' ? 'The fight is live. Spectators can join without entering the competition.' : event.winner ? `${event.winner.name} won this encounter. The final result is recorded below.` : 'This encounter has ended.';
      match.append(node('p', 'pvp-state-copy', stateCopy));
      if (event.actions?.length) match.append(actionList(event.actions));
      panel.append(match);
    } else panel.append(empty('No hourly challenge is active', 'A new encounter can open at the start of an hour when two different accounts are available with compatible levels. The level difference must be within 20% of the lower level.'));
    const feed = node('section', 'feed');
    feed.append(node('h2', 'eyebrow feed-title', 'Public battle history'));
    const history = data.pvp?.history || [];
    for (const entry of history) {
      const row = node('div', 'feed-row');
      const text = node('span');
      const loser = entry.winner?.account_id === entry.participant_one?.account_id ? entry.participant_two : entry.participant_one;
      if (entry.winner) text.append(node('strong', '', entry.winner.name), node('em', '', ' defeated '), node('strong', '', loser?.name || 'Adventurer'));
      else text.append(node('strong', '', entry.participant_one?.name || 'Adventurer'), node('em', '', ' faced '), node('strong', '', entry.participant_two?.name || 'Adventurer'));
      const time = node('time');
      const parsed = new Date(entry.completed_at);
      if (!Number.isNaN(parsed.getTime())) { time.dateTime = parsed.toISOString(); time.textContent = parsed.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); }
      row.append(text, time);
      feed.append(row);
    }
    if (!history.length) feed.append(node('p', 'lede', 'No completed hourly encounters to show.'));
    panel.append(feed);
    updatePvpCountdown(data);
  }
  function displayWeek(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return value || '';
    const date = new Date(`${value}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
    const year = date.getUTCFullYear();
    const first = new Date(Date.UTC(year, 0, 1));
    const week = Math.ceil((((date - first) / 86400000) + 1) / 7);
    return `${year}-W${String(week).padStart(2, '0')}`;
  }
  function render(data) {
    const scrollTop = document.scrollingElement.scrollTop;
    const focused = document.activeElement?.dataset?.actionKey;
    $('week').textContent = displayWeek(data.week_key);
    $('actor').textContent = data.actor ? `${data.actor.name} · Level ${count(data.actor.level)}` : '';
    $('achievement-badge').textContent = count(data.completed_achievements);
    $('achievement-badge').hidden = !data.completed_achievements;
    const availableSteps = (data.sections?.first_steps || []).filter(card => ['available', 'in_progress'].includes(card.state)).length;
    $('first-steps-badge').textContent = count(availableSteps);
    $('first-steps-badge').hidden = !availableSteps;
    renderBoard(data); renderAchievements(data); renderFirstSteps(data); renderPvp(data);
    $('panels').hidden = false;
    $('fatal').hidden = true;
    $('live').hidden = data.connection?.online === false;
    selectTab(activeTab);
    if (focused) [...document.querySelectorAll('[data-action-key]')].find(button => button.dataset.actionKey === focused && !button.disabled)?.focus({ preventScroll: true });
    document.scrollingElement.scrollTop = scrollTop;
  }
  async function queueAction(action) {
    if (expired || [...pending.values()].some(receipt => receipt.action_key === action.key)) return;
    const requestId = crypto.randomUUID();
    // Keep the same request ID if a POST response is lost: no duplicate game action.
    const receipt = { action_key: action.key, status: 'submitting' };
    pending.set(requestId, receipt);
    if (snapshot) render(snapshot);
    message('Sending your request to World…');
    try {
      const result = await api('/actions', { method: 'POST', body: JSON.stringify({ action_key: action.key, request_id: requestId }) });
      pending.set(requestId, result);
      await checkReceipt(requestId);
    } catch (error) {
      if (error.status && error.status < 500) pending.delete(requestId);
      else pending.set(requestId, { ...receipt, status: 'unknown' });
      if (!expired) message(error.status ? error.message : 'Connection interrupted. Checking whether World received your request…', true);
      if (snapshot) render(snapshot);
    }
  }
  async function checkReceipt(requestId) {
    const current = pending.get(requestId);
    if (!current?.id) return;
    const receipt = await api(`/actions/${encodeURIComponent(current.id)}`);
    pending.set(requestId, receipt);
    if (['succeeded', 'rejected'].includes(receipt.status)) {
      pending.delete(requestId);
      const explanation = typeof receipt.result?.message === 'string' ? receipt.result.message : typeof receipt.result?.error === 'string' ? receipt.result.error : null;
      message(explanation || (receipt.status === 'succeeded' ? 'Done. Your adventure is ready in the game.' : 'World could not perform that action. Return to the game and try again.'), receipt.status === 'rejected');
      lastSignature = '';
    } else message('World is handling your request…');
  }
  async function refresh() {
    if (refreshing || expired || !credential) return;
    refreshing = true;
    try {
      for (const [requestId, receipt] of pending) {
        if (receipt.status === 'unknown') {
          // Replay only the exact same idempotency key after a lost response.
          try {
            pending.set(requestId, await api('/actions', { method: 'POST', body: JSON.stringify({ action_key: receipt.action_key, request_id: requestId }) }));
          } catch (error) {
            if (error.status && error.status < 500) {
              pending.delete(requestId);
              message(error.message, true);
              continue;
            }
            throw error;
          }
        }
        await checkReceipt(requestId);
      }
      const data = await api('/adventures');
      snapshot = data;
      const signature = JSON.stringify({ ...data, generated_at: undefined, pending: [...pending.keys()] });
      if (signature !== lastSignature) { render(data); lastSignature = signature; }
      updatePvpCountdown(data);
      failures = 0;
      $('connection').textContent = data.connection?.actions_available === false ? data.connection.reason || 'Connect this character in World to use game actions.' : '';
    } catch (error) {
      failures += 1;
      if (!expired) $('connection').textContent = snapshot ? 'Connection interrupted. Your progress is saved; reconnecting…' : 'Could not load your adventures. Retrying…';
    } finally {
      refreshing = false;
      if (!expired) pollTimer = setTimeout(refresh, Math.min(15000, 2000 * Math.max(1, failures)));
    }
  }
  async function start() {
    selectTab(activeTab);
    const fragment = new URLSearchParams(location.hash.slice(1));
    const launchToken = fragment.get('token');
    // Remove launch credentials before making any request, even when exchange fails.
    if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    if (launchToken) {
      credential = null;
      storage.remove('wakemu.adventures.session');
      try {
        const session = await api('/session', { method: 'POST', body: JSON.stringify({ token: launchToken }) });
        credential = session.token;
        storage.set('wakemu.adventures.session', credential);
      } catch (error) {
        stop(error.status ? error.message : 'The connection could not be established. Run !adventures in the game to try again.');
        return;
      }
    }
    if (!credential) { stop('Run !adventures with your connected character to view your progress and use travel actions.'); return; }
    await refresh();
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !expired) { clearTimeout(pollTimer); refresh(); }
  });
  start();
})();
