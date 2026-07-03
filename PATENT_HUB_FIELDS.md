# PatentHub 搜索字段完整指南

## 一、可用字段总览

### 基础字段
| 字段名 | 说明 | 示例 | 可用性 |
|--------|------|------|--------|
| `title` | 专利标题 | title:石墨烯 | ✓ 完全可用 |
| `summary` | 专利摘要 | summary:石墨烯 | ✓ 完全可用 |
| `applicant` | 申请人 | applicant:华为 | ✓ 完全可用 |
| `inventor` | 发明人 | inventor:张三 | ✓ 完全可用 |
| `ipc` | IPC分类号 | ipc:H01M | ✓ 完全可用 |
| `applicationYear` | 申请年份 | applicationYear:2024 | ✓ 完全可用 |
| `documentYear` | 公开年份 | documentYear:2024 | ✓ 完全可用 |
| `legalStatus` | 法律状态 | legalStatus:有效专利 | ✓ 完全可用 |
| `agency` | 代理机构 | agency:柳沈律师事务所 | ✓ 完全可用 |

### 法律状态枚举值
```python
LEGAL_STATUSES = [
    "有效专利",      # 授权且维持有效
    "失效专利",      # 过期或放弃
    "公开",          # 公开但未授权
    "发明授权",      # 已授权
    "发明公开",      # 发明专利公开
    "实用新型",      # 实用新型专利
    "外观设计",      # 外观设计专利
]
```

### IPC分类号（常用）
```python
IPC_CATEGORIES = {
    # 能源与电池
    "H01M": "电池/燃料电池",
    "H02J": "电路系统/储能",
    
    # 新材料
    "C01B": "非金属元素/碳材料",
    "C08K": "高分子化合物应用",
    
    # 电子元器件
    "H01L": "半导体器件",
    "H05K": "印刷电路/电子封装",
    
    # 机械
    "F16B": "紧固件/连接件",
    "B23K": "焊接/切割",
    
    # 化学
    "B01D": "分离/过滤",
    "C07C": "有机化学",
}
```

## 二、搜索语法

### 1. 基础搜索（全文）
```
q=石墨烯
q=电池发热
q=激光焊接
```
说明：在所有字段中搜索关键词

### 2. 字段搜索（精确）
```
q=title:石墨烯薄膜
q=applicant:华为技术有限公司
q=ipc:H01M
q=applicationYear:2024
```
说明：只在指定字段中搜索

### 3. 组合搜索（AND连接）
```
# 关键词 + IPC分类号
q=title:石墨烯 AND ipc:H01M
q=石墨烯 AND ipc:C01B

# 关键词 + 法律状态
q=title:石墨烯 AND legalStatus:有效专利
q=summary:电池 AND legalStatus:公开

# 关键词 + 时间
q=title:石墨烯 AND applicationYear:2024
q=summary:焊接 AND documentYear:2023
```

### 4. 语法限制

#### ✓ 支持的组合
```python
VALID_COMBINATIONS = [
    # 关键词 + 分类号
    ("title|summary", "ipc"),
    
    # 关键词 + 法律状态
    ("title|summary", "legalStatus"),
    
    # 关键词 + 时间
    ("title|summary", "applicationYear|documentYear"),
]
```

#### ✗ 不支持的组合
```python
INVALID_COMBINATIONS = [
    # 分类号 + 法律状态
    "ipc:H01M AND legalStatus:有效专利",
    
    # 申请人 + 分类号
    "applicant:华为 AND ipc:H01M",
    
    # 多条件组合
    "title:石墨烯 AND ipc:H01M AND legalStatus:有效",
]
```

## 三、分页参数

```python
params = {
    "t": "your_token",
    "q": "石墨烯",
    "p": 1,          # 页码（1-100）
    "ps": 10,        # 每页条数（1-50）
    "v": 1,          # 版本号（必须=1）
}
```

## 四、排序参数

```python
params = {
    "s": "!applicationDate",  # 申请时间降序
    # 可选值：
    # "relation" - 相关度（默认）
    # "applicationDate" - 申请时间升序
    # "!applicationDate" - 申请时间降序
    # "documentDate" - 公开时间升序
    # "!documentDate" - 公开时间降序
}
```

⚠️ **注意**：免费版不支持排序参数（返回code=207）

## 五、搜索结果字段

