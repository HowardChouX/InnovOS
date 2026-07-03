#!/usr/bin/env python3
"""PatentHub API 测试脚本"""

import requests
import json
import sys

TOKEN = "6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc"
BASE_URL = "https://www.patenthub.cn/api"

def test_search(query="石墨烯", page=1, page_size=5):
    """测试专利搜索接口"""
    url = f"{BASE_URL}/s"
    params = {
        "t": TOKEN,
        "q": query,
        "v": 1,
        "p": page,
        "ps": page_size,
    }

    try:
        print(f"测试搜索接口: {url}")
        print(f"参数: q={query}, page={page}, pageSize={page_size}")
        print("-" * 60)

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        print(f"状态码: {data.get('code')}")
        print(f"成功: {data.get('success')}")
        print(f"总条数: {data.get('total')}")
        print(f"返回条数: {len(data.get('patents', []))}")

        if data.get('patents'):
            print("\n第一个专利:")
            patent = data['patents'][0]
            print(f"  ID: {patent.get('id')}")
            print(f"  标题: {patent.get('title')}")
            print(f"  申请人: {patent.get('applicant')}")
            print(f"  申请日: {patent.get('applicationDate')}")
            print(f"  状态: {patent.get('legalStatus')}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        print(f"响应内容: {resp.text[:500]}")
        return None

def test_patent_detail(patent_id):
    """测试专利详情接口"""
    url = f"{BASE_URL}/patent/detail"
    params = {
        "t": TOKEN,
        "id": patent_id,
        "v": 1,
    }

    try:
        print(f"\n\n测试详情接口: {url}")
        print(f"参数: id={patent_id}")
        print("-" * 60)

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        print(f"状态码: {data.get('code')}")
        print(f"成功: {data.get('success')}")

        if data.get('patent'):
            patent = data['patent']
            print(f"\n专利详情:")
            print(f"  ID: {patent.get('id')}")
            print(f"  标题: {patent.get('title')}")
            print(f"  申请人: {patent.get('applicant')}")
            print(f"  权利要求长度: {len(patent.get('claims', ''))} 字符")
            print(f"  说明书长度: {len(patent.get('description', ''))} 字符")

        return data

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        print(f"响应内容: {resp.text[:500]}")
        return None

if __name__ == "__main__":
    print("PatentHub API 测试")
    print("=" * 60)

    # 1. 测试搜索
    search_result = test_search("石墨烯", page_size=3)

    # 2. 如果有结果，测试详情
    if search_result and search_result.get('patents'):
        first_patent_id = search_result['patents'][0]['id']
        test_patent_detail(first_patent_id)

    print("\n" + "=" * 60)
    print("测试完成")
