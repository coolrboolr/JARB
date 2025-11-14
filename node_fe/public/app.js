const API_BASE = window.APP_CONFIG?.API_BASE || 'http://localhost:5000';

const state = {
    tools: [],
    selectedToolName: null,
    runHistoryCache: {},
};

const elements = {
    apiBasePill: document.getElementById('api-base-pill'),
    toolList: document.getElementById('tool-list'),
    reloadButton: document.getElementById('reload-tools'),
    catalogLoading: document.getElementById('catalog-loading'),
    catalogError: document.getElementById('catalog-error'),
    catalogErrorMessage: document.getElementById('catalog-error-message'),
    catalogRetry: document.getElementById('catalog-retry'),
    detailPlaceholder: document.getElementById('detail-placeholder'),
    detailContainer: document.getElementById('tool-detail'),
    toolTitle: document.getElementById('tool-title'),
    toolDocstring: document.getElementById('tool-docstring'),
    toolReturn: document.getElementById('tool-return'),
    parametersSection: document.getElementById('parameters-section'),
    toolForm: document.getElementById('tool-form'),
    resultBanner: document.getElementById('result-banner'),
    resultOutput: document.getElementById('result-output'),
    runHistorySection: document.getElementById('run-history'),
    runHistoryReload: document.getElementById('run-history-reload'),
    runHistoryLoading: document.getElementById('run-history-loading'),
    runHistoryError: document.getElementById('run-history-error'),
    runHistoryEmpty: document.getElementById('run-history-empty'),
    runHistoryTable: document.getElementById('run-history-table'),
    runHistoryTableBody: document.querySelector('#run-history-table tbody'),
};

function init() {
    elements.toolForm?.addEventListener('submit', handleToolSubmit);
    elements.reloadButton?.addEventListener('click', loadCatalog);
    elements.catalogRetry?.addEventListener('click', loadCatalog);
    elements.runHistoryReload?.addEventListener('click', () => {
        if (state.selectedToolName) {
            loadRunHistory(state.selectedToolName, { force: true });
        }
    });
    updateApiBaseIndicator();
    loadCatalog();
}

async function loadCatalog() {
    setCatalogLoading(true);
    hideCatalogError();
    try {
        const response = await fetch(`${API_BASE}/api/tools`);
        const envelope = await safeJson(response);

        if (!envelope || envelope.success !== true) {
            const errorPayload = envelope?.error || {
                code: 'CATALOG_FAILED',
                message: 'The backend did not return a success envelope.',
            };
            showCatalogError(errorPayload);
            state.tools = [];
            state.selectedToolName = null;
            renderToolList();
            renderToolDetail(null);
            return;
        }

        state.tools = Array.isArray(envelope.data?.tools) ? envelope.data.tools : [];

        if (!state.tools.find((tool) => tool.name === state.selectedToolName)) {
            state.selectedToolName = null;
        }

        renderToolList();
        renderToolDetail(getSelectedTool());
    } catch (error) {
        showCatalogError({
            code: 'NETWORK_ERROR',
            message: error.message || 'Unable to reach the backend.',
        });
        state.tools = [];
        state.selectedToolName = null;
        renderToolList();
        renderToolDetail(null);
    } finally {
        setCatalogLoading(false);
    }
}

function safeJson(response) {
    return response
        .json()
        .catch(() => ({ success: false, error: { code: 'INVALID_JSON', message: 'Response body was not JSON.' } }));
}

function setCatalogLoading(isLoading) {
    toggleHidden(elements.catalogLoading, !isLoading);
    if (elements.reloadButton) {
        elements.reloadButton.disabled = isLoading;
    }
}

function showCatalogError(error) {
    if (!elements.catalogError || !elements.catalogErrorMessage) {
        return;
    }
    const code = error?.code || 'ERROR';
    const message = error?.message || 'Something went wrong while loading the catalog.';
    elements.catalogErrorMessage.textContent = `${code}: ${message}`;
    toggleHidden(elements.catalogError, false);
}

