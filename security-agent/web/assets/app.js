"use strict";

const state = {
  csrf: "",
  username: "",
  cases: [],
  currentCase: null,
  view: "chat",
  statusTimer: null,
  pendingApprovalId: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET" && state.csrf) {
    headers["X-CSRF-Token"] = state.csrf;
  }
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  if (response.status === 401) {
    showLogin();
    throw new Error("Authentication required");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function showLogin() {
  clearInterval(state.statusTimer);
  $("#app-view").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
}

function showApp(session) {
  state.csrf = session.csrf_token;
  state.username = session.username;
  $("#current-user").textContent = session.username;
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.remove("hidden");
  window.setTimeout(() => node.classList.add("hidden"), 4000);
}

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function profileLabel(profile) {
  return { soc: "SOC", redteam: "Red Team", grc: "GRC" }[profile] || profile;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function login(event) {
  event.preventDefault();
  $("#login-error").textContent = "";
  try {
    const session = await api("/api/web/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("#login-username").value,
        password: $("#login-password").value,
      }),
    });
    showApp(session);
    $("#login-password").value = "";
    await loadCases();
    await refreshStatus();
    state.statusTimer = window.setInterval(refreshStatus, 30000);
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
}

async function logout() {
  try {
    await api("/api/web/logout", { method: "POST" });
  } finally {
    state.csrf = "";
    state.currentCase = null;
    showLogin();
  }
}

async function loadCases(selectCaseId = null) {
  state.cases = await api("/api/web/cases");
  renderCases();
  const target = selectCaseId || state.currentCase?.id || state.cases[0]?.id;
  if (target) await selectCase(target);
}

function renderCases() {
  const list = $("#case-list");
  list.replaceChildren();
  if (!state.cases.length) {
    list.append(node("p", "muted", "No cases yet."));
    return;
  }
  for (const item of state.cases) {
    const button = node("button", "case-item");
    if (state.currentCase?.id === item.id) button.classList.add("active");
    const title = node("strong", "", item.title);
    const meta = node("div", "case-item-meta");
    meta.append(
      node("span", "", profileLabel(item.profile)),
      node("span", "", `${item.message_count} messages`),
    );
    button.append(title, meta);
    button.addEventListener("click", () => selectCase(item.id));
    list.append(button);
  }
}

async function selectCase(caseId) {
  state.currentCase = await api(`/api/web/cases/${encodeURIComponent(caseId)}`);
  $("#empty-state").classList.add("hidden");
  $("#case-workspace").classList.remove("hidden");
  $("#case-title").textContent = state.currentCase.title;
  $("#case-meta").textContent =
    `${profileLabel(state.currentCase.profile)} · ${state.currentCase.status} · ` +
    `Updated ${formatTime(state.currentCase.updated_at)}`;
  renderCases();
  renderMessages();
  renderApprovals();
}

async function createCase(event) {
  event.preventDefault();
  try {
    const created = await api("/api/web/cases", {
      method: "POST",
      body: JSON.stringify({
        title: $("#new-case-title").value,
        profile: $("#new-case-profile").value,
      }),
    });
    $("#new-case-title").value = "";
    $("#new-case-form").classList.add("hidden");
    await loadCases(created.id);
  } catch (error) {
    toast(error.message);
  }
}

function renderMessages() {
  const list = $("#message-list");
  list.replaceChildren();
  for (const message of state.currentCase.messages) {
    const card = node("article", `message ${message.role}`);
    const head = node("div", "message-head");
    head.append(
      node("strong", "", message.role === "user" ? "Operator" : "Security AI"),
      node("time", "", formatTime(message.created_at)),
    );
    card.append(head, node("p", "message-content", message.content));

    if (message.evidence?.length) {
      const evidence = node("div", "message-evidence");
      evidence.append(node("strong", "", "Evidence"));
      for (const item of message.evidence) {
        evidence.append(node("span", "pill", item));
      }
      card.append(evidence);
    }

    for (const result of message.tool_results || []) {
      const details = node("details", "tool-result");
      const summary = node(
        "summary",
        "",
        `${result.name} · ${result.status}`,
      );
      const output = node(
        "pre",
        "",
        JSON.stringify(
          {
            reason: result.reason,
            arguments: result.arguments,
            output: result.output,
          },
          null,
          2,
        ),
      );
      details.append(summary, output);
      card.append(details);
    }

    if (message.citations?.length) {
      const citations = node("div", "citations");
      citations.append(node("strong", "", "Sources "));
      for (const item of message.citations) {
        citations.append(node("span", "pill", item));
      }
      card.append(citations);
    }
    list.append(card);
  }
  window.requestAnimationFrame(() => {
    list.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
  });
}

function renderApprovals() {
  const pending = (state.currentCase.approvals || []).filter(
    (item) => item.status === "pending",
  );
  const panel = $("#approval-panel");
  const list = $("#approval-list");
  list.replaceChildren();
  panel.classList.toggle("hidden", pending.length === 0);

  for (const approval of pending) {
    const card = node("div", "approval-card");
    const capability = node("code", "", approval.capability);
    const reason = node(
      "p",
      "",
      approval.justification || "This action requires explicit operator approval.",
    );
    const details = node("details", "");
    details.append(
      node("summary", "", "Review exact arguments"),
      node("pre", "audit-detail", JSON.stringify(approval.arguments, null, 2)),
    );
    const actions = node("div", "approval-actions");
    const approveButton = node("button", "primary", "Approve and execute");
    const rejectButton = node("button", "danger-button", "Reject");
    approveButton.addEventListener("click", () => openApprovalDialog(approval.id));
    rejectButton.addEventListener("click", () => decideApproval(approval.id, false));
    actions.append(approveButton, rejectButton);
    card.append(capability, reason, details, actions);
    list.append(card);
  }
}

