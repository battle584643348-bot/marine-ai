================================================================================
                       海工智舱 · Marine AI  项目说明
                  本地部署的海工/船舶调试领域 AI 助手
================================================================================
文件位置   E:\AI LCP\marine-ai
文档版本   2026-10-20（基于当前代码与数据实测整理，非规划稿）
技术栈     Python 3.11+ / FastAPI / 原生 HTML+CSS+JS（零构建）/ RAG / Ollama
运行方式   python run.py  →  http://127.0.0.1:8000
================================================================================


[1] 一句话说清这是什么
--------------------------------------------------------------------------------
这是一个"给自己用的"本地 AI 工作台：把一个海工船舶调试工程师日常要干的
七类活儿（查项目情报、查标准条款、算电气参数、读图纸、写 SOP/ITR、
出 Excel 清单、整理文件），全部收进一个本地网页里，用大模型 + 7 个固
定技能去完成。

三个设计取舍决定了它长现在这样：
  · 本地优先     —— 涉密图纸和项目资料不上云，支持 Ollama 全离线推理
  · 零构建前端   —— 不装 Node、不打包，改完 JS 刷新浏览器就生效
  · 技能确定性   —— 计算、标注、出表这类活儿不交给模型"生成"，而是走
                    写死的 Python 公式/库，模型只负责理解意图和调参数，
                    避免算错数、编标准


[2] 你到底在干什么（从项目本身反推的业务背景）
--------------------------------------------------------------------------------
docs/海工问题分类.html 是这套系统的"需求来源"，里面写明：
  职业      海工船舶调试工程师
  工作内容  PLC 编程 / 设备调试 / 技术程序撰写
  协作环境  国际化团队，中英双语
  常驻      江苏南通 · 海工项目现场

七类真实需求 → 系统里的八个专业分支（data/branches.json）：
  1 行业项目与市场情报   FPSO/FSO 造价、工期、建造地、合同归属
        → 分支「项目情报」(project-intel)
  2 标准与规范溯源       ASME / IEC / GB/T 具体条款，拒绝"行业惯例"
        → 分支「标准溯源」(standard)
  3 电气/机械理论与实操  软起动、SFC 静止变频、谐波相位、继保定值
        → 分支「电气理论」(electrical)
  4 图纸/文档智能化      原理图 OCR、符号识别、单线图按系统标注
        → 分支「图纸智能」(drawing)
  5 工程技术文书         SOP / ITR-A / Punch List / 继保定值清单
        → 分支「文书撰写」(docs)
  6 办公自动化           Excel 匹配、批量文件、批处理脚本
        → 分支「办公自动化」(automation)
  7 本地 AI 系统建设     本项目自身（2026-10-13 起）
        → 分支「本地AI系统」(ai-system)
  ＋ 综合助手 (overall)  全技能默认分支

从 generated/ 里的真实产出可以确认在做的具体项目：
  · 1008B-OSE-D-EL-SD-00012  A LIGHTING & SMALL POWER SINGLE LINE
    DIAGRAM - M01 CRUDE OIL TREATMENT MODULE（照明/小动力单线图）
  · 1008B-OSE-D-EL-SD-00005  0 690V TOPSIDE SWITCHBOARD 1 SINGLE
    LINE DIAGRAM（690V 上部模块开关柜单线图）
  · 电缆清册  总的电缆清册_系统划分补全_20261012.xlsx（sheet: cable schedule）
  → 即：在给 FPSO/FSO 类项目的电气单线图做"按系统划分 + 标注"的活，
    并用清册（Cable Schedule）交叉核对图纸，产出未匹配电缆清单。


