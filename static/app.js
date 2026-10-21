(() => {
  const taskInput = document.getElementById('task');
  const generateButton = document.getElementById('generate');
  const buttonLabel = document.getElementById('button-label');
  const status = document.getElementById('status');
  const charCount = document.getElementById('char-count');
  const resultSection = document.getElementById('result-section');
  const answerElement = document.getElementById('answer');
  const validationPanel = document.getElementById('validation-panel');
  const resultSubtitle = document.getElementById('result-subtitle');
  let latestAnswer = '';

  const setStatus = (message, kind = 'normal') => {
    status.className = 'status-line' + (kind === 'error' ? ' error' : '');
    status.replaceChildren();
    const dot = document.createElement('span');
    dot.className = 'status-light';
    const text = document.createElement('span');
    text.textContent = message;
    status.append(dot, text);
  };

  const updateCount = () => {
    charCount.textContent = `${taskInput.value.length.toLocaleString('ru-RU')} / 20 000 символов`;
  };

  const renderAnswer = (text) => {
    // Use text nodes rather than innerHTML so model output cannot inject HTML/scripts.
    answerElement.replaceChildren();
    const lines = text.split('\n');
    const fragment = document.createDocumentFragment();
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        fragment.append(document.createElement('br'));
      } else if (/^#{1,4}\s+/.test(trimmed)) {
        const level = Math.min(4, (trimmed.match(/^#+/)[0].length) + 1);
        const heading = document.createElement(`h${level}`);
        heading.textContent = trimmed.replace(/^#{1,4}\s+/, '');
        fragment.append(heading);
      } else {
        const paragraph = document.createElement('div');
        paragraph.textContent = line;
        fragment.append(paragraph);
      }
    }
    answerElement.append(fragment);
  };

  const renderIssues = (issues) => {
    validationPanel.replaceChildren();
    const summary = document.createElement('div');
    summary.className = 'validation-summary' + (issues.length ? '' : ' ok');
    summary.textContent = issues.length
      ? `Найдено замечаний: ${issues.length}. Проверь их перед использованием результата.`
      : 'Замечаний по доступным проверкам не найдено.';
    validationPanel.append(summary);
    for (const issue of issues) {
      const item = document.createElement('div');
      item.className = 'validation-item';
      item.textContent = issue;
      validationPanel.append(item);
    }
  };

  taskInput.addEventListener('input', updateCount);
  document.getElementById('clear-task').addEventListener('click', () => {
    taskInput.value = '';
    updateCount();
    taskInput.focus();
    setStatus('Поле очищено');
  });

  generateButton.addEventListener('click', async () => {
    const task = taskInput.value.trim();
    if (!task) {
      setStatus('Сначала опиши задачу', 'error');
      taskInput.focus();
      return;
    }
    generateButton.disabled = true;
    buttonLabel.textContent = 'Анализирую…';
    setStatus('Модель формирует требования. Это может занять несколько минут.');
    generateButton.querySelector('.button-icon').textContent = '◌';
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
      const raw = await response.text();
      let data;
      try { data = JSON.parse(raw); } catch { throw new Error(raw || `Ошибка HTTP ${response.status}`); }
      if (!response.ok) throw new Error(data.error || raw || `Ошибка HTTP ${response.status}`);
      latestAnswer = data.answer || '';
      renderAnswer(latestAnswer);
      renderIssues(Array.isArray(data.issues) ? data.issues : []);
      resultSubtitle.textContent = `Модель: ${data.model || 'локальная'} · Замечаний валидатора: ${(data.issues || []).length}`;
      resultSection.hidden = false;
      setStatus('Анализ завершён');
      resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      setStatus(error.message || 'Не удалось выполнить анализ', 'error');
    } finally {
      generateButton.disabled = false;
      buttonLabel.textContent = 'Подготовить анализ';
      generateButton.querySelector('.button-icon').textContent = '✳';
    }
  });

  document.getElementById('copy-answer').addEventListener('click', async () => {
    if (!latestAnswer) return;
    try {
      await navigator.clipboard.writeText(latestAnswer);
      setStatus('Ответ скопирован в буфер обмена');
    } catch {
      setStatus('Не удалось скопировать автоматически — выдели текст ответа', 'error');
    }
  });

  document.getElementById('download-answer').addEventListener('click', () => {
    if (!latestAnswer) return;
    const blob = new Blob(['\ufeff', latestAnswer], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sa-copilot-analysis.txt';
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  updateCount();
})();
