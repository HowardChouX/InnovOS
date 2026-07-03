#!/usr/bin/env python3
"""PatentHub API 多接口测试"""

import requests
import json

TOKEN = "6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc"
BASE_URL = "https://www.patenthub.cn/api"

def test_api(endpoint, name, params):
    """测试单个接口"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        success = data.get('success', False)
        code = data.get('code', 0)
        status = "✓" if success else "✗"

        print(f"{status} {name} (code={code})")

        if success and data.get('patents'):
            print(f"    返回 {len(data['patents'])} 条专利")
            if data['patents']:
                first = data['patents'][0]
                print(f"    示例: {first.get('id', 'N/A')} - {first.get('title', 'N/A')[:50]}")

        return success

    except Exception as e:
        print(f"✗ {name} - 错误: {e}")
        return False

if __name__ == "__main__":
    print("PatentHub API 接口测试")
    print("=" * 60)

    # 测试参数
    params_search = {"t": TOKEN, "q": "石墨烯", "v": 1, "ps": 2}
    params_detail = {"t": TOKEN, "id": "CN111344253A", "v": 1}
    params_stats = {"t": TOKEN, "q": "石墨烯", "c": "ipc", "v": 1, "limit": 5}

    # 逐个测试
    tests = [
        ("s", "搜索接口", params_search),
        ("patent/base", "基本信息接口", params_detail),
        ("patent/detail", "详细信息接口", params_detail),
        ("patent/claims", "权利要求接口", params_detail),
        ("patent/desc", "说明书接口", params_detail),
        ("ration", "统计分析接口", params_stats),
    ]

    results = []
    for endpoint, name, params in tests:
        success = test_api(endpoint, name, params)
        results.append((name, success))
        print()

    # 总结
    print("=" * 60)
    print("测试结果总结:")
    print("=" * 60)
    for name, success in results:
        status = "可用" if success else "受限"
        print(f"  {name}: {status}")

    print("\n可用的接口可以用于集成!")
