"""抓取官方一手 AI 资讯 → 去重 → （可选）AI 翻译 + 打相关度 → data/news.json

环境变量（可选，不配就只抓不评分）：
  AI_API_KEY   兼容 OpenAI 格式的 key（默认 DeepSeek）
  AI_BASE_URL  默认 https://api.deepseek.com
  AI_MODEL     默认 deepseek-chat
"""
import calendar, html, json, os, re, time
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "news.json"
KEEP_DAYS = 30          # news.json 里保留多久
NEW_WITHIN_DAYS = 14    # 只收这么多天内发布的
UA = "Mozilla/5.0 (ai-news-feed; +https://github.com)"

PERSONA = ("读者是一位做『企业 AI 落地咨询 + 企业 AI 培训』的博主，客户是中小企业老板、管理层、HR/培训负责人。"
           "他需要能拿来做内容、给老板讲清楚『这对企业意味着什么』的一手信息。")


def clean(s, n=None):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] if n else s


def fetch_source(src):
    r = requests.get(src["url"], headers={"User-Agent": UA}, timeout=40)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    cutoff = time.time() - NEW_WITHIN_DAYS * 86400
    items = []
    for e in feed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        ts = calendar.timegm(t) if t else time.time()
        if ts < cutoff:
            continue
        title, summary = clean(e.get("title")), clean(e.get("summary") or e.get("description"), 600)
        if src.get("keywords"):
            text = (title + " " + summary).lower()
            if not any(k in text for k in src["keywords"]):
                continue
        link = e.get("link") or ""
        if not link or not title:
            continue
        items.append({"id": link, "source": src["id"], "sourceName": src["name"], "title": title,
                      "link": link, "summary": summary, "ts": int(ts)})
    items.sort(key=lambda x: -x["ts"])
    return items[: src.get("max", 30)]


def ai_enrich(items):
    key = os.environ.get("AI_API_KEY")
    if not key or not items:
        return
    base = (os.environ.get("AI_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("AI_MODEL") or "deepseek-chat"
    for i in range(0, len(items), 12):
        batch = items[i:i + 12]
        listing = "\n".join(f'{j}. [{x["sourceName"]}] {x["title"]} —— {x["summary"][:300]}' for j, x in enumerate(batch))
        prompt = (f"{PERSONA}\n\n下面是一批官方发布的资讯。对每条输出：\n"
                  "- zh：准确的中文标题（≤30字，不夸张）\n"
                  "- brief：一句话说清发布了什么（≤60字，只写原文有的事实）\n"
                  "- why：对企业老板意味着什么（≤40字；没关系就写空字符串）\n"
                  "- score：对这位博主做内容的价值 0-10（纯学术/纯开发者细节/营销软文给低分，"
                  "新模型能力、价格变化、企业落地案例、行业报告、政策合规给高分）\n"
                  '只输出 JSON：{"items":[{"i":序号,"zh":"","brief":"","why":"","score":0}]}\n\n' + listing)
        try:
            r = requests.post(f"{base}/chat/completions", timeout=120,
                              headers={"Authorization": f"Bearer {key}"},
                              json={"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                                    "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"]
            for o in json.loads(re.search(r"\{[\s\S]*\}", txt).group(0)).get("items", []):
                x = batch[int(o["i"])]
                x.update(zh=o.get("zh", ""), brief=o.get("brief", ""), why=o.get("why", ""), score=int(o.get("score", 0)))
        except Exception as e:  # AI 失败不影响抓取结果，下次运行会重试没评分的
            print(f"  AI 评分失败（第 {i // 12 + 1} 批）：{e}")


def main():
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"items": []}
    known = {x["id"]: x for x in old["items"]}
    status = {}
    for src in json.loads((ROOT / "sources.json").read_text("utf-8")):
        try:
            got = fetch_source(src)
            new = [x for x in got if x["id"] not in known]
            for x in new:
                known[x["id"]] = x
            status[src["id"]] = {"name": src["name"], "ok": True, "count": len(got), "new": len(new)}
            print(f"✓ {src['name']}: {len(got)} 条，新 {len(new)}")
        except Exception as e:
            status[src["id"]] = {"name": src["name"], "ok": False, "error": str(e)[:200]}
            print(f"✗ {src['name']}: {e}")

    cutoff = time.time() - KEEP_DAYS * 86400
    items = sorted((x for x in known.values() if x["ts"] >= cutoff), key=lambda x: -x["ts"])
    ai_enrich([x for x in items if "score" not in x])

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": int(time.time()), "sources": status, "items": items},
                              ensure_ascii=False, indent=1), "utf-8")
    print(f"共 {len(items)} 条 → {OUT}")


if __name__ == "__main__":
    main()