[3] 现在能干什么：7 个技能
--------------------------------------------------------------------------------
技能不是"提示词模板"，是后端可执行的 Python 模块，模型只能通过
{"tool":..., "args":{...}} 这一行 JSON 去调用它。

  1) knowledge_search   知识库检索
     本地 TF-IDF 关键词检索（中文二字组切词）+ 可选语义向量混合召回
     权重：关键词 0.6 / 语义 0.4；精确词命中再 ×1.25 加权
     返回原文片段 + 来源文件名
  2) standard_lookup    标准速查
     data/standards.json 内置 28 条国际/国内标准索引（IEC/IEEE/GB/ASME/API）
     给适用范围、关键要求、条款主题；明确"以官方最新版原文为准"
  3) sop_generator      SOP / ITR 生成
     11 节行业模板 + 未提供信息用【待填】占位，中/英双语
  4) calc_engine        工程计算（确定性公式，不靠模型算）
     voltage_drop  三相/单相压降 √3·I·L·(R·cosφ + X·sinφ)
     cable_area    按允许压降反选电缆截面 + 标准截面建议
     harmonic_thd  THD 计算 + IEEE 519 / GB/T 14549 限值校核
     power_factor  无功补偿容量 Qc 与电容值
     soft_starter  限流起动电流/转矩校核
     resonance     电容器并联谐振频率，5/7/11/13 次风险判定
  5) translate          中英技术翻译（内置 40+ 海工术语）
  6) excel_report       Excel 报告：punch_list / test_values / general
     openpyxl 样式化输出（表头配色、冻结首行、列宽）
  7) diagram_annotate   单线图按系统标注（本项目最"重"的技能，833 行）
     mode=lighting  照明/配电单线图：识别 CKT/LOOP 回路，框配电板与回路，
                    打 <系统号>-<回路号> / LOOP-<回路号> 标签
     mode=sld       开关柜单线图：识别 P- 动力电缆馈线 + 尾设备标签，
                    框"电缆+下游设备"，标母线 BUSBAR，栅格图自动 OCR，
                    并把识别结果回填清册副本（新增「SLD识别结果」表）
     特性：所有框和文本框都是 PDF 注释（Annotation），可在福昕/
           PDF-XChange 里选中、拖动、双击改字，不烘焙进图纸
     产物：*_系统标注.pdf ＋ 未匹配电缆清单.xlsx（＋ 清册_含SLD识别.xlsx）

当前启用状态（data/user_config.yaml）：7 个全部启用。
注意 config.yaml 里只写 6 个，运行时被 user_config 覆盖成 7 个。


[4] 目录结构（按实际文件）
--------------------------------------------------------------------------------
marine-ai/
├─ run.py                 启动入口，读 config.yaml 拿 host/port
├─ config.yaml            基础配置（LLM / 服务 / RAG / Agent / 技能开关）
├─ requirements.txt       9 个依赖：fastapi uvicorn httpx pypdf python-docx
│                         openpyxl pyyaml python-multipart pymupdf
├─ start.bat              Windows 双击启动（自动检测依赖，缺了先 pip install）
├─ start-dev.bat          开发用：先 taskkill 占用 8000 的进程，再启动
├─ .vscode/               F5 断点调试配置 + 编辑器设置（UTF-8 / 缩进 / 排除索引）
├─ README.md              早期 Markdown 版说明（内容略旧，见 [10]）
├─ README.txt             本文件
│
├─ backend/app/
│  ├─ main.py             FastAPI 入口，注册 4 个 router，把 frontend/ 挂到 "/"
│  ├─ core/
│  │  ├─ config.py        config.yaml + data/user_config.yaml 深度合并，
│  │  │                   支持 "llm.ollama.model" 点路径取值
│  │  ├─ llm.py           三家 Provider：Ollama / OpenAI兼容 / Mock，
│  │  │                   auto 模式＝探测本机 Ollama → 有 key 走 API → 否则 Mock
│  │  └─ embeddings.py    可选语义向量（走 Ollama /api/embed，默认关闭）
│  ├─ agent/
│  │  ├─ loop.py          Agent 主循环 + 分支 + 会话 + 技能调用协议解析
│  │  └─ context.py       传给技能的 ctx（配置、路径、provider、索引）
│  ├─ rag/
│  │  ├─ parsers.py       PDF/DOCX/XLSX/TXT/MD/CSV 解析（编码自动嗅探）
│  │  ├─ chunker.py       切块（默认 800 字 / 重叠 120）
│  │  └─ index.py         纯 Python TF-IDF 索引 + 混合检索 + JSON 持久化
│  ├─ skills/
│  │  ├─ base.py          技能基类（name/title/description/parameters/run）
│  │  ├─ registry.py      pkgutil 自动扫描本目录，发现 Skill 子类即注册
│  │  ├─ knowledge_search.py / standard_lookup.py / sop_generator.py
│  │  ├─ calc_engine.py / translate.py / excel_report.py
│  │  └─ diagram_annotate.py   单线图标注（lighting + sld 双模式）
│  └─ api/
│     ├─ chat.py          POST /api/chat（SSE）、/clear、/history、/branches
│     ├─ documents.py     上传 / 列表 / 删除 / 重建索引 / 查看片段
│     ├─ skills.py        技能列表与启停
│     └─ settings.py      /api/config、/api/health、/api/files/{filename}
│
├─ frontend/              零构建 SPA（共 832 行）
│  ├─ index.html          侧边栏（分支 + 4 个视图）+ 对话/知识库/技能/设置
│  ├─ css/style.css
│  └─ js/ api.js（fetch + SSE 解析）/ app.js（视图与流式渲染）
│        docs.js / skills.js / settings.js / markdown.js（自带轻量 MD 渲染）
│
├─ data/
│  ├─ branches.json       8 个分支定义：id/名称/图标/技能子集/专属系统提示词
│  ├─ standards.json      28 条标准索引（id/title/tags/scope/key_points）
│  ├─ user_config.yaml    页面「设置」写入的覆盖层（当前只存了技能开关）
│  ├─ index.json          RAG 索引（当前 1 份文档 / 4 个片段）
│  ├─ sample/             演示文档：低压电动机软起动器调试程序.md
│  └─ uploads/            上传原件落盘目录
│
├─ generated/             技能产出（3.5MB）
│  ├─ 1791899950680_punch_list.xlsx        Punch List 缺陷清单
│  ├─ lighting_mark/…_系统标注.pdf + 未匹配电缆清单.xlsx
│  └─ diagram_mark/…_系统标注.pdf + 未匹配电缆清单.xlsx
│                   + 清册_含SLD识别.xlsx（cable schedule + SLD识别结果）
│
└─ docs/                  10 份自建 HTML 文档（浏览器直接打开）
   architecture.html              系统架构图
   工程结构总览.html              目录与模块说明
   代码编辑导览.html              改哪里的代码
   开发环境搭建.html / 开发环境部署.html
   技能注册表架构.html            技能自动发现机制
   diagram-skill-合并技能.html    两个标注脚本如何合成一个技能
   github-skills-生态.html        Agent Skills 生态对照
   海工问题分类.html              7 类需求梳理（本系统的需求源）
   离线可用方案.html              各技能离线能力盘点与落地三步


