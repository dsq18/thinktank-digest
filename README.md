# ThinkTank-Digest

ThinkTank-Digest 是一个每日运行的地缘政治研究助理。它从 `sources.yaml` 中登记的国际智库自动发现新研究，抽取正文，去重入库，筛掉低价值内容，使用 OpenAI 生成简体中文战略分析，并通过 NetEase SMTP 发送 HTML 邮件简报。

它不是新闻聚合器。排序和摘要优先服务于战略意义、政策相关性、来源权重和时效性。

## 功能

- 所有智库来源都维护在 `sources.yaml`，代码不硬编码机构清单。
- RSS 优先，RSS 不可用时自动回退到网站抓取。
- SQLite 保存 URL 状态，防止同一 URL 被重复总结。
- 每篇相关研究生成：
  - 一句话结论
  - 3-5 个核心观点
  - 对中国的影响
  - 对印太的影响
  - 对国际安全的影响
  - 对全球经济的影响
  - 重要性评分 1-5
  - 主题标签
- HTML 邮件包含：
  - 今日最重要研究
  - 今日重点观察
  - 按主题分类
  - 全部新增研究
- 支持纯文本 fallback。
- GitHub Actions 每天 08:00 Asia/Singapore 自动运行。
- SMTP 使用 `SMTP_SSL` 和 NetEase 授权码，不使用邮箱登录密码。

## 主题分类

系统至少识别这些主题：

`China`, `Taiwan`, `Indo-Pacific`, `US-China Relations`, `Technology`, `AI`, `Semiconductors`, `Defense`, `Military`, `Economics`, `Trade`, `Energy`, `Europe`, `Russia`, `Middle East`

优先关注：

`China`, `Taiwan`, `Indo-Pacific`, `Great Power Competition`, `National Security`, `Defense`, `Emerging Technology`, `AI`, `Geoeconomics`

## 本地安装

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

复制环境变量模板：

```bash
cp .env.example .env
```

