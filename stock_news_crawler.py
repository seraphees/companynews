#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
import datetime
import hashlib
import requests
import logging
from bs4 import BeautifulSoup
import schedule
import re


# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StockNewsCrawler")

# 全局变量
CONFIG_FILE = "config.json"
FILTER_KEYWORDS_FILE = "filter_keywords.json"
DATA_FILE = "news_data.json"
config = None
filter_keywords = []
news_data = {}

# URL模板
URL_TEMPLATE = "https://guba.eastmoney.com/list,{code},1,f.html"

def should_filter_title(title):
    """判断标题是否应该被过滤"""
    # 使用从配置文件加载的过滤关键词
    for keyword in filter_keywords:
        if keyword in title:
            return True
    
    return False

def load_config():
    """加载配置文件"""
    global config, filter_keywords
    try:
        # 加载主配置文件
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"配置加载成功，监控 {len(config['stocks'])} 只股票")
        
        # 加载过滤关键词配置文件
        if os.path.exists(FILTER_KEYWORDS_FILE):
            with open(FILTER_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                filter_data = json.load(f)
                filter_keywords = filter_data.get('filter_keywords', [])
            logger.info(f"过滤关键词加载成功，共 {len(filter_keywords)} 个关键词")
        else:
            logger.warning(f"过滤关键词文件 {FILTER_KEYWORDS_FILE} 不存在，使用空列表")
            filter_keywords = []
        
        # 输出所有要监控的股票和URL
        for stock in config['stocks']:
            url = URL_TEMPLATE.format(code=stock['code'])
            logger.info(f"将监控股票: {stock['name']}({stock['code']}), URL: {url}")
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

def crawl_stock_news(stock):
    """抓取单个股票的最新资讯"""
    stock_name = stock['name']
    stock_code = stock['code']
    url = URL_TEMPLATE.format(code=stock_code)
    
    logger.info(f"开始抓取 {stock_name}({stock_code}) 的最新资讯，URL: {url}")
    
    try:
        # 使用MCP FireCrawl抓取页面
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logger.info(f"正在请求URL: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'  # 设置响应编码为UTF-8
        logger.info(f"请求成功，状态码: {response.status_code}")
        
        # 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 输出HTML结构的关键部分，帮助分析
        logger.debug("分析页面HTML结构...")
        
        # 保存HTML内容到文件，用于调试
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.debug("已保存页面HTML到debug_page.html文件")
        
        # 尝试多种选择器来查找资讯列表
        news_items = []
        
        # 尝试方法1：查找表格中的行
        table = soup.select_one('table.articleh')
        if table:
            logger.debug("找到资讯表格 table.articleh")
            rows = table.select('tr')
            if rows:
                news_items = rows
                logger.debug(f"从表格中找到 {len(rows)} 行")
        
        # 尝试方法2：直接查找articleh类的div
        if not news_items:
            items = soup.select('div.articleh')
            if items:
                news_items = items
                logger.debug(f"找到 {len(items)} 个div.articleh元素")
        
        # 尝试方法3：查找包含资讯的列表项
        if not news_items:
            items = soup.select('ul.newlist > li')
            if items:
                news_items = items
                logger.debug(f"找到 {len(items)} 个列表项")
        
        # 尝试方法4：查找所有可能的资讯容器
        if not news_items:
            items = soup.select('.listcont .articleh, .articleh_list .articleh, #mainlist .articleh')
            if items:
                news_items = items
                logger.debug(f"从多个容器中找到 {len(items)} 个资讯项")
        
        # 尝试方法5：查找所有包含标题和链接的行
        if not news_items:
            items = soup.select('tr:has(a), div:has(span.l3 > a)')
            if items:
                news_items = items
                logger.debug(f"找到 {len(items)} 个包含链接的行")
        
        if not news_items:
            logger.warning(f"未找到 {stock_name} 的资讯列表项，URL: {url}")
            return []
        
        logger.info(f"找到 {len(news_items)} 条资讯项")
        
        # 输出前几个资讯项的HTML结构，帮助调试
        for i, item in enumerate(news_items[:3]):
            logger.debug(f"资讯项 {i+1} HTML结构: {item}")
        
        news_list = []
        for idx, item in enumerate(news_items):
            try:
                # 尝试多种方式提取标题和链接
                title_tag = None
                
                # 方法1：标准的东方财富股吧格式
                title_tag = item.select_one('span.l3 > a')
                
                # 方法2：其他可能的格式
                if not title_tag:
                    title_tag = item.select_one('a.title, a.news_title, a[title]')
                
                # 方法3：任何链接
                if not title_tag:
                    title_tag = item.select_one('a')
                
                if not title_tag:
                    logger.warning(f"第 {idx+1} 条资讯没有找到标题标签")
                    continue
                
                title = title_tag.get_text().strip()
                news_url = title_tag.get('href')
                
                # 如果链接是相对路径，转为绝对路径
                if news_url and not news_url.startswith('http'):
                    news_url = f"https://guba.eastmoney.com{news_url}"
                
                # 跳过没有URL的项目
                if not news_url:
                    logger.debug(f"跳过没有URL的资讯: {title}")
                    continue
                
                # 只保留以https://guba.eastmoney.com/news开头的资讯
                if not news_url.startswith('https://guba.eastmoney.com/news'):
                    logger.debug(f"跳过非资讯URL: {news_url}")
                    continue
                
                # 尝试多种方式提取发布时间
                time_tag = None
                
                # 方法1：标准的东方财富股吧格式
                time_tag = item.select_one('span.l6')
                
                # 方法2：其他可能的格式
                if not time_tag:
                    time_tag = item.select_one('span.time, span.date, td:last-child')
                
                pub_time = time_tag.get_text().strip() if time_tag else ""
                
                # 如果没有发布时间，尝试从其他地方提取
                if not pub_time:
                    # 尝试从URL或标题中提取日期
                    date_match = re.search(r'(\d{2}-\d{2}|\d{2}/\d{2}|\d{4}-\d{2}-\d{2})', title)
                    if date_match:
                        pub_time = date_match.group(1)
                    else:
                        logger.debug(f"跳过没有发布时间的资讯: {title}")
                        continue
                
                # 尝试多种方式提取阅读数
                read_tag = item.select_one('span.l1')
                read_count = read_tag.get_text().strip() if read_tag else "0"
                
                # 尝试多种方式提取评论数
                comment_tag = item.select_one('span.l2')
                comment_count = comment_tag.get_text().strip() if comment_tag else "0"
                
                # 尝试多种方式提取作者信息
                author_tag = item.select_one('span.l4')
                author = author_tag.get_text().strip() if author_tag else ""
                
                
                # 过滤包含特定关键词的标题
                if should_filter_title(title):
                    logger.debug(f"过滤包含特定关键词的标题: '{title}'")
                    continue
                
                # 生成唯一ID
                news_id = generate_news_id(title, news_url)
                
                # 添加到结果列表
                news_list.append({
                    'id': news_id,
                    'title': title,
                    'url': news_url,
                    'pub_time': pub_time,
                    'read_count': read_count,
                    'comment_count': comment_count,
                    'author': author,
                    'stock_name': stock_name,
                    'stock_code': stock_code,
                    'crawl_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                logger.debug(f"成功解析资讯: 标题='{title}', 发布时间={pub_time}, 阅读数={read_count}, 评论数={comment_count}, 作者={author}")
                
            except Exception as e:
                logger.error(f"解析第 {idx+1} 条资讯项时出错: {e}")
                continue
        
        logger.info(f"成功抓取 {stock_name} 的 {len(news_list)} 条有效资讯")
        return news_list
    
    except requests.exceptions.RequestException as e:
        logger.error(f"请求 {url} 失败: {e}")
        return []
    except Exception as e:
        logger.error(f"抓取 {stock_name} 资讯失败: {e}")
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
            logger.debug(f"新增资讯: {news['title']} ({news['stock_name']})")
    
    logger.info(f"新增 {added_count} 条新闻")
    
    # 按股票代码保存到单独的文件
    save_news_by_stock()
    
    return added_count

def save_news_by_stock():
    """按股票代码将新闻保存到单独的文件"""
    # 创建数据目录
    data_dir = "stock_data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"创建数据目录: {data_dir}")
    
    # 按股票分组整理新闻
    stock_news = {}
    for news_id, news in news_data.items():
        # 只保存以https://guba.eastmoney.com/news开头的资讯
        if not news['url'].startswith('https://guba.eastmoney.com/news'):
            logger.debug(f"跳过非资讯URL: {news['url']}")
            continue
        
        # 过滤包含特定关键词的标题
        if should_filter_title(news['title']):
            logger.debug(f"跳过包含特定关键词的标题: {news['title']}")
            continue
            
        stock_code = news['stock_code']
        if stock_code not in stock_news:
            stock_news[stock_code] = []
        stock_news[stock_code].append(news)
    
    # 对每个股票的新闻按发布时间排序（最新的在前）
    for stock_code in stock_news:
        stock_news[stock_code].sort(key=lambda x: x['pub_time'], reverse=True)
        
        # 保存到对应的文件
        file_path = os.path.join(data_dir, f"{stock_code}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(stock_news[stock_code], f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {stock_code} 的 {len(stock_news[stock_code])} 条资讯到 {file_path}")
        except Exception as e:
            logger.error(f"保存 {stock_code} 的资讯到文件失败: {e}")

def generate_html():
    """生成HTML页面"""
    output_file = config.get('output_file', 'stock_news.html')
    logger.info(f"开始生成HTML页面: {output_file}")
    
    # 从文件读取各股票的新闻数据
    stock_news = {}
    data_dir = "stock_data"
    
    if not os.path.exists(data_dir):
        logger.warning(f"数据目录 {data_dir} 不存在，无法生成HTML")
        return
    
    # 读取所有股票的数据文件
    for stock in config['stocks']:
        stock_code = stock['code']
        file_path = os.path.join(data_dir, f"{stock_code}.json")
        
        if not os.path.exists(file_path):
            logger.warning(f"股票 {stock_code} 的数据文件不存在")
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stock_news[stock_code] = json.load(f)
            
            # 确保按发布时间逆序排序
            stock_news[stock_code].sort(key=lambda x: x['pub_time'], reverse=True)
            logger.info(f"已读取 {stock_code} 的 {len(stock_news[stock_code])} 条资讯")
        except Exception as e:
            logger.error(f"读取 {stock_code} 的资讯文件失败: {e}")
    
    # 按行业分组股票
    industries = {}
    for stock in config['stocks']:
        industry = stock.get('industry', '其他')
        if industry not in industries:
            industries[industry] = []
        industries[industry].append(stock)
    
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
                padding: 0;
                background-color: #f5f5f5;
            }
            .container {
                display: flex;
                max-width: 1400px;
                margin: 0 auto;
                min-height: 100vh;
            }
            .sidebar {
                width: 250px;
                background-color: #2c3e50;
                color: white;
                padding: 20px 0;
                overflow-y: auto;
                position: sticky;
                top: 0;
                height: 100vh;
            }
            .content {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
            }
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 5px 5px 0 0;
                margin-bottom: 20px;
            }
            .industry-section {
                margin-bottom: 20px;
            }
            .industry-title {
                padding: 10px 20px;
                background-color: #34495e;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }
            .industry-stocks {
                padding: 0;
                margin: 0;
                list-style: none;
                display: none;
            }
            .stock-item {
                padding: 8px 20px 8px 30px;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            .stock-item:hover {
                background-color: #3498db;
            }
            .stock-item.active {
                background-color: #3498db;
            }
            .stock-section {
                background-color: white;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                overflow: hidden;
                display: none;
            }
            .stock-section.active {
                display: block;
            }
            .stock-header {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .stock-link {
                margin: 10px 20px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
                border-left: 4px solid #3498db;
            }
            .stock-link a {
                color: #2c3e50;
                text-decoration: none;
                font-weight: bold;
            }
            .stock-link a:hover {
                text-decoration: underline;
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
            .stats {
                display: inline-block;
                margin-right: 15px;
            }
            .stats i {
                margin-right: 5px;
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
            .pagination {
                display: flex;
                justify-content: center;
                margin: 20px 0;
                padding: 0;
                list-style: none;
            }
            .pagination li {
                margin: 0 5px;
            }
            .pagination a {
                display: block;
                padding: 8px 12px;
                background-color: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 3px;
            }
            .pagination a:hover {
                background-color: #2980b9;
            }
            .pagination .active a {
                background-color: #2c3e50;
            }
            .pagination .disabled a {
                background-color: #bdc3c7;
                cursor: not-allowed;
            }
            .page-content {
                display: none;
            }
            .page-content.active {
                display: block;
            }
            .no-news {
                padding: 20px;
                text-align: center;
                color: #7f8c8d;
            }
            .collapsible {
                cursor: pointer;
            }
            .collapsible:after {
                content: '\\002B';
                color: white;
                font-weight: bold;
                float: right;
                margin-left: 5px;
            }
            .active.collapsible:after {
                content: "\\2212";
            }
        </style>
        <script>
            function showStock(stockCode) {
                // 隐藏所有股票区域
                var stockSections = document.querySelectorAll('.stock-section');
                for (var i = 0; i < stockSections.length; i++) {
                    stockSections[i].classList.remove('active');
                }
                
                // 显示选中的股票区域
                var selectedStock = document.getElementById('stock-' + stockCode);
                if (selectedStock) {
                    selectedStock.classList.add('active');
                }
                
                // 更新侧边栏选中状态
                var stockItems = document.querySelectorAll('.stock-item');
                for (var i = 0; i < stockItems.length; i++) {
                    stockItems[i].classList.remove('active');
                }
                
                var activeItem = document.querySelector('.stock-item[data-code="' + stockCode + '"]');
                if (activeItem) {
                    activeItem.classList.add('active');
                }
                
                return false;
            }
            
            function showPage(stockCode, pageNum) {
                // 隐藏所有页面
                var pages = document.querySelectorAll('.page-' + stockCode);
                for (var i = 0; i < pages.length; i++) {
                    pages[i].style.display = 'none';
                }
                
                // 显示选中的页面
                var selectedPage = document.getElementById('page-' + stockCode + '-' + pageNum);
                if (selectedPage) {
                    selectedPage.style.display = 'block';
                }
                
                // 更新分页按钮状态
                var paginationLinks = document.querySelectorAll('.pagination-' + stockCode + ' li');
                for (var i = 0; i < paginationLinks.length; i++) {
                    paginationLinks[i].classList.remove('active');
                }
                
                var activeLink = document.querySelector('.pagination-' + stockCode + ' li[data-page="' + pageNum + '"]');
                if (activeLink) {
                    activeLink.classList.add('active');
                }
                
                return false;
            }
            
            function toggleIndustry(element) {
                element.classList.toggle("active");
                var content = element.nextElementSibling;
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            }
            
            // 初始化函数
            window.onload = function() {
                // 默认展开所有行业
                var industries = document.querySelectorAll('.industry-stocks');
                for (var i = 0; i < industries.length; i++) {
                    industries[i].style.display = "block";
                }
                
                // 如果有股票，默认选中第一个
                var firstStock = document.querySelector('.stock-item');
                if (firstStock) {
                    var stockCode = firstStock.getAttribute('data-code');
                    showStock(stockCode);
                }
            };
        </script>
    </head>
    <body>
        <div class="container">
            <div class="sidebar">
                <div style="padding: 20px; text-align: center;">
                    <h2>股票资讯</h2>
                    <p class="update-time" style="text-align: center;">更新: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + """</p>
                </div>
    """
    
    # 添加侧边栏行业和股票列表
    for industry, stocks in sorted(industries.items()):
        html_content += f"""
                <div class="industry-section">
                    <div class="industry-title collapsible" onclick="toggleIndustry(this)">{industry}</div>
                    <ul class="industry-stocks">
        """
        
        for stock in sorted(stocks, key=lambda x: x['name']):
            stock_code = stock['code']
            stock_name = stock['name']
            
            # 检查是否有新闻数据
            has_news = stock_code in stock_news and len(stock_news[stock_code]) > 0
            news_count = len(stock_news[stock_code]) if has_news else 0
            
            html_content += f"""
                        <li class="stock-item" data-code="{stock_code}" onclick="showStock('{stock_code}')">
                            {stock_name} ({stock_code}) <span style="float:right;">{news_count}</span>
                        </li>
            """
        
        html_content += """
                    </ul>
                </div>
        """
    
    html_content += """
            </div>
            <div class="content">
                <div class="header">
                    <h1>股票最新资讯</h1>
                    <p class="update-time">最后更新时间: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
                </div>
    """
    
    # 每页显示的新闻数量
    items_per_page = 10
    
    # 添加每只股票的新闻区域
    for stock in config['stocks']:
        stock_code = stock['code']
        stock_name = stock['name']
        stock_url = URL_TEMPLATE.format(code=stock_code)
        
        html_content += f"""
                <div id="stock-{stock_code}" class="stock-section">
                    <div class="stock-header">
                        <h2>{stock_name} ({stock_code})</h2>
                        <div class="stock-link">
                            <a href="{stock_url}" target="_blank">前往东方财富股吧查看 {stock_name} 的更多讨论 »</a>
                        </div>
        """
        
        if stock_code in stock_news and stock_news[stock_code]:
            news_list = stock_news[stock_code]
            total_news = len(news_list)
            total_pages = (total_news + items_per_page - 1) // items_per_page  # 向上取整
            
            html_content += f"""
                        <span>共 {total_news} 条资讯</span>
                    </div>
            """
            
            # 分页显示新闻
            for page in range(1, total_pages + 1):
                start_idx = (page - 1) * items_per_page
                end_idx = min(start_idx + items_per_page, total_news)
                page_news = news_list[start_idx:end_idx]
                
                display_style = "block" if page == 1 else "none"
                
                html_content += f"""
                    <div id="page-{stock_code}-{page}" class="page-{stock_code}" style="display: {display_style}">
                        <ul class="news-list">
                """
                
                for news in page_news:
                    html_content += f"""
                            <li class="news-item">
                                <h3 class="news-title"><a href="{news['url']}" target="_blank">{news['title']}</a></h3>
                                <div class="news-meta">
                                    <span class="stats">👁️ 阅读: {news.get('read_count', '0')}</span>
                                    <span class="stats">💬 评论: {news.get('comment_count', '0')}</span>
                                    <span class="stats">👤 作者: {news.get('author', '未知')}</span>
                                    <span class="stats">⏱️ 发布时间: {news['pub_time']}</span>
                                    <span class="stats">🔄 抓取时间: {news['crawl_time']}</span>
                                </div>
                            </li>
                    """
                
                html_content += """
                        </ul>
                    </div>
                """
            
            # 添加分页导航
            if total_pages > 1:
                html_content += f"""
                    <div class="pagination-container" style="padding: 10px 20px;">
                        <ul class="pagination pagination-{stock_code}">
                """
                
                for page in range(1, total_pages + 1):
                    active_class = "active" if page == 1 else ""
                    html_content += f"""
                            <li class="{active_class}" data-page="{page}"><a href="javascript:void(0)" onclick="showPage('{stock_code}', {page}); return false;">{page}</a></li>
                    """
                
                html_content += """
                        </ul>
                    </div>
                """
        else:
            html_content += f"""
                        <span>暂无资讯</span>
                    </div>
                    <div class="stock-link">
                        <a href="{stock_url}" target="_blank">前往东方财富股吧查看 {stock_name} 的更多讨论 »</a>
                    </div>
                    <div class="no-news">
                        <p>暂无 {stock_name} 的相关资讯</p>
                    </div>
            """
        
        html_content += """
                </div>
        """
    
    html_content += """
                <div class="footer">
                    <p>© """ + datetime.datetime.now().strftime('%Y') + """ 股票资讯爬虫 | 数据来源: 东方财富网</p>
                </div>
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
    
    logger.info("开始抓取所有股票的资讯")
    all_news = []
    for stock in config['stocks']:
        logger.info(f"准备抓取 {stock['name']}({stock['code']}) 的资讯")
        news_list = crawl_stock_news(stock)
        all_news.extend(news_list)
        # 添加延时，避免请求过于频繁
        delay_seconds = 2
        logger.info(f"等待 {delay_seconds} 秒后继续下一只股票")
        time.sleep(delay_seconds)
    
    # 更新数据
    added_count = update_news_data(all_news)
    
    # 如果有新增数据，保存数据并更新HTML
    if added_count > 0:
        logger.info(f"有 {added_count} 条新资讯，更新数据和HTML")
        save_news_data()
        generate_html()
    else:
        logger.info("没有新资讯，跳过更新")
    
    logger.info(f"本次抓取完成，新增 {added_count} 条资讯")

def main():
    """主函数"""
    logger.info("股票资讯爬虫启动")
    
    # 加载配置
    if not load_config():
        logger.error("配置加载失败，程序退出")
        return
    
    # 加载已保存的新闻数据
    load_news_data()
    
    # 立即执行一次抓取
    logger.info("开始第一次抓取")
    crawl_all_stocks()
    
    # 设置定时任务
    interval_minutes = config.get('update_interval_minutes', 60)
    logger.info(f"设置定时任务，每 {interval_minutes} 分钟执行一次")
    
    schedule.every(interval_minutes).minutes.do(crawl_all_stocks)
    
    # 运行定时任务
    logger.info("进入定时任务循环")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()