function hideCatalogError() {
    toggleHidden(elements.catalogError, true);
    if (elements.catalogErrorMessage) {
        elements.catalogErrorMessage.textContent = '';
    }
}

function renderToolList() {
    if (!elements.toolList) {
        return;
    }

    elements.toolList.innerHTML = '';

    if (state.tools.length === 0) {
        const empty = document.createElement('li');
        empty.className = 'muted';
        empty.textContent = 'No tools available yet.';
        elements.toolList.appendChild(empty);
        return;
    }

    const fragment = document.createDocumentFragment();
    state.tools.forEach((tool) => {
        const listItem = document.createElement('li');
        listItem.className = 'tool-list-item';
        if (tool.name === state.selectedToolName) {
            listItem.classList.add('active');
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'tool-button';
        const summary = summarizeDoc(tool.docstring);

        const nameSpan = document.createElement('span');
        nameSpan.className = 'tool-name';
        nameSpan.textContent = tool.name;

        const summarySpan = document.createElement('span');
        summarySpan.className = 'tool-summary';
        summarySpan.textContent = summary || 'No description available.';

        button.appendChild(nameSpan);
        button.appendChild(summarySpan);
        button.addEventListener('click', () => selectTool(tool.name));

        listItem.appendChild(button);
        fragment.appendChild(listItem);
    });

    elements.toolList.appendChild(fragment);
}

function selectTool(toolName) {
    state.selectedToolName = toolName;
    renderToolList();
    renderToolDetail(getSelectedTool());
}

function getSelectedTool() {
    return state.tools.find((tool) => tool.name === state.selectedToolName) || null;
}

function renderToolDetail(tool) {
    if (!elements.detailContainer || !elements.detailPlaceholder) {
        return;
    }

    if (!tool) {
        elements.detailPlaceholder.textContent = state.tools.length
            ? 'Select a tool to view its description and parameters.'
            : 'No tools detected yet. Create one via the API, then reload the catalog.';
        toggleHidden(elements.detailPlaceholder, false);
        toggleHidden(elements.detailContainer, true);
        clearResult();
        hideRunHistorySection();
        return;
    }

    toggleHidden(elements.detailPlaceholder, true);
    toggleHidden(elements.detailContainer, false);
    showRunHistorySection();

    elements.toolTitle.textContent = tool.name;
    const docstring = (tool.docstring || '').trim();
    elements.toolDocstring.textContent = docstring || 'No description available.';

    const returnDisplay = formatReturnAnnotation(tool.return_annotation);
    if (returnDisplay) {
        elements.toolReturn.textContent = `Returns: ${returnDisplay}`;
        elements.toolReturn.classList.remove('hidden');
    } else {
        elements.toolReturn.textContent = '';
        elements.toolReturn.classList.add('hidden');
    }

    renderParameterMetadata(tool);
    renderToolForm(tool);
    clearResult();
    loadRunHistory(tool.name);
}

function renderParameterMetadata(tool) {
    if (!elements.parametersSection) {
        return;
    }
    elements.parametersSection.innerHTML = '';

    if (!tool.parameters || tool.parameters.length === 0) {
        const noParams = document.createElement('p');
        noParams.className = 'muted';
        noParams.textContent = 'This tool does not declare any parameters.';
        elements.parametersSection.appendChild(noParams);
        return;
    }

    const table = document.createElement('table');
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>Name</th><th>Type</th><th>Kind</th><th>Default</th><th>Required</th></tr>';
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    tool.parameters.forEach((param) => {
        const row = document.createElement('tr');

        const nameCell = document.createElement('td');
        nameCell.textContent = param.name;

        const typeCell = document.createElement('td');
        typeCell.textContent = formatTypeLabel(param);

        const kindCell = document.createElement('td');
        kindCell.textContent = param.kind;

        const defaultCell = document.createElement('td');
        defaultCell.textContent = formatDefaultValue(param.default);

        const requiredCell = document.createElement('td');
        requiredCell.textContent = param.required ? 'Yes' : 'No';

        row.appendChild(nameCell);
        row.appendChild(typeCell);
        row.appendChild(kindCell);
        row.appendChild(defaultCell);
        row.appendChild(requiredCell);
        tbody.appendChild(row);
    });

    table.appendChild(tbody);
    elements.parametersSection.appendChild(table);
}

function renderToolForm(tool) {
    if (!elements.toolForm) {
        return;
    }

    elements.toolForm.replaceChildren();

    const fieldsContainer = document.createElement('div');
    fieldsContainer.className = 'form-fields';

    const hasParams = tool.parameters && tool.parameters.length > 0;
    if (hasParams) {
        tool.parameters.forEach((param) => {
            const field = buildFormField(param);
            fieldsContainer.appendChild(field);
        });
    } else {
        const info = document.createElement('p');
        info.className = 'muted';
        info.textContent = 'No parameters required – just hit “Run Tool.”';
        fieldsContainer.appendChild(info);
    }

    elements.toolForm.appendChild(fieldsContainer);

    const actions = document.createElement('div');
    actions.className = 'form-actions';
    const submitButton = document.createElement('button');
    submitButton.type = 'submit';
    submitButton.className = 'primary';
    submitButton.textContent = 'Run Tool';
    actions.appendChild(submitButton);

    elements.toolForm.appendChild(actions);
}

async function handleToolSubmit(event) {
    event.preventDefault();

    const tool = getSelectedTool();
    if (!tool) {
        return;
    }

    const submitButton = event.currentTarget.querySelector('button[type="submit"]');
    const validation = collectFormParams(event.currentTarget, tool);
    if (validation.errors.length) {
        showResultError({
            code: 'CLIENT_VALIDATION',
            message: validation.errors.join(' '),
        });
        return;
    }

    setSubmitButtonState(submitButton, true);
    showResultInfo('Running tool…');

    try {
        const { params } = validation;
        const response = await fetch(`${API_BASE}/api/use_tool`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tool_name: tool.name,
                params,
            }),
        });

        const envelope = await safeJson(response);

        if (!envelope || envelope.success !== true) {
            const errorPayload = envelope?.error || {
                code: response.ok ? 'USE_FAILED' : response.status,
                message: envelope?.error?.message || 'Tool execution failed.',
            };
            showResultError(errorPayload);
            return;
        }

        showResultSuccess(envelope.data?.result);
    } catch (error) {
        showResultError({
            code: 'NETWORK_ERROR',
            message: error.message || 'Unable to reach the backend.',
        });
    } finally {
        setSubmitButtonState(submitButton, false);
    }
}

