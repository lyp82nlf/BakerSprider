# Barker 理财监控爬虫

每 5 分钟拉取 Barker CEX 理财活动接口，发现新增活动、实时年化利率变化达到 1 个百分点、或到期时间变化时，通过企业微信群机器人通知。

## 配置

复制 `.env.example` 为 `.env`，填入：

```bash
BARKER_API_KEY=你的 Barker x-api-key
WECOM_WEBHOOK_URL=你的企业微信群机器人 webhook
```

可选配置：

```bash
FETCH_INTERVAL_SECONDS=300
RATE_THRESHOLD_POINTS=1.0
ONLY_ACTIVE=true
STATE_PATH=state/campaign_snapshot.json
HISTORY_PATH=state/campaign_history.jsonl
REPORT_STATE_PATH=state/report_state.json
DAILY_REPORT_ENABLED=true
DAILY_REPORT_HOUR=10
DAILY_RATE_CHANGE_THRESHOLD_POINTS=2.0
DAILY_HIGH_APY_THRESHOLD=8.0
```

## 运行

执行一次，首次运行只建立基线：

```bash
python3 -m barker_spider once
```

只打印结果，不发送企微通知：

```bash
python3 -m barker_spider once --dry-run
```

查看当前保存的监控列表：

```bash
python3 -m barker_spider list
```

重新抓取并查看最新监控列表：

```bash
python3 -m barker_spider list --refresh
```

查看接口原始关键字段和脚本换算后的显示值：

```bash
python3 -m barker_spider raw-list
```

预览日报：

```bash
python3 -m barker_spider daily-report --dry-run
```

重新抓取最新数据后预览日报：

```bash
python3 -m barker_spider daily-report --dry-run --refresh
```

常驻运行：

```bash
python3 -m barker_spider run
```

## Mac 开机启动

```bash
chmod +x scripts/install_launchd.sh
scripts/install_launchd.sh
```

日志会写入：

```text
logs/stdout.log
logs/stderr.log
```

## 测试

```bash
python3 -m unittest discover -s tests
```