[5] 怎么启动
--------------------------------------------------------------------------------
首次：
  双击 start.bat            （自动 pip install -r requirements.txt，然后启动）
日常：
  python run.py             或双击 start-dev.bat（会先杀掉占用 8000 的进程）
  VS Code 里按 F5          （走 .vscode/launch.json，可打断点）
带热重载开发：
  python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
换端口：
  python run.py --port 9000   或改 config.yaml 的 server.port

编辑生效规则：
  frontend/**            保存 → 浏览器刷新（必要时 URL 加 ?v=时间戳）
  backend/**/*.py        保存 → 重启服务
  data/branches.json     重启后生效
  data/standards.json    重启后生效
  页面「设置」里的改动     立即生效（写入 data/user_config.yaml 并重建 runtime）


[6] 模型怎么接（四条路）
--------------------------------------------------------------------------------
config.yaml → llm.provider，四种取值：
  auto    默认。启动时探测 http://127.0.0.1:11434（Ollama）
          → 通：用本地模型
          → 不通但有 API Key：用 OpenAI 兼容接口
          → 都没有：Mock 离线占位（能跑通全链路，但不是真回答）
  ollama  强制本地。需先 ollama pull qwen2.5:14b（16GB 内存建议 7b/3b）
  openai  任意 OpenAI 兼容接口：DeepSeek / 通义 / GLM / Moonshot
          填 base_url + api_key + model
  mock    离线联调，固定返回占位文本

API Key 优先级：环境变量 MARINE_LLM_API_KEY > config.yaml 明文
前端永远只看到 ***（settings.py 里的 _mask 脱敏）

语义检索（可选）：ollama pull bge-m3，然后把
  llm.ollama.embedding_enabled 设为 true，并重建索引（POST /api/documents/reindex）


[7] 一次对话的完整链路（排障必看）
--------------------------------------------------------------------------------
 浏览器 POST /api/chat {message, session_id, branch}
   │
   ├─ Agent.run_turn()
   │   ① RAG 自动接地：拿用户原话检索 index.json，top_k=5 片段
   │      命中就先推一个 {type:"grounding", sources:[文件名...]}
   │      （前端显示"📚 知识库命中：xxx"）
   │   ② 组装 messages = [分支系统提示 + 知识上下文] + 最近 12 轮历史 + 本次提问
   │      系统提示里嵌入当前分支可用技能的 name/title/参数说明
   │   ③ provider.stream() 流式输出，逐片推 {type:"token"}
   │   ④ 输出结束后整体正则匹配，看是不是一行技能调用 JSON
   │      命中 → 推 {tool_start} → await skill.run() → 推 {tool_end}
   │             → 把"[技能「x」执行结果] ..."当 user 消息塞回 messages，继续循环
   │      ｜单轮最多连续 4 次（agent.max_tool_rounds），超了强制收尾
   │   ⑤ 不是 JSON → 视为最终答案，推 {type:"done", sources, tools}
   │
   └─ FastAPI 包成 SSE（data: {json}\n\n），前端 api.js 按空行切事件

会话：纯内存 dict，key = "sessionId::branch"，重启即清空；按分支隔离。
技能调用失败不中断对话，会以 [技能执行错误] 文本回灌给模型自己解释。