function collectFormParams(form, tool) {
    const params = {};
    const errors = [];

    if (!tool?.parameters) {
        return { params, errors };
    }

    tool.parameters.forEach((param) => {
        const field = form.elements.namedItem(param.name);
        if (!field) {
            return;
        }

        const typeLabel = formatTypeLabel(param);

        if (typeLabel === 'bool') {
            params[param.name] = Boolean(field.checked);
            return;
        }

        const rawValue = typeof field.value === 'string' ? field.value.trim() : '';

        if (rawValue === '') {
            if (param.required) {
                errors.push(`Parameter "${param.name}" is required.`);
            }
            return;
        }

        if (typeLabel === 'int' || typeLabel === 'float') {
            const numeric = typeLabel === 'int' ? parseInt(rawValue, 10) : parseFloat(rawValue);
            if (Number.isNaN(numeric)) {
                errors.push(`Parameter "${param.name}" must be a valid ${typeLabel}.`);
                return;
            }
            params[param.name] = numeric;
            return;
        }

        if (typeLabel === 'json') {
            try {
                params[param.name] = JSON.parse(rawValue);
            } catch (_err) {
                errors.push(`Parameter "${param.name}" must be valid JSON.`);
            }
            return;
        }

        if (typeLabel === 'str') {
            params[param.name] = rawValue;
            return;
        }

        params[param.name] = coerceValue(rawValue);
    });

    return { params, errors };
}

