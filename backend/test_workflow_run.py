#!/usr/bin/env python3
"""Run full workflow test with ratings for task_id=46"""
import httpx
import json
import time
import sys

BASE = "http://localhost:8000"
TOKEN = None
TASK_ID = 46

def get_token():
    resp = httpx.post(f"{BASE}/api/auth/login", json={
        "username": "InnovOS2026@admin", "password": "K9#mP7$xR2!vL8"
    })
    return resp.json()["access_token"]

def headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def get_workflow():
    resp = httpx.get(f"{BASE}/api/workflow/{TASK_ID}", headers=headers())
    return resp.json()["data"]

def submit_proceed(ratings=None):
    body = {}
    if ratings:
        body["ratings"] = ratings
    resp = httpx.post(f"{BASE}/api/analysis/{TASK_ID}/proceed", headers=headers(), json=body)
    return resp.json()

def poll_until(agent_id, timeout=300):
    """Poll until the given agent reaches awaiting_rating or completed"""
    start = time.time()
    last_status = ""
    while time.time() - start < timeout:
        time.sleep(3)
        wf = get_workflow()
        status = wf["status"]
        steps = wf["steps"]
        
        # Find this agent's step
        agent_step = None
        for s in steps:
            if s["agentId"] == agent_id:
                agent_step = s
                break
        
        if agent_step:
            step_status = agent_step["status"]
            if step_status != last_status:
                elapsed = int(time.time() - start)
                print(f"  [{elapsed}s] {agent_id}: {step_status}")
                last_status = step_status
            
            if status == "awaiting_rating" and step_status == "completed":
                return True, agent_step
            if status == "failed":
                print(f"  FAILED at {agent_id}")
                return False, agent_step
        
        # Also check for stuck state
        if time.time() - start > 10 and last_status == "running":
            # Check if another agent is running
            for s in steps:
                if s["agentId"] != agent_id and s["status"] == "running":
                    print(f"  WARNING: {s['agentId']} is running while waiting for {agent_id}")
    
    print(f"  TIMEOUT waiting for {agent_id}")
    return False, None

def parse_output(step):
    if not step or not step.get("output"):
        return {}
    out = step["output"]
    if isinstance(out, str):
        return json.loads(out)
    return out

