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

  const processSteps = document.getElementById('process-steps');
  let nextStepNumber = 1;

  const makeField = (labelText, control, className = '') => {
    const wrapper = document.createElement('label');
    wrapper.className = 'step-field' + (className ? ' ' + className : '');
    const label = document.createElement('span');
    label.textContent = labelText;
    wrapper.append(label, control);
    return wrapper;
  };

  const makeInput = (placeholder = '') => {
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = placeholder;
    return input;
  };

  const makeStatusSelect = (selected = 'observed') => {
    const select = document.createElement('select');
    const options = [
      ['observed', 'Наблюдал в системе'],
      ['confirmed_by_analyst', 'Подтверждено аналитиком'],
      ['hypothesis', 'Гипотеза'],
      ['unknown', 'Неизвестно'],
    ];
    for (const [value, label] of options) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    select.value = selected;
    return select;
  };

  const addProcessStep = () => {
    const empty = processSteps.querySelector('.empty-state');
    if (empty) empty.remove();

    const number = nextStepNumber++;
    const card = document.createElement('article');
    card.className = 'process-step-card';
    card.dataset.stepId = `STEP-${String(number).padStart(3, '0')}`;

    const heading = document.createElement('div');
    heading.className = 'process-step-heading';
    const title = document.createElement('strong');
    title.textContent = `Шаг ${number}`;
    const controls = document.createElement('div');
    controls.className = 'step-order-controls';
    const moveUp = document.createElement('button');
    moveUp.type = 'button';
    moveUp.className = 'text-button';
    moveUp.textContent = '↑ Выше';
    moveUp.addEventListener('click', () => {
      const previous = card.previousElementSibling;
      if (previous && previous.classList.contains('process-step-card')) {
        processSteps.insertBefore(card, previous);
        updateStepOrders();
      }
    });
    const moveDown = document.createElement('button');
    moveDown.type = 'button';
    moveDown.className = 'text-button';
    moveDown.textContent = '↓ Ниже';
    moveDown.addEventListener('click', () => {
      const next = card.nextElementSibling;
      if (next && next.classList.contains('process-step-card')) {
        processSteps.insertBefore(next, card);
        updateStepOrders();
      }
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'text-button remove-step';
    remove.textContent = 'Удалить';
    remove.addEventListener('click', () => {
      card.remove();
      if (!processSteps.querySelector('.process-step-card')) {
        const emptyState = document.createElement('p');
        emptyState.className = 'empty-state';
        emptyState.textContent = 'Шаги ещё не добавлены.';
        processSteps.append(emptyState);
      }
      updateStepOrders();
    });
    controls.append(moveUp, moveDown, remove);
    heading.append(title, controls);

    const action = document.createElement('textarea');
    action.rows = 2;
    action.placeholder = 'Например: пользователь выбирает регион отправления';
    const actionStatus = makeStatusSelect();
    const response = document.createElement('textarea');
    response.rows = 2;
    response.placeholder = 'Например: в поле отображается выбранный регион. Если неизвестно — оставь пустым.';
    const responseStatus = makeStatusSelect();
    const actionGrid = document.createElement('div');
    actionGrid.className = 'step-fields-grid';
    actionGrid.append(
      makeField('Действие пользователя', action),
      makeField('Статус действия', actionStatus)
    );
    const responseGrid = document.createElement('div');
    responseGrid.className = 'step-fields-grid';
    responseGrid.append(
      makeField('Реакция системы', response),
      makeField('Статус реакции', responseStatus)
    );

    const evidenceTitle = document.createElement('div');
    evidenceTitle.className = 'step-subheading';
    evidenceTitle.textContent = 'Источник подтверждения (необязательно)';
    const sourceId = makeInput('Например: screenshot-01 или video-01');
    const sourceType = document.createElement('select');
    for (const [value, label] of [
      ['screenshot', 'Скриншот'],
      ['video', 'Видео'],
      ['browser_capture', 'Запись браузера'],
      ['manual_note', 'Ручная заметка'],
    ]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      sourceType.append(option);
    }
    const timestamp = makeInput('мс от начала видео');
    timestamp.inputMode = 'numeric';
    const frame = makeInput('Номер кадра');
    frame.inputMode = 'numeric';
    const evidenceGrid = document.createElement('div');
    evidenceGrid.className = 'step-evidence-grid';
    evidenceGrid.append(
      makeField('ID источника', sourceId),
      makeField('Тип источника', sourceType),
      makeField('Время, мс', timestamp),
      makeField('Кадр №', frame)
    );

    const questions = document.createElement('textarea');
    questions.rows = 2;
    questions.placeholder = 'Один открытый вопрос на строку';
    card.append(
      heading,
      actionGrid,
      responseGrid,
      evidenceTitle,
      evidenceGrid,
      makeField('Открытые вопросы', questions)
    );
    card._stepControls = { action, actionStatus, response, responseStatus, sourceId, sourceType, timestamp, frame, questions };
    processSteps.append(card);
    updateStepOrders();
  };

  const updateStepOrders = () => {
    Array.from(processSteps.querySelectorAll('.process-step-card')).forEach((card, index) => {
      card.dataset.order = String(index + 1);
      const title = card.querySelector('.process-step-heading strong');
      title.textContent = `Шаг ${index + 1} · ${card.dataset.stepId}`;
    });
  };

  const collectProcessSteps = () => {
    return Array.from(processSteps.querySelectorAll('.process-step-card')).map((card, index) => {
      const fields = card._stepControls;
      const actionText = fields.action.value.trim();
      const responseText = fields.response.value.trim();
      const actionStatusValue = fields.actionStatus.value;
      const responseStatusValue = fields.responseStatus.value;
      if (!actionText && actionStatusValue !== 'unknown') {
        throw new Error(`В шаге ${index + 1} заполни действие или выбери статус «Неизвестно».`);
      }
      if (!responseText && responseStatusValue !== 'unknown') {
        throw new Error(`В шаге ${index + 1} заполни реакцию системы или выбери статус «Неизвестно».`);
      }

      const evidence = [];
      const source = fields.sourceId.value.trim();
      const timeText = fields.timestamp.value.trim();
      const frameText = fields.frame.value.trim();
      if (source || timeText || frameText) {
        const item = {
          source_id: source,
          source_type: fields.sourceType.value,
        };
        if (timeText) {
          if (!/^\d+$/.test(timeText)) throw new Error(`В шаге ${index + 1}: время должно быть целым числом миллисекунд.`);
          item.timestamp_ms = Number(timeText);
        }
        if (frameText) {
          if (!/^\d+$/.test(frameText) || Number(frameText) < 1) throw new Error(`В шаге ${index + 1}: номер кадра должен быть целым числом от 1.`);
          item.frame_number = Number(frameText);
        }
        if (!source) throw new Error(`В шаге ${index + 1}: укажи ID источника доказательства.`);
        if (item.source_type === 'video' && item.timestamp_ms === undefined) {
          throw new Error(`В шаге ${index + 1}: для видео укажи время в миллисекундах.`);
        }
        evidence.push(item);
      }

      return {
        step_id: card.dataset.stepId,
        order: index + 1,
        action: { text: actionText, status: actionStatusValue },
        system_response: { text: responseText, status: responseStatusValue },
        evidence,
        open_questions: fields.questions.value.split('\n').map((value) => value.trim()).filter(Boolean),
      };
    });
  };

  document.getElementById('add-process-step').addEventListener('click', addProcessStep);

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
          steps: collectProcessSteps(),
          calculation_result: {
            value: resultValue || null,
            status: resultValue ? document.getElementById('scenario-result-status').value : 'unknown',
          },
          observations: observationsText ? observationsText.split('\n').filter(Boolean) : [],
        }),
      });
      setScenarioStatus(`Сохранён сценарий ${data.scenario.scenario_id}`);
      document.getElementById('scenario-observations').value = '';
      processSteps.replaceChildren();
      const emptySteps = document.createElement('p');
      emptySteps.className = 'empty-state';
      emptySteps.textContent = 'Шаги ещё не добавлены.';
      processSteps.append(emptySteps);
      nextStepNumber = 1;
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
