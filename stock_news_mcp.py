#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
import datetime
import hashlib
import logging
import re
import requests
import schedule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_crawler_mcp.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StockNewsCrawlerMCP")

# 全局变量
CONFIG_FILE = "config.json"
DATA_FILE = "news_data_mcp.json"
config = None
news_data = {}

def load_config():
    """加载配置文件"""
    global config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"配置加载成功，监控 {len(config['stocks'])} 只股票")
        return True
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return False

def load_news_data():
    """加载已保存的新闻数据"""
    global news_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                news_data = json.load(f)
            logger.info(f"已加载保存的新闻数据，包含 {len(news_data)} 条记录")
        except Exception as e:
            logger.error(f"加载新闻数据失败: {e}")
            news_data = {}
    else:
        news_data = {}
        logger.info("没有找到已保存的新闻数据，将创建新的数据文件")

def save_news_data():
    """保存新闻数据到文件"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(news_data, f, ensure_ascii=False, indent=2)
        logger.info(f"新闻数据已保存，共 {len(news_data)} 条记录")
    except Exception as e:
        logger.error(f"保存新闻数据失败: {e}")

def generate_news_id(title, url):
    """生成新闻的唯一ID"""
    content = f"{title}_{url}".encode('utf-8')
    return hashlib.md5(content).hexdigest()

def clean_stock_price_info(title):
    """清除标题中的股价涨跌信息"""
    # 匹配常见的股价涨跌模式，如：上涨5%，下跌3.2%，+2.5%，-1.8%等
    patterns = [
        r'上涨\s*\d+(\.\d+)?%',
        r'下跌\s*\d+(\.\d+)?%',
        r'涨\s*\d+(\.\d+)?%',
        r'跌\s*\d+(\.\d+)?%',
        r'[+-]\s*\d+(\.\d+)?%',
        r'大涨\s*\d+(\.\d+)?%',
        r'大跌\s*\d+(\.\d+)?%',
        r'收盘\s*[+-]?\s*\d+(\.\d+)?%',
        r'报\s*[+-]?\s*\d+(\.\d+)?%',
        r'涨停',
        r'跌停'
    ]
    
    cleaned_title = title
    for pattern in patterns:
        cleaned_title = re.sub(pattern, '', cleaned_title)
    
    # 去除多余空格
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def crawl_stock_news_with_mcp(stock):
    """使用MCP FireCrawl抓取单个股票的最新资讯"""
    stock_name = stock['name']
    stock_code = stock['code']
    url = stock['url']
    
    logger.info(f"开始使用MCP抓取 {stock_name}({stock_code}) 的最新资讯")
    
    try:
        # 使用MCP FireCrawl API抓取页面
        api_url = "https://api.example.com/firecrawl/scrape"  # 替换为实际的MCP API端点
        
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer YOUR_API_KEY"  # 替换为您的API密钥
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        if "content" not in result or not result["content"]:
            logger.warning(f"未获取到 {stock_name} 的资讯内容")
            return []
        
        # 提取资讯列表
        markdown_content = result["content"][0]["text"]
        
        # 解析markdown内容中的表格，提取资讯
        news_list = []
        
        # 简单的表格解析逻辑，根据实际返回的markdown格式调整
        lines = markdown_content.split('\n')
        table_start = False
        headers = []
        
        for line in lines:
            line = line.strip()
            
            # 查找表格头部
            if line.startswith('| 阅读') and '标题' in line and '作者' in line:
                table_start = True
                headers = [h.strip() for h in line.split('|')[1:-1]]
                continue
            
            # 跳过表格分隔行
            if table_start and line.startswith('| ---'):
                continue
            
            # 处理表格内容行
            if table_start and line.startswith('|') and len(line.split('|')) > 3:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                
                # 提取标题和链接
                title_cell = cells[2]  # 假设标题在第3列
                
                # 使用正则表达式提取标题和链接
                title_match = re.search(r'\[(.*?)\]\((.*?)\)', title_cell)
                
                if title_match:
                    title = title_match.group(1)
                    news_url = title_match.group(2)
                    
                    # 清除标题中的股价涨跌信息
                    cleaned_title = clean_stock_price_info(title)
                    
                    # 提取发布时间
                    pub_time = cells[4] if len(cells) > 4 else ""  # 假设时间在第5列
                    
                    # 生成唯一ID
                    news_id = generate_news_id(cleaned_title, news_url)
                    
                    # 添加到结果列表
                    news_list.append({
                        'id': news_id,
                        'title': cleaned_title,
                        'url': news_url,
                        'pub_time': pub_time,
                        'stock_name': stock_name,
                        'stock_code': stock_code,
                        'crawl_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        logger.info(f"成功抓取 {stock_name} 的 {len(news_list)} 条资讯")
        return news_list
    
    except Exception as e:
        logger.error(f"使用MCP抓取 {stock_name} 资讯失败: {e}")
        return []

def update_news_data(new_news_list):
    """更新新闻数据，避免重复"""
    global news_data
    
    added_count = 0
    for news in new_news_list:
        news_id = news['id']
        if news_id not in news_data:
            news_data[news_id] = news
            added_count += 1
    
    logger.info(f"新增 {added_count} 条新闻")
    return added_count

def generate_html():
    """生成HTML页面"""
    output_file = config.get('output_file', 'stock_news.html')
    
    # 按股票分组整理新闻
    stock_news = {}
    for news_id, news in news_data.items():
        stock_code = news['stock_code']
        if stock_code not in stock_news:
            stock_news[stock_code] = []
        stock_news[stock_code].append(news)
    
    # 对每个股票的新闻按抓取时间排序（最新的在前）
    for stock_code in stock_news:
        stock_news[stock_code].sort(key=lambda x: x['crawl_time'], reverse=True)
        # 限制每只股票显示的新闻数量
        max_news = config.get('max_news_per_stock', 10)
        stock_news[stock_code] = stock_news[stock_code][:max_news]
    
    # 生成HTML内容
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>股票最新资讯</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 5px 5px 0 0;
                margin-bottom: 20px;
            }
            .stock-section {
                background-color: white;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                overflow: hidden;
            }
            .stock-header {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
            }
            .news-list {
                padding: 0;
                margin: 0;
                list-style: none;
            }
            .news-item {
                padding: 15px 20px;
                border-bottom: 1px solid #eee;
            }
            .news-item:last-child {
                border-bottom: none;
            }
            .news-title {
                margin: 0 0 5px 0;
                font-size: 16px;
            }
            .news-title a {
                color: #2c3e50;
                text-decoration: none;
            }
            .news-title a:hover {
                text-decoration: underline;
            }
            .news-meta {
                color: #7f8c8d;
                font-size: 12px;
            }
            .footer {
                text-align: center;
                margin-top: 20px;
                color: #7f8c8d;
                font-size: 12px;
            }
            .update-time {
                text-align: right;
                color: #7f8c8d;
                font-size: 12px;
                padding: 10px 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>股票最新资讯</h1>
                <p class="update-time">最后更新时间: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
            </div>
    """
    
    # 添加每只股票的新闻
    for stock in config['stocks']:
        stock_code = stock['code']
        stock_name = stock['name']
        
        if stock_code not in stock_news or not stock_news[stock_code]:
            continue
        
        html_content += f"""
            <div class="stock-section">
                <div class="stock-header">
                    <h2>{stock_name} ({stock_code})</h2>
                </div>
                <ul class="news-list">
        """
        
        for news in stock_news[stock_code]:
            html_content += f"""
                    <li class="news-item">
                        <h3 class="news-title"><a href="{news['url']}" target="_blank">{news['title']}</a></h3>
                        <div class="news-meta">
                            <span>发布时间: {news['pub_time']}</span>
                            <span> | 抓取时间: {news['crawl_time']}</span>
                        </div>
                    </li>
            """
        
        html_content += """
                </ul>
            </div>
        """
    
    html_content += """
            <div class="footer">
                <p>© """ + datetime.datetime.now().strftime('%Y') + """ 股票资讯爬虫 | 数据来源: 东方财富网</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 写入文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"HTML页面已生成: {output_file}")
    except Exception as e:
        logger.error(f"生成HTML页面失败: {e}")

def crawl_all_stocks():
    """抓取所有股票的资讯"""
    if not config:
        logger.error("配置未加载，无法抓取")
        return
    
    all_news = []
    for stock in config['stocks']:
        news_list = crawl_stock_news_with_mcp(stock)
        all_news.extend(news_list)
        # 添加延时，避免请求过于频繁
        time.sleep(2)
    
    # 更新数据
    added_count = update_news_data(all_news)
    
    # 如果有新增数据，保存数据并更新HTML
    if added_count > 0:
        save_news_data()
        generate_html()
    
    logger.info(f"本次抓取完成，新增 {added_count} 条资讯")

def main():
    """主函数"""
    # 加载配置
    if not load_config():
        return
    
    # 加载已保存的新闻数据
    load_news_data()
    
    # 立即执行一次抓取
    crawl_all_stocks()
    
    # 设置定时任务
    interval_minutes = config.get('update_interval_minutes', 60)
    logger.info(f"设置定时任务，每 {interval_minutes} 分钟执行一次")
    
    schedule.every(interval_minutes).minutes.do(crawl_all_stocks)
    
    # 运行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main() 