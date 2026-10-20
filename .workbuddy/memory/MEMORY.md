# 项目长期记忆 · marine-ai（海工智舱）

## ★ 最高优先级约规：本项目是用户的"全栈学习载体"
用户开发此项目的目的有两个，**同等重要**：
1. 得到一个能用的海工调试 AI 工作台；
2. **通过开发它成为全栈软件开发者**。

因此：**凡是涉及修改/开发本项目的请求，必须先讲底层原理，再动手。**
固定讲解格式（六段，缺一不可）：
1. **这一层是什么** —— 从最底层讲起：进程/事件循环 → 网络协议 → ASGI → 框架 → 业务 → 前端，
   指明当前改动落在第几层、它下面依赖什么。
2. **本项目里谁在实现它** —— 精确到 `文件:行号` 与函数名，不泛泛而谈。
3. **为什么这么设计** —— 取舍与被放弃的替代方案（例如为什么用 SSE 而不是 WebSocket）。
4. **改动方案** —— 要改哪几行、为什么改这里而不是别处。
5. **动手 + 验证** —— 改完给出可执行的验证命令或手动步骤。
6. **一句话复述** —— 用一句不含行话的话总结这次学到了什么。

额外要求：
- 讲代码时同步讲**工具链与工程习惯**（git、调试器、日志、测试、依赖管理），
  因为全栈不只是会写业务逻辑。
- 发现坏味道要当场指出并解释原因（如 `innerHTML` 的 XSS 风险、无版本管理、
  内存态会话、硬编码路径），不要因为"能跑"就放过。
- 不要一次倒完所有知识；按用户当前改动的那一层讲深，上层只给坐标。

## 项目定位
本地部署的海工/船舶调试领域 AI 助手。前端零构建 SPA + FastAPI + 自建 RAG + 技能插件体系。
8 个专业分支（data/branches.json），7 个技能（含 diagram_annotate 单线图标注）。

## 技术栈与版本事实
- Python 3.13 / FastAPI / uvicorn / httpx / pypdf / python-docx / openpyxl / pymupdf
- 前端：原生 HTML+CSS+JS，无框架无打包；自带 markdown.js
- 模型：Ollama(本地) / OpenAI 兼容 / Mock 三通道，auto 模式自动降级
- 目录：backend/app/{core,agent,rag,skills,api} · frontend · data · generated · docs

## 已确认的工程缺口（教学时可作为案例）
1. /api/files/{filename} 不支持子路径 → generated/diagram_mark 产物无法下载；
   前端 app.js tool_end 未渲染 meta.path，file 类技能结果等于"看得见摸不着"。
2. requirements.txt 缺 rapidocr_onnxruntime（diagram_annotate sld 模式依赖）。
3. diagram_annotate.DEFAULT_SCHEDULE 硬编码桌面绝对路径。
4. 会话历史为内存 dict，重启即丢，无多会话管理。
5. 前端用 innerHTML 渲染模型输出 → 存在 XSS 面。
6. 无 .git、无测试、无日志规范。
7. 根目录 README.md 已过期，以 README.txt 为准。
