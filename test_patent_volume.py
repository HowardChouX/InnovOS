#!/usr/bin/env python3
"""测试PatentHub专利库总规模"""

import requests
import json

TOKEN = "6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc"
BASE_URL = "https://www.patenthub.cn/api"

def test_global_stats():
    """测试全局统计（通过搜索空查询或通用查询）"""
    tests = [
        ("全局总数", {"q": "*", "ps": 1}),
        ("中国专利", {"ds": "cn", "q": "*", "ps": 1}),
        ("全球专利", {"ds": "all", "q": "*", "ps": 1}),
        ("按年度", {"q": "*", "s": "!applicationDate", "ps": 1}),
    ]

    print("PatentHub 专利库总规模")
    print("=" * 60)

    results = []
    for name, params in tests:
        try:
            params["t"] = TOKEN
            params["v"] = 1
            resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                total = data.get('total', 0)
                results.append((name, total))
                print(f"✓ {name}: {total:,} 条")
            else:
                print(f"✗ {name}: code={data.get('code')}")
                results.append((name, 0))

        except Exception as e:
            print(f"✗ {name}: {e}")
            results.append((name, 0))

    return results

def test_category_stats():
    """测试分类统计"""
    categories = [
        ("IPC分类号", "ipc"),
        ("法律状态", "legalStatus"),
        ("专利类型", "type"),
        ("申请年份", "applicationYear"),
    ]

    print("\n\n分类维度统计")
    print("=" * 60)

    for name, field in categories:
        try:
            params = {
                "t": TOKEN,
                "q": "*",
                "c": field,
                "v": 1,
                "limit": 5,
            }
            resp = requests.get(f"{BASE_URL}/ration", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                analysis = data.get('analysis_total', '[]')
                if isinstance(analysis, str):
                    analysis = json.loads(analysis)

                if analysis:
                    total = sum(item.get('count', 0) for item in analysis[:5])
                    print(f"✓ {name}: (前5项共 {total:,} 条)")
                    for item in analysis[:3]:
                        print(f"    {item.get('key', 'N/A')}: {item.get('count', 0):,}")
                else:
                    print(f"✓ {name}: 无数据")
            else:
                print(f"✗ {name}: code={data.get('code')}")

        except Exception as e:
            print(f"✗ {name}: {e}")

def test_patent_type_breakdown():
    """测试按专利类型分布"""
    patent_types = ["发明公开", "发明授权", "实用新型", "外观设计"]

    print("\n\n专利类型分布")
    print("=" * 60)

    for ptype in patent_types:
        try:
            params = {
                "t": TOKEN,
                "q": f"type:{ptype}",
                "ps": 1,
                "v": 1,
            }
            resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                total = data.get('total', 0)
                print(f"✓ {ptype}: {total:,} 条")
            else:
                print(f"✗ {ptype}: code={data.get('code')}")

        except Exception as e:
            print(f"✗ {ptype}: {e}")

if __name__ == "__main__":
    print("PatentHub API 专利库规模统计")
    print("=" * 60)

    # 1. 全局统计
    results = test_global_stats()

    # 2. 分类统计（可能受限）
    test_category_stats()

    # 3. 专利类型分布
    test_patent_type_breakdown()

    # 总结
    print("\n" + "=" * 60)
    print("【总结】")
    print("=" * 60)
    if results:
        # 找出最大值
        max_total = max(r[1] for r in results if r[1] > 0)
        if max_total:
            print(f"专利库预估总规模: {max_total:,} 条")
        else:
            print("无法获取总规模")
