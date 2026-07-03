#!/usr/bin/env python3
"""测试PatentHub搜索字段和语法"""

import requests
import json

TOKEN = "6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc"
BASE_URL = "https://www.patenthub.cn/api"

def test_search_field(field, value, name=""):
    """测试单个搜索字段"""
    try:
        params = {
            "t": TOKEN,
            "q": f"{field}:{value}" if field else value,
            "ps": 3,
            "v": 1,
        }
        resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
        data = resp.json()

        if data.get('success'):
            total = data.get('total', 0)
            print(f"✓ {name or field}: {total:,} 条")
            if data.get('patents'):
                p = data['patents'][0]
                print(f"  示例: {p.get('id')} - {p.get('title', '')[:50]}")
            return total
        else:
            print(f"✗ {name or field}: code={data.get('code')}")
            return 0

    except Exception as e:
        print(f"✗ {name or field}: {e}")
        return 0

if __name__ == "__main__":
    print("PatentHub 搜索字段测试")
    print("=" * 60)

    # 基础搜索字段
    print("\n【基础字段】")
    test_search_field(None, "石墨烯", "全文搜索（石墨烯）")
    test_search_field("title", "石墨烯", "标题字段")
    test_search_field("summary", "石墨烯", "摘要字段")
    test_search_field("applicant", "北京大学", "申请人字段")
    test_search_field("inventor", "张三", "发明人字段")

    # 分类号字段
    print("\n【分类号字段】")
    test_search_field("ipc", "C01B32/18", "IPC分类号")
    test_search_field("ipc", "H01M", "IPC大类")

    # 法律状态
    print("\n【法律状态】")
    test_search_field("legalStatus", "有效专利", "法律状态")
    test_search_field("legalStatus", "公开", "法律状态")
    test_search_field("legalStatus", "发明授权", "专利类型")

    # 时间字段
    print("\n【时间字段】")
    test_search_field("applicationYear", "2024", "申请年份")
    test_search_field("documentYear", "2024", "公开年份")

    # 代理机构
    print("\n【代理机构】")
    test_search_field("agency", "北京市柳沈律师事务所", "代理机构")

    # 组合搜索
    print("\n【组合搜索】")
    tests = [
        ("石墨烯 AND H01M", "关键词 + IPC"),
        ("石墨烯 AND 有效专利", "关键词 + 法律状态"),
        ("石墨烯 AND 2024", "关键词 + 年份"),
        ("申请人:华为 AND ipc:H04", "申请人 + IPC"),
    ]

    for query, name in tests:
        try:
            params = {"t": TOKEN, "q": query, "ps": 3, "v": 1}
            resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                total = data.get('total', 0)
                print(f"✓ {name}: {total:,} 条")
            else:
                print(f"✗ {name}: code={data.get('code')}")

        except Exception as e:
            print(f"✗ {name}: {e}")

    # 排序
    print("\n【排序方式】")
    sort_tests = [
        ("!applicationDate", "申请时间降序"),
        ("!documentDate", "公开时间降序"),
        ("relation", "相关度（默认）"),
    ]

    for sort, name in sort_tests:
        try:
            params = {"t": TOKEN, "q": "石墨烯", "s": sort, "ps": 3, "v": 1}
            resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                total = data.get('total', 0)
                print(f"✓ {name}: {total:,} 条")
            else:
                print(f"✗ {name}: code={data.get('code')}")

        except Exception as e:
            print(f"✗ {name}: {e}")

    print("\n" + "=" * 60)
    print("【总结】常用搜索语法")
    print("=" * 60)
    print("1. 全文搜索: q=石墨烯")
    print("2. 字段搜索: q=field:value")
    print("3. 组合搜索: q=field1:value1 AND field2:value2")
    print("4. 排序: s=!applicationDate（降序）")
    print("5. 分页: p=页码 ps=每页条数")
