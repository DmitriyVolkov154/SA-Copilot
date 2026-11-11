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
    answerElement.replaceChildren();
    const fragment = document.createDocumentFragment();
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) fragment.append(document.createElement('br'));
      else if (/^#{1,4}\s+/.test(trimmed)) {
        const level = Math.min(4, trimmed.match(/^#+/)[0].length + 1);
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

  const requestJson = async (url, options = {}) => {
    const response = await fetch(url, options);
    const raw = await response.text();
    let data;
    try { data = JSON.parse(raw); } catch { throw new Error(raw || `Ошибка HTTP ${response.status}`); }
    if (!response.ok) throw new Error(data.error || `Ошибка HTTP ${response.status}`);
    return data;
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
      const data = await requestJson('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
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

  const scenarioStatus = document.getElementById('scenario-status');
  const setScenarioStatus = (message, error = false) => {
    scenarioStatus.className = 'status-line' + (error ? ' error' : '');
    scenarioStatus.replaceChildren();
    const dot = document.createElement('span');
    dot.className = 'status-light';
    const label = document.createElement('span');
    label.textContent = message;
    scenarioStatus.append(dot, label);
  };

  const selectedScenarioIds = () =>
    Array.from(document.querySelectorAll('.scenario-choice:checked')).map((input) => input.value);

  const updateCompareButton = () => {
    document.getElementById('compare-scenarios').disabled = selectedScenarioIds().length < 2;
  };

  const renderScenarios = (scenarios) => {
    const list = document.getElementById('scenario-list');
    list.replaceChildren();
    if (!scenarios.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'Пока нет сценариев. Добавь первый вариант расчёта слева.';
      list.append(empty);
      updateCompareButton();
      return;
    }

    for (const scenario of scenarios) {
      const wrapper = document.createElement('div');
      wrapper.className = 'scenario-item';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'scenario-choice';
      checkbox.value = scenario.scenario_id;
      checkbox.id = `scenario-${scenario.scenario_id}`;
      checkbox.addEventListener('change', updateCompareButton);
      const label = document.createElement('label');
      label.htmlFor = checkbox.id;
      const title = document.createElement('strong');
      title.textContent = `${scenario.scenario_id} · ${scenario.process_name}`;
      const details = document.createElement('small');
      const result = scenario.calculation_result || {};
      details.textContent = `${scenario.input_parameters.length} параметров · Результат: ${result.value ?? 'не указан'} · Не проверен`;
      label.append(title, details);
      wrapper.append(checkbox, label);
      list.append(wrapper);
    }
    updateCompareButton();
  };

  const loadScenarios = async () => {
    try {
      const data = await requestJson('/api/scenarios');
      renderScenarios(data.scenarios || []);
    } catch (error) {
      document.getElementById('scenario-list').textContent = error.message;
      setScenarioStatus('Не удалось загрузить сценарии', true);
    }
  };

  document.getElementById('save-scenario').addEventListener('click', async () => {
    const processName = document.getElementById('process-name').value.trim();
    const resultValue = document.getElementById('scenario-result').value.trim();
    let parameters;
    try {
      parameters = JSON.parse(document.getElementById('scenario-parameters').value || '[]');
      if (!Array.isArray(parameters)) throw new Error('Ожидается JSON-массив параметров.');
    } catch (error) {
      setScenarioStatus(`Ошибка в JSON параметров: ${error.message}`, true);
      return;
    }
    const observationsText = document.getElementById('scenario-observations').value.trim();
    const button = document.getElementById('save-scenario');
    button.disabled = true;
    try {
      const data = await requestJson('/api/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          process_name: processName,
          input_parameters: parameters,
          calculation_result: {
            value: resultValue || null,
            status: resultValue ? document.getElementById('scenario-result-status').value : 'unknown',
          },
          observations: observationsText ? observationsText.split('\n').filter(Boolean) : [],
        }),
      });
      setScenarioStatus(`Сохранён сценарий ${data.scenario.scenario_id}`);
      document.getElementById('scenario-observations').value = '';
      await loadScenarios();
    } catch (error) {
      setScenarioStatus(error.message || 'Не удалось сохранить сценарий', true);
    } finally {
      button.disabled = false;
    }
  });

  document.getElementById('refresh-scenarios').addEventListener('click', loadScenarios);

  const appendText = (parent, tag, text, className) => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.append(node);
    return node;
  };

  const renderComparison = (data) => {
    const root = document.getElementById('comparison-result');
    root.replaceChildren();
    appendText(
      root,
      'div',
      `Сравнено вариантов: ${data.comparison_count}. Параметры с изменениями: ${(data.summary.changed_parameter_names || []).join(', ') || 'не выявлены'}.`,
      'comparison-summary'
    );

    for (const item of data.comparisons || []) {
      const card = document.createElement('article');
      card.className = 'comparison-card';
      appendText(card, 'h3', `${item.baseline_scenario_id} → ${item.scenario_id}`);
      appendText(card, 'h4', 'Изменившиеся параметры');
      const changed = document.createElement('ul');
      if (!item.changed_parameters.length) appendText(changed, 'li', 'Подтверждённых изменений нет.');
      for (const parameter of item.changed_parameters) {
        appendText(changed, 'li', `${parameter.name}: ${JSON.stringify(parameter.baseline.value)} → ${JSON.stringify(parameter.candidate.value)}`);
      }
      card.append(changed);

      appendText(card, 'h4', 'Результат расчёта');
      appendText(card, 'p', `${JSON.stringify(item.calculation_result.baseline.value)} → ${JSON.stringify(item.calculation_result.candidate.value)} · Статус сравнения: ${item.calculation_result.status}`);

      for (const warning of item.warnings || []) appendText(card, 'div', warning, 'comparison-warning');
      root.append(card);
    }

    if ((data.suggested_experiments || []).length) {
      appendText(root, 'h3', 'Предлагаемые дополнительные эксперименты');
      for (const experiment of data.suggested_experiments) {
        const card = document.createElement('article');
        card.className = 'experiment-card';
        appendText(card, 'strong', `${experiment.experiment_id} · ${experiment.title}`);
        if (experiment.change_only) {
          appendText(card, 'p', `Изменить только: ${experiment.change_only}. ${JSON.stringify(experiment.baseline_value)} → ${JSON.stringify(experiment.test_value)}`);
        }
        const steps = document.createElement('ol');
        for (const step of experiment.steps || []) appendText(steps, 'li', step);
        card.append(steps);
        if (experiment.limitation) appendText(card, 'p', experiment.limitation);
        root.append(card);
      }
    }
  };

  document.getElementById('compare-scenarios').addEventListener('click', async () => {
    const scenarioIds = selectedScenarioIds();
    if (scenarioIds.length < 2) return;
    const button = document.getElementById('compare-scenarios');
    button.disabled = true;
    try {
      const data = await requestJson('/api/scenarios/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_ids: scenarioIds }),
      });
      renderComparison(data);
    } catch (error) {
      const root = document.getElementById('comparison-result');
      root.replaceChildren();
      appendText(root, 'div', error.message, 'comparison-warning');
    } finally {
      updateCompareButton();
    }
  });

  updateCount();
  loadScenarios();
})();
