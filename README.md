# 东方财富股票资讯爬虫

这是一个用于抓取东方财富网股票资讯的爬虫程序，可以定时获取指定股票的最新资讯，并将结果整合到一个网页上。

## 功能特点

- 支持配置多只股票的监控
- 自动过滤股价涨跌信息，保留有价值的资讯内容
- 定时抓取更新，避免重复内容
- 生成美观的HTML页面展示结果
- 支持多种抓取方式（普通爬虫和MCP FireCrawl）

## 文件说明

- `config.json`: 配置文件，包含要监控的股票列表和其他设置
- `stock_news_crawler.py`: 使用普通爬虫方式抓取的主程序
- `stock_news_mcp.py`: 使用MCP API方式抓取的主程序
- `stock_news_mcp_firecrawl.py`: 使用MCP FireCrawl工具抓取的主程序
- `news_data.json`: 保存抓取的新闻数据
- `stock_news.html`: 生成的HTML页面

## 安装依赖

```bash
pip install requests beautifulsoup4 schedule
```

## 配置说明

在`config.json`文件中配置要监控的股票：

```json
{
  "stocks": [
    {
      "name": "东方财富",
      "code": "300059",
      "url": "https://guba.eastmoney.com/list,300059,1,f.html"
    },
    {
      "name": "中国平安",
      "code": "601318",
      "url": "https://guba.eastmoney.com/list,601318,1,f.html"
    }
  ],
  "update_interval_minutes": 60,
  "max_news_per_stock": 10,
  "output_file": "stock_news.html"
}
```

配置项说明：
- `stocks`: 要监控的股票列表
  - `name`: 股票名称
  - `code`: 股票代码
  - `url`: 东方财富网资讯页面URL
- `update_interval_minutes`: 更新间隔（分钟）
- `max_news_per_stock`: 每只股票最多显示的新闻数量
- `output_file`: 输出的HTML文件名

## 使用方法

### 使用普通爬虫方式

```bash
python stock_news_crawler.py
```

### 使用MCP FireCrawl方式

```bash
python stock_news_mcp_firecrawl.py
```

## 注意事项

1. 使用MCP FireCrawl方式时，需要替换代码中的API端点和密钥
2. 程序会在后台持续运行，定时抓取更新
3. 日志文件会记录抓取过程中的信息和错误

## 自定义

- 可以修改HTML模板样式，美化页面展示
- 可以调整过滤规则，根据需要保留或过滤特定内容
- 可以扩展功能，如添加邮件通知、数据分析等 