function openApprovalDialog(approvalId) {
  state.pendingApprovalId = approvalId;
  $("#approval-key").value = "";
  $("#approval-dialog").showModal();
  $("#approval-key").focus();
}

async function submitApproval(event) {
  event.preventDefault();
  const approvalId = state.pendingApprovalId;
  const approvalKey = $("#approval-key").value;
  if (!approvalId || !approvalKey) return;
  $("#approval-dialog").close();
  $("#approval-key").value = "";
  state.pendingApprovalId = null;
  await decideApproval(approvalId, true, approvalKey);
}

async function decideApproval(approvalId, approved, approvalKey = "") {
  const action = approved ? "approve" : "reject";
  try {
    toast(approved ? "Executing approved action…" : "Rejecting action…");
    await api(`/api/web/approvals/${approvalId}/${action}`, {
      method: "POST",
      body: approved ? JSON.stringify({ approval_key: approvalKey }) : undefined,
    });
    await selectCase(state.currentCase.id);
    await loadCases(state.currentCase.id);
    toast(approved ? "Approved action completed." : "Action rejected.");
  } catch (error) {
    toast(error.message);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (!state.currentCase) return;
  const button = $("#send-button");
  const message = $("#chat-message").value.trim();
  if (!message) return;
  button.disabled = true;
  button.textContent = "Working…";
  try {
    const evidence = $("#chat-evidence").value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    await api(`/api/web/cases/${state.currentCase.id}/messages`, {
      method: "POST",
      body: JSON.stringify({
        message,
        evidence,
        allow_tools: $("#allow-tools").checked,
      }),
    });
    $("#chat-message").value = "";
    $("#chat-evidence").value = "";
    await selectCase(state.currentCase.id);
    await loadCases(state.currentCase.id);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Send";
  }
}

async function refreshStatus() {
  try {
    const payload = await api("/api/web/status");
    renderStatus(payload.services);
  } catch (error) {
    renderStatus({});
  }
}

function renderStatus(services) {
  const strip = $("#service-status");
  strip.replaceChildren();
  for (const name of ["llm", "bas", "extrahop", "crowdstrike"]) {
    const item = services[name] || { name, status: "offline", error: "Unavailable" };
    const card = node("div", "status-card");
    const dot = node("i", `status-dot ${item.status}`);
    const text = node("div", "");
    const detail = item.status === "online"
      ? `${item.latency_ms} ms${item.tool_count !== undefined ? ` · ${item.tool_count} tools` : ""}`
      : item.error || "Offline";
    text.append(node("strong", "", name), node("span", "", detail));
    card.append(dot, text);
    strip.append(card);
  }
}

async function loadAudit() {
  try {
    const query = state.currentCase
      ? `?case_id=${encodeURIComponent(state.currentCase.id)}&limit=200`
      : "?limit=200";
    const events = await api(`/api/web/audit${query}`);
    const list = $("#audit-list");
    list.replaceChildren();
    if (!events.length) {
      list.append(node("p", "muted", "No audit events."));
      return;
    }
    for (const item of events) {
      const event = node("article", "audit-event");
      event.append(
        node("time", "", formatTime(item.created_at)),
        node("span", "audit-case", item.case_id),
      );
      const detail = node("div", "");
      detail.append(
        node("strong", "", item.event),
        node("pre", "audit-detail", JSON.stringify(item.detail, null, 2)),
      );
      event.append(detail);
      list.append(event);
    }
  } catch (error) {
    toast(error.message);
  }
}

function switchView(view) {
  state.view = view;
  $$(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  $("#chat-view").classList.toggle("hidden", view !== "chat");
  $("#audit-view").classList.toggle("hidden", view !== "audit");
  if (view === "audit") loadAudit();
}

async function bootstrap() {
  bindEvents();
  try {
    const session = await api("/api/web/session");
    showApp(session);
    await loadCases();
    await refreshStatus();
    state.statusTimer = window.setInterval(refreshStatus, 30000);
  } catch {
    showLogin();
  }
}

function bindEvents() {
  $("#login-form").addEventListener("submit", login);
  $("#logout-button").addEventListener("click", logout);
  $("#new-case-toggle").addEventListener("click", () => {
    $("#new-case-form").classList.toggle("hidden");
  });
  $("#new-case-cancel").addEventListener("click", () => {
    $("#new-case-form").classList.add("hidden");
  });
  $("#new-case-form").addEventListener("submit", createCase);
  $("#chat-form").addEventListener("submit", sendMessage);
  $("#refresh-audit").addEventListener("click", loadAudit);
  $("#approval-form").addEventListener("submit", submitApproval);
  $("#approval-cancel").addEventListener("click", () => {
    state.pendingApprovalId = null;
    $("#approval-key").value = "";
    $("#approval-dialog").close();
  });
  $$(".tab").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
}

bootstrap();