```python
response = {
    "took": 0.123,              # 请求耗时（秒）
    "total": 158813,            # 总结果数
    "code": 200,                # 状态码
    "success": True,            # 是否成功
    "nextPage": 2,              # 下一页页码
    "totalPages": 15882,        # 总页数
    "page": 1,                  # 当前页码
    "patents": [                # 专利列表
        {
            "id": "CN111344253A",           # 专利唯一ID
            "title": "3D石墨烯",            # 专利标题
            "summary": "一种形成3D石墨烯...", # 专利摘要
            "applicant": "RD石墨烯有限公司", # 申请人
            "applicationDate": "2018-08-24", # 申请日期
            "legalStatus": "无效专利",       # 法律状态
            "type": "发明公开",             # 专利类型
            "mainIpc": "C01B32/184",        # 主分类号
            "documentNumber": "CN111344253A", # 文献号
        }
    ]
}
```

## 六、错误码对照

| 错误码 | 说明 | 解决方案 |
|--------|------|---------|
| 200 | 成功 | - |
| 201 | Token为空 | 检查请求参数 |
| 202 | 非法Token | 检查Token是否正确 |
| 207 | 没有访问权限 | 检查免费版限制 |
| 208 | 没有访问权限 | 检查免费版限制 |

## 七、使用场景示例

### 场景1：搜索石墨烯电池相关专利
```python
search_queries = [
    # 石墨烯在电池中的应用
    "q=title:石墨烯 AND ipc:H01M",
    
    # 电池热管理
    "q=电池 AND 热管理 AND ipc:H01M",
    
    # 有效专利
    "q=title:电池 AND legalStatus:有效专利",
]
```

### 场景2：搜索某公司专利
```python
search_queries = [
    # 华为的电池相关专利
    "q=applicant:华为 AND ipc:H01M",
    
    # 宁德时代的电池专利
    "q=applicant:宁德时代 AND ipc:H01M",
]
```

### 场景3：按时间筛选
```python
search_queries = [
    # 2024年新专利
    "q=title:石墨烯 AND applicationYear:2024",
    
    # 近3年专利
    "q=title:电池 AND applicationYear:[2022 TO 2025]",
]
```

## 八、最佳实践

### 1. 搜索策略
```python
def build_search_query(keywords, ipc_code=None, year=None, status=None):
    """构建搜索查询"""
    query_parts = []
    
    # 关键词搜索
    if keywords:
        query_parts.append(keywords)
    
    # IPC分类号
    if ipc_code:
        query_parts.append(f"ipc:{ipc_code}")
    
    # 时间范围
    if year:
        query_parts.append(f"applicationYear:{year}")
    
    # 法律状态
    if status:
        query_parts.append(f"legalStatus:{status}")
    
    # 用AND连接
    return " AND ".join(query_parts)
```

### 2. 分页处理
```python
def fetch_all_patents(query, max_pages=100):
    """获取所有搜索结果"""
    all_patents = []
    page = 1
    
    while page <= max_pages:
        result = client.search(query, page=page, page_size=50)
        if not result.get('patents'):
            break
        
        all_patents.extend(result['patents'])
        page += 1
        
        # 避免API限流
        time.sleep(0.1)
    
    return all_patents
```

### 3. 缓存策略
```python
# 对高频访问的专利进行缓存
cache_ttl = 86400  # 24小时

def get_patent_with_cache(patent_id):
    """带缓存的专利查询"""
    cache_key = f"patent:{patent_id}"
    
    # 先查缓存
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # 无缓存，调用API
    patent = client.get_patent(patent_id)
    
    # 写入缓存
    cache.set(cache_key, patent, ttl=cache_ttl)
    
    return patent
```

## 九、免费版限制提醒

```python
FREE_TIER_LIMITS = {
    "search": "50次/天",
    "claims": "2积分/次",
    "description": "2积分/次",
    "sorting": "不支持",
    "advanced_stats": "不支持",
    "semantic_search": "不支持",
}
```

## 十、总结

### 可用字段列表
```
title, summary, applicant, inventor,
ipc, applicationYear, documentYear,
legalStatus, agency
```

### 组合语法
```
q=字段1:值1 AND 字段2:值2
```

### 分页语法
```
p=页码 ps=每页条数
```

---

你现在可以开始用这些字段构建搜索功能了！