function buildFormField(param) {
    const typeLabel = formatTypeLabel(param);
    const field = document.createElement('label');
    field.className = `form-field form-field-${typeLabel}`;
    if (typeLabel === 'bool') {
        field.classList.add('form-field-checkbox');
    }
    if (param.required) {
        field.classList.add('required');
    }
    field.dataset.parameter = param.name;
    field.dataset.paramType = typeLabel;
    field.dataset.required = param.required ? 'true' : 'false';

    const header = document.createElement('div');
    header.className = 'field-header';

    const nameEl = document.createElement('span');
    nameEl.className = 'field-name';
    nameEl.textContent = param.name;

    const badges = document.createElement('div');
    badges.className = 'field-badges';

    const typePill = document.createElement('span');
    typePill.className = 'type-pill';
    typePill.textContent = typeLabel;

    const requirementPill = document.createElement('span');
    requirementPill.className = `requirement-pill ${param.required ? 'required' : 'optional'}`;
    requirementPill.textContent = param.required ? 'Required' : 'Optional';

    badges.appendChild(typePill);
    badges.appendChild(requirementPill);

    header.appendChild(nameEl);
    header.appendChild(badges);

    const controlWrapper = document.createElement('div');
    controlWrapper.className = 'field-control';
    const control = createControlForParam(param, typeLabel);
    controlWrapper.appendChild(control);

    const hint = document.createElement('div');
    hint.className = 'field-hint';
    hint.textContent = param.kind;

    field.appendChild(header);
    field.appendChild(controlWrapper);
    field.appendChild(hint);

    return field;
}

function createControlForParam(param, typeLabel) {
    if (typeLabel === 'bool') {
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.name = param.name;
        input.checked = typeof param.default === 'boolean' ? param.default : false;
        input.dataset.paramType = typeLabel;
        return input;
    }

    if (typeLabel === 'json') {
        const textarea = document.createElement('textarea');
        textarea.name = param.name;
        textarea.rows = 4;
        textarea.spellcheck = false;
        textarea.placeholder = 'JSON value';
        textarea.dataset.paramType = typeLabel;
        const defaultValue = formatDefaultInput(param.default);
        if (defaultValue) {
            textarea.value = defaultValue;
        }
        return textarea;
    }

    const input = document.createElement('input');
    input.name = param.name;
    input.placeholder = param.kind;
    input.dataset.paramType = typeLabel;

    if (typeLabel === 'int' || typeLabel === 'float') {
        input.type = 'number';
        input.step = typeLabel === 'int' ? '1' : 'any';
        input.inputMode = typeLabel === 'int' ? 'numeric' : 'decimal';
    } else {
        input.type = 'text';
    }

    const defaultValue = formatDefaultInput(param.default);
    if (defaultValue) {
        input.value = defaultValue;
    }

    return input;
}

function coerceValue(value) {
    const trimmed = value.trim();

    if (trimmed.toLowerCase() === 'true') {
        return true;
    }
    if (trimmed.toLowerCase() === 'false') {
        return false;
    }

    if (trimmed !== '' && !Number.isNaN(Number(trimmed))) {
        return Number(trimmed);
    }

    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        try {
            return JSON.parse(trimmed);
        } catch (_err) {
            // fall through to raw string
        }
    }

    return value;
}

function showResultInfo(message) {
    setResultState({ variant: 'info', title: message });
}

function showResultSuccess(result) {
    const payload = formatResultPayload(result);
    setResultState({
        variant: 'success',
        title: 'Tool executed successfully.',
        detail: 'See the response payload below.',
        payload,
    });
}

function showResultError(error) {
    const code = error?.code || 'ERROR';
    const message = error?.message || 'The backend reported a failure.';
    setResultState({
        variant: 'error',
        title: `Execution failed (${code})`,
        detail: message,
    });
}