[8] 关键配置项速查
--------------------------------------------------------------------------------
服务     server.host / server.port
模型     llm.provider / llm.temperature(0.3) / llm.max_tokens(4096)
本地     llm.ollama.base_url / model(qwen2.5:14b) / embedding_model(bge-m3)
云端     llm.openai_compatible.base_url / api_key / model(deepseek-chat)
检索     rag.chunk_size(800) / chunk_overlap(120) / top_k(5) / search_top_k(8)
         rag.hybrid_weight_sparse(0.6) / dense(0.4)
         rag.upload_dir(data/uploads) / index_path(data/index.json)
Agent    agent.max_tool_rounds(4) / history_turns(12)
技能     skills.enabled 列表（页面「技能」面板开关，写回 user_config.yaml）
产出     files.generated_dir(generated)


[9] 加一个新技能（3 步，不用改注册表）
--------------------------------------------------------------------------------
  1. 在 backend/app/skills/ 新建 xxx.py
  2. 写一个继承 Skill 的类，给 name / title / description / parameters，
     实现 async def run(self, ctx, args) -> {"type":"text"|"file", "content":...}
  3. 重启 → 自动被发现 → 技能面板出现 → 若要在某分支可用，
     把 name 加进 data/branches.json 对应分支的 skills 数组

约束：
  · 返回 type=file 时，content 放文件名，meta 放 {"path","filename","stats"}
  · registry._discover() 用 pkgutil 扫同目录，文件名不要以 _ 开头
  · 目录名必须已存在，否则整块技能不会被注册（会抛 import 异常）


[10] 当前状态快照（2026-10-20 实测）
--------------------------------------------------------------------------------
已跑通：8 分支 / 7 技能注册 / 前端四视图 / SSE 流式 / 文档上传与检索
        diagram_annotate 已在真实图纸上产出过 4 轮结果（见 generated/）
当前模型：provider=auto，本机未装 Ollama 且无 API Key → 实际运行在 Mock
          所以对话内容是占位文本，但技能本身不依赖模型，可单独验证
知识库：仅 1 份示例文档（4 片段），实质是空库
索引里记录的文档路径仍是旧的 Doubao\chats\... 绝对路径（不影响检索，
          但说明索引是从旧目录复制过来的，可清空重建）
代码规模：backend 2735 行 Python（diagram_annotate 单文件占 833 行）
          / frontend 832 行 / docs 10 份 HTML


[11] 已知缺口（诚实清单，按影响排序）
--------------------------------------------------------------------------------
1. 生成文件没有下载入口
   /api/files/{filename} 只拼接 generated 根目录，不接受子路径；而
   diagram_annotate 的产物在 generated/diagram_mark/ 子目录里 → 前端
   拿不到链接。且 app.js 的 tool_end 只渲染文字摘要，没渲染 meta.path。
   → 修法：接口改成接受相对路径并做越界校验，前端在 tool_end 里渲染
     <a href="/api/files/...">；或技能产出统一写到 generated 根目录。

2. 缺 OCR 依赖但代码里用了
   diagram_annotate.sld 模式遇到栅格化图纸会调 rapidocr_onnxruntime，
   但 requirements.txt 没列这个包。没装时只会打印警告并跳过 OCR 标注。
   → pip install rapidocr_onnxruntime（约几百 MB，按需装）

3. 清册默认路径硬编码
   DEFAULT_SCHEDULE = C:\Users\zhang\Desktop\总的电缆清册_系统划分补全_20261012.xlsx
   写死在 diagram_annotate.py 里，换机器/改文件名就失效。
   → 应移到 config.yaml，或强制每次由对话传 schedule 参数

4. 会话不持久
   内存 dict，重启清空；无多会话管理、无标题、无导出。
   → 落盘 SQLite 是最小改动方案

5. 扫描件 PDF 知识库无 OCR
   parsers._parse_pdf 用 pypdf 抽文字，扫描件会抛"未提取到文字"。
   （注意：这与技能 7 的 OCR 是两条独立通道，别混）

6. README.md 已过期
   只写 6 个技能、7 个分支，未提 diagram_annotate 和「项目情报」等；
   本 README.txt 反映的是当前真实代码。

7. 无版本管理
   目录下没有 .git，generated/ 里 3.5MB 历史产物也没归档规则。


[12] 快速自检（改完代码验证用）
--------------------------------------------------------------------------------
  curl http://127.0.0.1:8000/api/health
       → 看 llm.provider / rag.chunks / skills.enabled 是否符合预期
  curl http://127.0.0.1:8000/api/chat/branches
       → 看 8 个分支是否都读到
  node --check frontend/js/app.js
       → 前端语法检查（不需要打包）
  python -c "import backend.app.main"
       → 后端导入自检，能抓出技能模块 import 错误

================================================================================
本文件描述的是"代码现在是什么样"，不是"计划做成什么样"。
改动代码后请同步更新对应段落，尤其是 [3][4][10][11]。
================================================================================
