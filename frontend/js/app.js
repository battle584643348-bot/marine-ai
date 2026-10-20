/* 主应用：视图切换 + 聊天流式渲染 */
window.App = (function () {
  const state = { sessionId: "default", branch: "overall", busy: false };
  let WELCOME_HTML = "";
  let BRANCHES = [];

  function $(sel) { return document.querySelector(sel); }

  function refreshStatus() {
    API.get("/api/health").then((h) => {
      const dot = $("#statusDot");
      if (h.llm.ok) {
        dot.className = "dot ok";
        $("#statusText").textContent = h.llm.provider + " · " + (h.llm.model || "");
      } else {
        dot.className = "dot err";
        $("#statusText").textContent = h.llm.detail || "模型未就绪";
      }
      $("#modelHint").textContent = "(" + h.llm.provider + " · " + (h.llm.model || "") + ")";
    }).catch(() => {
      $("#statusDot").className = "dot err";
      $("#statusText").textContent = "后端未连接";
    });
  }

  function scrollBottom() {
    const m = $("#messages");
    m.scrollTop = m.scrollHeight;
  }

  /* ---------------- 分支 ---------------- */
  function branchById(id) {
    return BRANCHES.find((b) => b.id === id) || BRANCHES[0] || { id: "overall", name: "综合助手", icon: "⚓", desc: "", skills: [] };
  }
  function welcomeHtml(b) {
    const skills = (b.skills || []).length;
    return "<b>「" + b.name + "」分支已就绪</b> " + (b.icon || "") + "<br>" +
      (b.desc || "") + (skills ? "（本分支启用 " + skills + " 项技能）" : "") + "<br>" +
      "在这里提问将自动套用该分支的专业定位与技能集。";
  }
  async function renderBranches() {
    try {
      const data = await API.get("/api/chat/branches");
      BRANCHES = data.branches || [];
    } catch (e) { BRANCHES = []; }
    const list = $("#branchList");
    list.innerHTML = "";
    BRANCHES.forEach((b) => {
      const btn = document.createElement("button");
      btn.className = "branch-btn" + (b.id === state.branch ? " active" : "");
      btn.title = b.desc || "";
      btn.innerHTML = '<span class="b-ico">' + (b.icon || "•") + '</span>' +
        '<span class="b-name">' + b.name + '</span><span class="b-desc">' + (b.desc || "") + "</span>";
      btn.addEventListener("click", () => switchBranch(b.id));
      list.appendChild(btn);
    });
  }
  async function switchBranch(id) {
    if (state.branch === id) return;
    if (state.busy) { alert("当前对话进行中，请稍候再切换。"); return; }
    state.branch = id;
    await API.post("/api/chat/clear", { session_id: state.sessionId, branch: id }).catch(() => {});
    $("#messages").innerHTML = "";
    addMessage("system", welcomeHtml(branchById(id)));
    document.querySelectorAll(".branch-btn").forEach((btn, i) => {
      btn.classList.toggle("active", BRANCHES[i] && BRANCHES[i].id === id);
    });
    $("#modelHint").textContent = "(" + branchById(id).name + ")";
  }

  function addMessage(role, html) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + role;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = html || "";
    wrap.appendChild(bubble);
    $("#messages").appendChild(wrap);
    scrollBottom();
    return { wrap, bubble };
  }

  function sendMessage(text) {
    if (state.busy || !text.trim()) return;
    state.busy = true;
    setBusy(true);
    addMessage("user", MD.render(text));

    const a = addMessage("assistant", '<span class="thinking">思考中…</span>');
    const bubble = a.bubble;
    // 结构：meta 区（来源/技能芯片）+ 正文区（Markdown）
    const meta = document.createElement("div");
    const body = document.createElement("div");
    bubble.innerHTML = "";
    bubble.appendChild(meta);
    bubble.appendChild(body);
    let streamBuf = "";
    let tools = [];

    API.sseChat(text, state.sessionId, state.branch, (ev) => {
      if (ev.type === "grounding" && ev.sources && ev.sources.length) {
        const div = document.createElement("div");
        div.className = "src-line";
        div.textContent = "📚 知识库命中：" + ev.sources.join("、");
        meta.appendChild(div);
        scrollBottom();
      } else if (ev.type === "token") {
        streamBuf += ev.text;
        body.innerHTML = MD.render(streamBuf);
        scrollBottom();
      } else if (ev.type === "tool_start") {
        streamBuf = "";
        body.innerHTML = "";
        const chip = document.createElement("span");
        chip.className = "tool-chip";
        chip.textContent = "🧩 调用技能：" + ev.title;
        meta.appendChild(chip);
        tools.push(ev.title);
        scrollBottom();
      } else if (ev.type === "tool_end") {
        const line = document.createElement("div");
        line.className = "meta-line";
        line.textContent = "✔ " + ev.title + " 执行完成";
        if (ev.summary) {
          line.textContent += " — " + ev.summary.replace(/\n/g, " ").slice(0, 150);
        }
        meta.appendChild(line);
        scrollBottom();
      } else if (ev.type === "error") {
        body.innerHTML = "";
        const div = document.createElement("div");
        div.style.color = "var(--err)";
        div.textContent = "⚠ " + ev.message;
        meta.appendChild(div);
      }
    }).then((final) => {
      if (final && final.sources && final.sources.length) {
        const div = document.createElement("div");
        div.className = "src-line";
        div.textContent = "📎 依据来源：" + final.sources.join("、");
        meta.appendChild(div);
      }
      if (tools.length) {
        const div = document.createElement("div");
        div.className = "meta-line";
        div.textContent = "本轮调用技能：" + tools.join("、");
        meta.appendChild(div);
      }
      if (streamBuf) body.innerHTML = MD.render(streamBuf);
      state.busy = false;
      setBusy(false);
      scrollBottom();
    }).catch((err) => {
      body.innerHTML = "";
      const div = document.createElement("div");
      div.style.color = "var(--err)";
      div.textContent = "⚠ 请求失败：" + err.message;
      meta.appendChild(div);
      state.busy = false;
      setBusy(false);
      scrollBottom();
    });
  }

  function setBusy(b) {
    $("#btnSend").disabled = b;
    $("#input").disabled = b;
  }

  function switchView(name) {
    document.querySelectorAll(".nav-item").forEach((x) => x.classList.toggle("active", x.dataset.view === name));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
    if (name === "docs") window.Docs.load();
    if (name === "skills") window.Skills.load();
    if (name === "settings") window.Settings.load();
  }

  function init() {
    WELCOME_HTML = document.getElementById("welcome").querySelector(".bubble").innerHTML;

    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.dataset.view));
    });

    const input = $("#input");
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        $("#btnSend").click();
      }
    });
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 140) + "px";
    });
    $("#btnSend").addEventListener("click", () => {
      const v = input.value.trim();
      if (!v) return;
      input.value = "";
      input.style.height = "auto";
      sendMessage(v);
    });

    $("#btnNewChat").addEventListener("click", async () => {
      if (state.busy) return;
      if (!confirm("清空当前对话？")) return;
      await API.post("/api/chat/clear", { session_id: state.sessionId, branch: state.branch }).catch(() => {});
      $("#messages").innerHTML = "";
      addMessage("system", welcomeHtml(branchById(state.branch)));
    });

    window.Docs.bind();
    window.Settings.bind();
    renderBranches();
    window.Docs.load();
    window.Skills.load();
    window.Settings.load();
    refreshStatus();
    setInterval(refreshStatus, 30000);
  }

  return { init: init, refreshStatus: refreshStatus, getState: () => state };
})();
