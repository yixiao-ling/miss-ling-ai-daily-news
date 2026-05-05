# Miss Ling AI 日报

每日自动采集 AI 行业资讯，经 Claude AI 提炼摘要，生成精华日报。

## 数据源
- Hacker News（AI 相关热帖）
- Product Hunt（AI 类目新品）
- GitHub Trending（AI 相关仓库）
- X KOL 推文（手动维护 data/x_kol.json）
- 36kr / 虎嗅 / AIbase（RSS）

## 本地运行
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python -m src.main
```

## 部署
1. Fork 本仓库
2. Settings → Pages → Source 选择 main 分支 /docs 目录
3. Settings → Secrets → 添加 ANTHROPIC_API_KEY
4. Actions 自动每天 09:00（北京时间）运行

## 手动触发
Actions → Daily Digest → Run workflow