function setResultState({ variant, title = '', detail = '', payload }) {
    if (!elements.resultBanner || !elements.resultOutput) {
        return;
    }

    if (!variant) {
        clearResult();
        return;
    }

    elements.resultBanner.className = `banner banner-${variant}`;
    elements.resultBanner.innerHTML = '';

    const strong = document.createElement('strong');
    strong.textContent = title;
    elements.resultBanner.appendChild(strong);

    if (detail) {
        const detailEl = document.createElement('div');
        detailEl.className = 'banner-detail';
        detailEl.textContent = detail;
        elements.resultBanner.appendChild(detailEl);
    }

    toggleHidden(elements.resultBanner, false);

    if (payload !== undefined) {
        elements.resultOutput.textContent = payload;
        toggleHidden(elements.resultOutput, false);
    } else {
        toggleHidden(elements.resultOutput, true);
        elements.resultOutput.textContent = '';
    }
}

function clearResult() {
    toggleHidden(elements.resultBanner, true);
    toggleHidden(elements.resultOutput, true);
    if (elements.resultBanner) {
        elements.resultBanner.innerHTML = '';
    }
    if (elements.resultOutput) {
        elements.resultOutput.textContent = '';
    }
}

function setSubmitButtonState(button, isRunning) {
    if (!button) {
        return;
    }
    if (isRunning) {
        button.dataset.originalText = button.textContent;
        button.textContent = 'Running…';
    } else if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
    }
    button.disabled = isRunning;
}

function summarizeDoc(docstring) {
    if (!docstring) {
        return '';
    }
    const firstLine = docstring.trim().split('\n')[0];
    return firstLine.length > 120 ? `${firstLine.slice(0, 117)}…` : firstLine;
}

function formatDefaultValue(value) {
    if (value === null || value === undefined) {
        return '—';
    }
    if (typeof value === 'object') {
        try {
            return JSON.stringify(value);
        } catch (_err) {
            return '[object]';
        }
    }
    return String(value);
}

function formatDefaultInput(value) {
    if (value === null || value === undefined) {
        return '';
    }
    if (typeof value === 'object') {
        try {
            return JSON.stringify(value);
        } catch (_err) {
            return '';
        }
    }
    return String(value);
}

function formatReturnAnnotation(annotation) {
    if (!annotation) {
        return '';
    }
    if (typeof annotation === 'object') {
        return JSON.stringify(annotation);
    }
    return String(annotation);
}

function formatResultPayload(payload) {
    if (payload === undefined) {
        return 'No result returned.';
    }
    if (typeof payload === 'string') {
        return payload;
    }
    try {
        return JSON.stringify(payload, null, 2);
    } catch (_err) {
        return String(payload);
    }
}

function toggleHidden(element, shouldHide) {
    if (!element) {
        return;
    }
    if (shouldHide) {
        element.classList.add('hidden');
    } else {
        element.classList.remove('hidden');
    }
}

function updateApiBaseIndicator() {
    if (!elements.apiBasePill) {
        return;
    }
    elements.apiBasePill.textContent = `Backend: ${API_BASE}`;
}

function formatTypeLabel(param) {
    if (!param || !param.annotation) {
        return 'any';
    }
    return param.annotation.type || 'any';
}

