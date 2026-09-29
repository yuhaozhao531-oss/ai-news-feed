# ai-news-feed

每 3 小时由 GitHub Actions 抓取 AI 官方一手资讯（OpenAI / Anthropic / Google DeepMind / Google AI / Hugging Face / NVIDIA / AWS / 通义千问 / arXiv），
用 AI 翻译成中文、打「对企业 AI 落地内容的价值」分，输出到 `data/news.json`，供 AI 图文工作台的「资讯」页读取。

- 加/删信息源：改 `sources.json`（任何 RSS/Atom 地址都行；`keywords` 过滤、`max` 限量）
- AI 评分：仓库 Settings → Secrets → Actions 添加 `AI_API_KEY`（默认 DeepSeek；换别家再加 Variables `AI_BASE_URL`、`AI_MODEL`）
- 手动运行：Actions → fetch-news → Run workflow；本地：`pip install feedparser requests && python fetch.py`