def main():
    global TOKEN
    TOKEN = get_token()
    print("Login OK")

    # Step 1: Rate agent1 demands
    print("\n=== Agent1 (需求洞察) - Submitting ratings ===")
    wf = get_workflow()
    agent1 = None
    for s in wf["steps"]:
        if s["agentId"] == "agent1":
            agent1 = s
            break
    
    output = parse_output(agent1)
    demands = output.get("demands", [])
    print(f"  Demands: {len(demands)}")
    for d in demands:
        print(f"    {d['id']}: {d['description'][:50]} (priority={d['priority']})")
    
    # Rate demands: top 3 get 5 stars, next 2 get 4, last 1 gets 3
    ratings = []
    for i, d in enumerate(demands):
        if i < 3:
            score = 5
        elif i < 5:
            score = 4
        else:
            score = 3
        ratings.append({"demandId": d["id"], "score": score})
    
    print(f"  Ratings: {json.dumps(ratings, ensure_ascii=False)}")
    resp = submit_proceed(ratings)
    print(f"  Proceed: {resp}")

    # Step 2: Wait for agent2 (问题建模)
    print("\n=== Agent2 (问题建模) - Waiting ===")
    ok, step = poll_until("agent2")
    if ok:
        output = parse_output(step)
        innovations = output.get("innovations", [])
        print(f"  Innovations: {len(innovations)}")
        for inn in innovations[:5]:
            print(f"    {inn.get('id', '?')}: {inn.get('description', '?')[:60]}")
        
        # Rate innovations
        ratings = []
        for i, inn in enumerate(innovations):
            score = 5 if i < 2 else 4 if i < 4 else 3
            ratings.append({"demandId": inn.get("id", str(i)), "score": score})
        
        print(f"  Submitting {len(ratings)} ratings...")
        resp = submit_proceed(ratings)
        print(f"  Proceed: {resp}")
    else:
        print("  Agent2 failed or timed out")
        return

    # Step 3: Wait for agent5 (专利分析)
    print("\n=== Agent5 (专利分析) - Waiting ===")
    ok, step = poll_until("agent5")
    if ok:
        output = parse_output(step)
        patents = output.get("patents", [])
        print(f"  Patents found: {len(patents)}")
        for pt in patents[:5]:
            print(f"    {pt.get('title', '?')[:50]} (relevance={pt.get('relevance', '?')})")
        
        # Rate patents: high relevance get 5, medium 4, low 3
        ratings = []
        for i, pt in enumerate(patents):
            rel = pt.get("relevance", 0)
            if rel >= 0.8:
                score = 5
            elif rel >= 0.5:
                score = 4
            else:
                score = 3
            ratings.append({"demandId": pt.get("id", str(i)), "score": score})
        
        print(f"  Submitting {len(ratings)} patent ratings...")
        resp = submit_proceed(ratings)
        print(f"  Proceed: {resp}")
    else:
        print("  Agent5 failed or timed out")
        return

    # Step 4: Wait for agent3 (方案生成)
    print("\n=== Agent3 (方案生成) - Waiting ===")
    ok, step = poll_until("agent3")
    if ok:
        output = parse_output(step)
        solutions = output.get("solutions", []) if isinstance(output.get("solutions"), list) else []
        print(f"  Solutions: {len(solutions)}")
        for sol in solutions[:5]:
            title = sol.get("title", "?")
            refs = sol.get("referencedPatents", [])
            print(f"    {title[:50]}")
            if refs:
                print(f"      Ref patents: {refs[:3]}")
        
        # Confirm solutions
        ratings = []
        for i, sol in enumerate(solutions):
            ratings.append({"demandId": sol.get("id", str(i)), "score": 5})
        
        print(f"  Confirming {len(ratings)} solutions...")
        resp = submit_proceed(ratings)
        print(f"  Proceed: {resp}")
    else:
        print("  Agent3 failed or timed out")
        return

    # Step 5: Wait for agent4 (方案评估)
    print("\n=== Agent4 (方案评估) - Waiting ===")
    ok, step = poll_until("agent4")
    if ok:
        output = parse_output(step)
        evaluations = output.get("evaluations", [])
        print(f"  Evaluations: {len(evaluations)}")
        for ev in evaluations[:5]:
            print(f"    {ev.get('solutionTitle', '?')[:40]} overall={ev.get('overall', '?')} grade={ev.get('grade', '?')}")
        
        # Confirm evaluations
        ratings = []
        for i, ev in enumerate(evaluations):
            ratings.append({"demandId": ev.get("solutionId", str(i)), "score": 5})
        
        print(f"  Confirming {len(ratings)} evaluations...")
        resp = submit_proceed(ratings)
        print(f"  Proceed: {resp}")
    else:
        print("  Agent4 failed or timed out")
        return

    # Step 6: Wait for agent6 (成果转化)
    print("\n=== Agent6 (成果转化) - Waiting ===")
    ok, step = poll_until("agent6")
    if ok:
        output = parse_output(step)
        report = output.get("report", output)
        print(f"  Report generated: Yes")
        if isinstance(report, dict):
            print(f"  Title: {report.get('title', '?')[:60]}")
            print(f"  Sections: {len(report.get('sections', []))}")
            print(f"  Recommendations: {len(report.get('recommendations', []))}")
    else:
        print("  Agent6 failed or timed out")
        return

    # Final summary
    print("\n" + "=" * 60)
    print("  WORKFLOW COMPLETE!")
    print("=" * 60)
    wf = get_workflow()
    print(f"  Final status: {wf['status']}")
    for s in wf["steps"]:
        print(f"  {s['agentId']}: {s['status']} ({s.get('duration', 'N/A')})")

if __name__ == "__main__":
    main()