async function loadRunHistory(toolName, { force = false } = {}) {
    if (!toolName) {
        hideRunHistorySection();
        return;
    }

    const cached = state.runHistoryCache[toolName];
    if (cached && !force) {
        renderRunHistory(cached);
        return;
    }

    setRunHistoryLoading(true);
    hideRunHistoryError();

    try {
        const response = await fetch(`${API_BASE}/api/tool_runs/${encodeURIComponent(toolName)}?limit=20`);
        const envelope = await safeJson(response);
        if (!envelope || envelope.success !== true) {
            const errorPayload = envelope?.error || {
                code: 'RUNS_FAILED',
                message: 'Unable to fetch run history.',
            };
            if (state.selectedToolName === toolName) {
                showRunHistoryError(errorPayload);
            }
            return;
        }
        const runs = Array.isArray(envelope.data?.runs) ? envelope.data.runs : [];
        state.runHistoryCache[toolName] = runs;
        if (state.selectedToolName === toolName) {
            renderRunHistory(runs);
        }
    } catch (error) {
        if (state.selectedToolName === toolName) {
            showRunHistoryError({
                code: 'NETWORK_ERROR',
                message: error.message || 'Unable to fetch run history.',
            });
        }
    } finally {
        setRunHistoryLoading(false);
    }
}

function renderRunHistory(runs) {
    if (!elements.runHistoryTable || !elements.runHistoryTableBody) {
        return;
    }

    hideRunHistoryError();

    if (!runs || runs.length === 0) {
        elements.runHistoryTableBody.innerHTML = '';
        toggleHidden(elements.runHistoryTable, true);
        toggleHidden(elements.runHistoryEmpty, false);
        elements.runHistoryEmpty.textContent = 'No runs recorded yet.';
        return;
    }

    toggleHidden(elements.runHistoryEmpty, true);
    toggleHidden(elements.runHistoryTable, false);

    elements.runHistoryTableBody.innerHTML = '';
    runs.forEach((run) => {
        const row = document.createElement('tr');

        const finishedCell = document.createElement('td');
        finishedCell.textContent = formatTimestamp(run.finished_at);

        const statusCell = document.createElement('td');
        statusCell.textContent = run.status || 'unknown';
        statusCell.className = run.status === 'success' ? 'run-status-success' : 'run-status-error';

        const durationCell = document.createElement('td');
        durationCell.textContent = typeof run.duration_ms === 'number' ? `${run.duration_ms} ms` : '—';

        const paramsCell = document.createElement('td');
        paramsCell.textContent = formatPreview(run.params);

        const resultCell = document.createElement('td');
        resultCell.textContent = run.result_summary || '—';

        row.appendChild(finishedCell);
        row.appendChild(statusCell);
        row.appendChild(durationCell);
        row.appendChild(paramsCell);
        row.appendChild(resultCell);

        elements.runHistoryTableBody.appendChild(row);
    });
}

function setRunHistoryLoading(isLoading) {
    if (!elements.runHistoryLoading || !elements.runHistoryReload) {
        return;
    }
    toggleHidden(elements.runHistoryLoading, !isLoading);
    elements.runHistoryReload.disabled = isLoading;
}

function showRunHistorySection() {
    toggleHidden(elements.runHistorySection, false);
    toggleHidden(elements.runHistoryEmpty, true);
    toggleHidden(elements.runHistoryTable, true);
    hideRunHistoryError();
}

function hideRunHistorySection() {
    toggleHidden(elements.runHistorySection, true);
    hideRunHistoryError();
    setRunHistoryLoading(false);
}

function showRunHistoryError(error) {
    if (!elements.runHistoryError) {
        return;
    }
    const code = error?.code || 'ERROR';
    const message = error?.message || 'Unable to load run history.';
    elements.runHistoryError.textContent = `${code}: ${message}`;
    toggleHidden(elements.runHistoryError, false);
    toggleHidden(elements.runHistoryEmpty, true);
    toggleHidden(elements.runHistoryTable, true);
}

function hideRunHistoryError() {
    if (!elements.runHistoryError) {
        return;
    }
    toggleHidden(elements.runHistoryError, true);
    elements.runHistoryError.textContent = '';
}

function formatTimestamp(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function formatPreview(value) {
    if (value === undefined) {
        return '—';
    }
    try {
        const text = JSON.stringify(value);
        if (text.length > 80) {
            return `${text.slice(0, 77)}...`;
        }
        return text;
    } catch (_err) {
        return String(value);
    }
}

init();