然后设置：

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"
export EMAIL_SMTP_HOST="smtp.163.com"
export EMAIL_SMTP_PORT="465"
export EMAIL_ADDRESS="你的网易邮箱"
export EMAIL_AUTH_CODE="你的网易邮箱 SMTP 授权码"
export EMAIL_TO="收件邮箱"
```

`EMAIL_AUTH_CODE` 必须是 NetEase 邮箱里的 SMTP 授权码，不是邮箱登录密码。

## 本地运行

只生成报告，不发送邮件：

```bash
thinktank-digest run --no-send --html-out reports/latest.html --text-out reports/latest.txt
```

完整运行并发送邮件：

```bash
thinktank-digest run
```

运行确定性的端到端 staging 测试，不访问外网、不调用 OpenAI、不真的发送邮件：

```bash
thinktank-digest staging --out-dir reports/staging
```

staging 会连续运行两次同一条模拟文章。第一次应生成 1 条报告内容，第二次应生成 0 条报告内容，用来确认 SQLite URL 去重可以阻止同一文章再次进入日报。

运行自动 self-review：

```bash
thinktank-digest self-review --out-dir reports/self-review
```

self-review 会依次执行语法编译、pytest 和 staging 端到端流程。

运行测试：

```bash
pytest
```

检查 NetEase SMTP 环境变量：

```bash
thinktank-digest check-email-env
```

发送一封真实 SMTP 测试邮件：

```bash
thinktank-digest send-test-email
```

只有在 `EMAIL_ADDRESS`、`EMAIL_AUTH_CODE`、`EMAIL_TO` 等真实环境变量配置正确时，这个命令才能确认 NetEase SMTP 身份认证和收件链路可用。

## 来源管理

查看来源：

```bash
thinktank-digest list-sources
```

按自然命令更新 `sources.yaml`：

```bash
thinktank-digest source-command "Add source Example Institute" --website "https://example.org" --rss "https://example.org/feed" --priority 4 --topics "China,Defense" --tags "think-tank,test"
thinktank-digest source-command "Remove source Example Institute"
thinktank-digest source-command "Enable source Brookings"
thinktank-digest source-command "Disable source Brookings"
thinktank-digest source-command "Set priority Brookings 5"
```

新增来源时，如果暂时不知道 RSS，可以不传 `--rss`。系统会从 `website` 回退抓取页面链接。

## GitHub Actions 部署

1. 将项目推送到 GitHub。
2. 在仓库 Settings → Secrets and variables → Actions 中添加：
   - `OPENAI_API_KEY`
   - `EMAIL_ADDRESS`
   - `EMAIL_AUTH_CODE`
   - `EMAIL_TO`
3. 确认 `.github/workflows/thinktank-digest.yml` 已存在。
4. workflow 会使用：

```cron
0 0 * * *
```

GitHub Actions cron 使用 UTC，因此这是 Asia/Singapore 每天 08:00。

workflow 会缓存 `data/` 目录，让 SQLite 去重状态跨运行保存。也可以在 Actions 页面手动触发 `workflow_dispatch`。

每日真实发送前，workflow 会先执行编译检查、pytest 和 SMTP 环境变量检查。全部通过后，才会运行真实日报发送：

```bash
thinktank-digest run --max-articles 80 --html-out reports/latest.html --text-out reports/latest.txt
```

workflow 还会上传 `reports/` 作为 artifact，方便你在 GitHub Actions 页面查看当日 HTML 和纯文本报告。

如果你在今天完成推送并配置好 GitHub Secrets，下一次计划任务会在明天 08:00 Asia/Singapore 发送第一封真实简报。GitHub Actions 的定时触发和 NetEase SMTP 认证结果取决于 GitHub 仓库、Secrets 和邮箱授权码是否已正确配置。

## 可靠性设计

- `httpx` 请求设置超时并跟随重定向。
- RSS 和页面抓取有重试。
- OpenAI 分析有重试。
- SMTP 发送有重试。
- GitHub Actions 每日重新运行；单日失败不会阻止后续日期继续运行。
- 失败会写入日志。
- 邮件发送成功或失败会写入 SQLite 的 `email_logs` 表。
- 没有 `OPENAI_API_KEY` 时，本地仍可用规则 fallback 跑通流程，但正式部署建议配置 API key。
- 正文抽取失败或正文过短的 URL 会标记为 skipped，避免反复处理。
- 日报只包含本次运行中新分析成功的文章，避免手动重跑时重新发送已处理 URL。

## 故障排查

如果没有收到邮件：

- 检查 GitHub Actions 日志中的 `Email delivery failed`。
- 确认 `EMAIL_AUTH_CODE` 是 NetEase SMTP 授权码。
- 确认 NetEase 邮箱已开启 SMTP/POP3 服务。
- 确认 `EMAIL_SMTP_HOST=smtp.163.com` 且 `EMAIL_SMTP_PORT=465`。
- 确认 `EMAIL_TO` 没有拼写错误。

如果报告为空：

- 检查 `sources.yaml` 中来源是否 `enabled: true`。
- 检查 RSS URL 是否仍可访问。
- 运行 `thinktank-digest run --no-send --log-level DEBUG` 查看发现和抽取日志。
- 适当提高来源 `priority`，或补充来源的 `topics` 和 `tags`。

如果重复出现同一文章：

- 确认 GitHub Actions cache 步骤成功恢复了 `data/`。
- 确认 URL 没有因跟踪参数变化导致不同 URL 被视为新文章。

## 项目结构

```text
thinktank_digest/
  analyze.py       # 相关性判断、OpenAI 分析、排序、跨源综合
  cli.py           # 命令行入口
  db.py            # SQLite schema、去重、分析状态、邮件日志
  emailer.py       # SMTP_SSL 邮件发送
  ingest.py        # RSS 发现、网站回退、正文抽取
  pipeline.py      # 每日工作流编排
  report.py        # HTML 和纯文本日报渲染
  self_review.py   # 编译、测试、staging 自检
  staging.py       # 确定性端到端功能测试
  sources.py       # sources.yaml 读取和来源命令更新
sources.yaml       # 唯一来源注册表
.github/workflows/daily-digest.yml
```
