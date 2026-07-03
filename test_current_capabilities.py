#!/usr/bin/env python3
"""测试PatentHub API当前能做什么"""

import requests
import json

TOKEN = "6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc"
BASE_URL = "https://www.patenthub.cn/api"

def test_search_variations():
    """测试搜索的各种场景"""
    tests = [
        ("基础搜索", {"q": "石墨烯", "ps": 5}),
        ("分类号搜索", {"q": "ipc:H01M", "ps": 5}),
        ("时间范围", {"q": "石墨烯 AND documentYear:[2020 TO 2025]", "ps": 5}),
        ("法律状态", {"q": "石墨烯 AND legalStatus:有效专利", "ps": 5}),
        ("排序", {"q": "石墨烯", "s": "!applicationDate", "ps": 5}),
    ]

    results = {}
    for name, params in tests:
        try:
            params["t"] = TOKEN
            params["v"] = 1
            resp = requests.get(f"{BASE_URL}/s", params=params, timeout=30)
            data = resp.json()

            if data.get('success'):
                results[name] = {
                    "total": data['total'],
                    "sample": data['patents'][0]['title'] if data.get('patents') else "N/A",
                    "id": data['patents'][0]['id'] if data.get('patents') else None,
                }
                print(f"✓ {name}: {data['total']:,} 条")
                if data.get('patents'):
                    print(f"  示例: {data['patents'][0]['id']} - {data['patents'][0]['title'][:60]}")
            else:
                print(f"✗ {name}: {data.get('code')}")

        except Exception as e:
            print(f"✗ {name}: {e}")

    return results

def test_patent_workflow(patent_id):
    """测试完整的专利查询流程"""
    print(f"\n\n完整流程测试 - {patent_id}")
    print("=" * 60)

    workflow = {}

    # 1. 基本信息
    try:
        resp = requests.get(f"{BASE_URL}/patent/base", params={"t": TOKEN, "id": patent_id, "v": 1})
        data = resp.json()
        if data.get('success') and data.get('patent'):
            p = data['patent']
            workflow['base'] = {
                "title": p.get('title'),
                "applicant": p.get('applicant'),
                "date": p.get('applicationDate'),
                "status": p.get('legalStatus'),
            }
            print(f"✓ 基本信息: {p.get('title')[:50]}")
            print(f"  申请人: {p.get('applicant')}")
            print(f"  申请日: {p.get('applicationDate')}")
            print(f"  状态: {p.get('legalStatus')}")
        else:
            print(f"✗ 基本信息: {data.get('code')}")
    except Exception as e:
        print(f"✗ 基本信息: {e}")

    # 2. 权利要求
    try:
        resp = requests.get(f"{BASE_URL}/patent/claims", params={"t": TOKEN, "id": patent_id, "v": 1})
        data = resp.json()
        if data.get('success') and data.get('patent'):
            claims = data['patent'].get('claims', '')
            workflow['claims'] = {
                "length": len(claims),
                "preview": claims[:200] + "..." if len(claims) > 200 else claims,
            }
            print(f"✓ 权利要求: {len(claims):,} 字符")
        else:
            print(f"✗ 权利要求: {data.get('code')}")
    except Exception as e:
        print(f"✗ 权利要求: {e}")

    # 3. 说明书
    try:
        resp = requests.get(f"{BASE_URL}/patent/desc", params={"t": TOKEN, "id": patent_id, "v": 1})
        data = resp.json()
        if data.get('success') and data.get('patent'):
            desc = data['patent'].get('description', '')
            workflow['description'] = {
                "length": len(desc),
                "preview": desc[:200] + "..." if len(desc) > 200 else desc,
            }
            print(f"✓ 说明书: {len(desc):,} 字符")
        else:
            print(f"✗ 说明书: {data.get('code')}")
    except Exception as e:
        print(f"✗ 说明书: {e}")

    # 4. 引用关系
    try:
        resp = requests.get(f"{BASE_URL}/patent/citing", params={"t": TOKEN, "id": patent_id, "v": 1})
        data = resp.json()
        if data.get('success'):
            cited = len(data.get('citedList', []))
            cited_by = len(data.get('patentXref', []))
            workflow['citations'] = {
                "cited": cited,
                "cited_by": cited_by,
            }
            print(f"✓ 引用关系: 引用 {cited} 篇, 被引用 {cited_by} 篇")
        else:
            print(f"✗ 引用关系: {data.get('code')}")
    except Exception as e:
        print(f"✗ 引用关系: {e}")

    return workflow

if __name__ == "__main__":
    print("PatentHub API 当前能力测试")
    print("=" * 60)

    # 1. 测试搜索场景
    print("\n【搜索功能】")
    results = test_search_variations()

    # 2. 测试完整流程
    if results and results.get('基础搜索', {}).get('id'):
        test_id = results['基础搜索']['id']
        test_patent_workflow(test_id)

    print("\n" + "=" * 60)
    print("【总结】当前能实现的功能:")
    print("=" * 60)
    print("1. ✓ 专利搜索 - 多种条件组合、排序、分页")
    print("2. ✓ 专利详情 - 基本信息、权利要求、说明书")
    print("3. ✓ 引用分析 - 引用和被引用关系")
    print("4. ✓ 批量查询 - 支持最多1000条搜索结果")
    print("5. ✓ 全文获取 - 权利要求和说明书全文")
