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

        // ===== 生成的文件：渲染成可点击的下载链接 =====
        // ev.files 由后端 loop.py 的 _result_files() 产生，形如
        //   [{ name: "未匹配电缆清单.xlsx", url: "/api/files/diagram_mark/xxx.xlsx" }]
        // 纯文本技能（翻译、检索）不会有这个字段，此时 ev.files 是 undefined。
        //
        // Array.isArray 比 `ev.files && ev.files.length` 更严格：字符串也有 .length，
        // 如果后端某天误传了字符串，前者会安全跳过，后者会去遍历字符串的每个字符。
        if (Array.isArray(ev.files) && ev.files.length) {
          const fileRow = document.createElement("div");
          fileRow.className = "meta-line";

          // forEach 是数组的遍历方法；用普通 function 而不是箭头函数，
          // 是为了和这个文件里其他回调的风格保持一致（这里用不到 this，两者等价）
          ev.files.forEach(function (f) {
            // 防御式取值：后端字段缺失时得到空串，不会因为 f.url 是 undefined 而抛错
            const url = String((f && f.url) || "");

            // ★ 白名单校验：只允许站内 /api/files/ 开头的地址。
            //   为什么要校验？因为 a.href = "javascript:alert(1)" 在浏览器里是合法的，
            //   点击就会执行脚本。这个值虽然来自我们自己的后端，但一旦后端被注入
            //   （比如技能参数里混进了攻击者控制的字符串），这里就是最后一道闸门。
            //   「不信任任何外部输入」这条原则，对自家后端也要留一份。
            if (!url.startsWith("/api/files/")) return;

            // 【为什么全程用 createElement / textContent，而不用 innerHTML 拼字符串】
            //   假设文件名是 <img src=x onerror=alert(document.cookie)>，
            //   写成 el.innerHTML = '<a href="...">' + f.name + '</a>' 时，
            //   浏览器会把这个文件名当成 HTML 解析，onerror 里的脚本立刻执行 ——
            //   这就是 XSS（跨站脚本）。而某个模型若被诱导输出这样的文件名，
            //   文件就真的会被这样创建。
            //   textContent 的语义是「这里的字符全部当纯文本」，浏览器绝不会解析标签，
            //   所以它是天然安全的。代价只是不能写 HTML 标签，而链接本来就要靠
            //   createElement('a') 来建，正好不需要 innerHTML。
            const a = document.createElement("a");
            a.className = "file-link";          // 复用 style.css:104 已定义的样式
            a.href = url;                       // 相对地址，浏览器自动补上当前域名
            a.setAttribute("download", "");     // 提示浏览器「下载」而不是「跳转打开」
            a.textContent = "⬇ 下载 " + String((f && f.name) || "生成的文件");
            a.style.display = "inline-block";
            a.style.marginTop = "4px";
            a.style.marginRight = "12px";

            fileRow.appendChild(a);
          });

          // 只有真的加进去过链接才挂到界面上，避免出现一个空白的行
          if (fileRow.childNodes.length) meta.appendChild(fileRow);
        }

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
