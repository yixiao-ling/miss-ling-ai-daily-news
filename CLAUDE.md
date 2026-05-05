# Miss Ling AI 日报

## 项目简介
一款面向 AI 行业从业者的每日资讯聚合工具。自动从 Hacker News、Product Hunt、GitHub Trending、X KOL 推文 JSON、36kr/虎嗅/AIbase RSS 中采集内容，经本地关键词过滤、去重、Claude AI 摘要处理，生成每日精华 HTML 简报，部署在 GitHub Pages 上，用浏览器直接访问。

## 技术栈
- 语言：Python 3.11
- 采集：requests, feedparser, PRAW（Reddit 已移除，保留接口以备扩展）
- AI 摘要：anthropic SDK（claude-sonnet-4-20250514）
- 模板渲染：Jinja2
- 自动化：GitHub Actions（cron 每日 UTC 01:00 触发）
- 部署：GitHub Pages（docs/ 目录）

## 目录结构
miss-ling-ai-daily/
├── src/
│   ├── fetch_sources.py     # 各数据源采集模块
│   ├── filter.py            # 本地关键词过滤 & 去重
│   ├── summarize.py         # Claude AI 摘要生成
│   ├── render.py            # HTML 页面生成
│   └── main.py              # 入口，串联所有模块
├── templates/
│   └── daily.html           # Jinja2 HTML 模板
├── data/
│   └── x_kol.json           # 手动维护的 KOL 推文 JSON
├── docs/
│   ├── index.html           # 最新一期（GitHub Pages 入口）
│   └── archive/             # 历史存档 YYYY-MM-DD.html
├── .github/workflows/
│   └── daily.yml            # GitHub Actions 定时任务
├── requirements.txt
└── README.md

## 关键规则
- 称呼 Yixiao（每次回复前必须使用「Yixiao」作为称呼）
- 遇到不确定的设计决策，必须先询问 Yixiao，不得直接行动
- 不写兼容性代码，除非 Yixiao 主动要求
- 每完成一个功能模块必须 git commit，commit message 清晰描述改动
- 所有 API Key 通过环境变量注入，绝不硬编码

## 构建与验证
- 本地运行：`python src/main.py --dry-run`（不调用 Claude API，用 mock 数据验证流程）
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
