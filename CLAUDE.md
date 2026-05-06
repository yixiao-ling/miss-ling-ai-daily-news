# Miss Ling AI 日报

## 项目简介
一款面向 **AI 产品经理**的每日资讯聚合工具。自动从 Hacker News、Product Hunt、GitHub Trending、X KOL 推文 JSON、36kr/虎嗅/AIbase RSS 中采集内容，经本地关键词过滤、去重、Claude AI 摘要处理，生成每日精华 HTML 简报，部署在 GitHub Pages 上，用浏览器直接访问。

目标受众特征：懂技术原理、关注产品落地、重视商业价值、需要快速判断信息优先级。

## 技术栈
- 语言：Python 3.11
- 采集：requests, feedparser, PRAW（Reddit 已移除，保留接口以备扩展）
- AI 摘要：anthropic SDK（claude-sonnet-4-6）
- 模板渲染：Jinja2
- 自动化：GitHub Actions（cron 每日 UTC 01:00 触发）
- 部署：GitHub Pages（docs/ 目录）

## 目录结构
ai-news/
├── src/
│   ├── __init__.py
│   ├── schema.py            # RawItem / DigestedItem dataclass 定义
│   ├── fetch_sources.py     # 5个数据源采集：HN / PH / GitHub / X / RSS
│   ├── filter.py            # Module 2：关键词过滤 & 阈值过滤 & URL去重 & 截量
│   ├── summarize.py         # Module 3：Claude AI 摘要生成（prompt caching + fallback）
│   ├── render.py            # Module 4/5：Jinja2 → docs/index.html + docs/archive/YYYY-MM-DD.html
│   └── main.py              # 入口：--dry-run / --source 参数，串联所有模块
├── templates/
│   └── daily.html           # Module 4：Jinja2 HTML 模板（内联 CSS/JS，零外部依赖）
├── data/
│   └── x_kol.json           # KOL 推文数据（10人/24条，likes>=30过滤后19条）
├── docs/
│   ├── .gitkeep
│   └── archive/
│       └── .gitkeep         # 历史存档目录，存放 YYYY-MM-DD.html
├── .github/workflows/
│   └── daily.yml            # Module 7 占位：GitHub Actions cron 定时任务
├── .gitignore
├── requirements.txt         # anthropic, feedparser, requests, bs4, jinja2
├── README.md
└── CLAUDE.md

## 关键规则
- 称呼 Yixiao（每次回复前必须使用「Yixiao」作为称呼）
- 遇到不确定的设计决策，必须先询问 Yixiao，不得直接行动
- 不写兼容性代码，除非 Yixiao 主动要求
- 每完成一个功能模块必须 git commit，commit message 清晰描述改动
- 所有 API Key 通过环境变量注入，绝不硬编码

## 构建与验证
- 本地运行：`python src/main.py --dry-run`（跳过 filter + Claude，用原始数据渲染，验证采集层 + 模板渲染）
- 正式运行：`python src/main.py`
- 验证方式：运行后打开 `docs/index.html`，检查页面是否正常渲染，卡片数据是否完整
- GitHub Actions：push 后在 Actions tab 查看运行日志

## 环境变量
- ANTHROPIC_API_KEY：必须，Claude API 密钥
- REDDIT_CLIENT_ID：可选，Reddit API（当前未启用）
- REDDIT_SECRET：可选，Reddit API（当前未启用）

## 注意事项
- X KOL 数据通过 data/x_kol.json 手动注入，脚本直接读取，无需 Twitter API
- GitHub Trending 通过抓取页面获取，若结构变化需更新解析逻辑
- Product Hunt 使用官方 Atom feed，无需 API Key
- HN 使用 Algolia Search API，免费无需 Key
- Claude API 调用失败时降级展示原标题+截断摘要，不阻塞页面生成
- summarize.py 设计决策（Module 3）：
  - 模型：claude-sonnet-4-6（claude-sonnet-4-20250514 在当前账号 404，已弃用）
  - system prompt 用 cache_control: ephemeral 标记，30条/批复用同一缓存，降低 token 成本
  - 顺序处理，条目间 sleep 0.5s 避免 rate limit
  - 降级策略：API key 缺失/tool_use 解析失败/API 异常，返回 summary_zh=原文前150字，其余字段为空/默认值
  - 结构化输出：使用 tool_use + tool_choice={"type":"tool","name":"save_digest"} 强制输出，response.content 中找 type=="tool_use" 的 block，直接读 .input（已是 dict），无需任何 JSON 解析，从根本上消除 unescaped 引号导致的解析失败
  - prompt 面向 AI 产品经理视角，8 个字段通过 tool input_schema 强制类型+必填（见 DigestedItem）
- filter.py 设计决策（Module 2）：
  - URL 去重只剥离 utm_* 参数，fragment 保留
  - score 阈值：hn>=50，github>=20，x>=30，其余 source 为 0
  - aibase 跳过关键词过滤（全站为 AI 内容）
  - truncate 用 round-robin 交错（先各 source 取前 10，再轮询合并到 40），避免 RSS/PH 被 GH/X 的高 score 挤出
  - --dry-run 跳过 filter + Claude（所有非纯采集步骤），保留原始条目用于调试采集层
- render.py 设计决策（Module 4/5）：
  - Jinja2 autoescape=True（防 XSS），format_time 自定义过滤器（ISO→MM-DD HH:mm）
  - category_pills 按固定顺序：模型能力 → AI产品 → 商业动态 → 开源生态 → 行业落地 → 其他
  - 筛选栏不显示「其他」分类按钮，「其他」内容仅在「全部」下可见
  - 写入 docs/index.html（覆盖）+ docs/archive/YYYY-MM-DD.html（覆盖，每日一份）
  - 空 items 时渲染"今日暂无内容"提示页，不报错退出
  - --dry-run 模式用 _raw_to_fallback() 生成 DigestedItem 占位，验证模板不崩
- templates/daily.html 设计决策：
  - 字体：标题用 Space Grotesk（Google Fonts），标签/时间戳/按钮/标签用 JetBrains Mono；均有系统字体 fallback
  - 配色：背景 #0a0a0f 极暗系；分类颜色编码：蓝=#3b82f6(AI产品)、紫=#8b5cf6(商业动态)、绿=#10b981(开源生态)、橙=#f97316(行业落地)、紫罗兰=#a78bfa(模型能力)
  - 重要度：信号强度条（5档高度渐变）替代星级，颜色跟随分类
  - 卡片左侧边框：hover 时亮起分类色（CSS custom property --card-accent 内联注入）
  - So What 按钮：终端风格，CSS ::before 注入 "> " 前缀
  - 筛选 tab：JetBrains Mono 大写，矩形边框，激活态显示分类色

## DigestedItem 字段说明
| 字段 | 类型 | 说明 |
|------|------|------|
| raw | RawItem | 原始采集数据 |
| summary_zh | str | 50-100字中文摘要 |
| eli5 | str | 2-3句大白话，面向非技术人 |
| use_cases | list | 具体应用场景，2-4条 |
| tags | list | 关键词标签，2-4个 |
| importance | int | 1-5分，AI产品经理视角打分 |
| title_zh | str | 中文标题（原文非中文时翻译，中文则原样） |
| category | str | 分类：模型能力/AI产品/商业动态/开源生态/行业落地/其他 |
| so_what | str | 100-150字影响分析，AI产品经理视角 |
