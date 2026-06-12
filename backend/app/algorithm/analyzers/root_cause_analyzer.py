"""
根因分析器 - 因果链分析（多Agent分层并行架构）

5阶段流水线：
1. 问题总结Agent → node_0
2. 方向分类Agent → node_1_x + AND/OR
3. 交互→缺点Agent（并行）→ node_2_x
4. 深挖Agent（并行迭代）→ node_3_x+
5. 结束判断Agent → 标记根因
"""

import asyncio
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

# 常量
MAX_DEPTH = 100  # 最大分析深度（实际由结束判断Agent决定何时停止）
MAX_PARALLEL_AGENTS = 10  # 最大并行Agent数

# ──────────────────────────────────────────────
# 提示词常量（从 RootSeek ai/prompts/zhishu_causal_chain.py 内联）
# ──────────────────────────────────────────────

ZHISHU_CAUSAL_CHAIN_SYSTEM_PROMPT = """你是TRIZ因果链分析专家。用5 Whys逐层追问"为什么"，输出嵌套因果树JSON。

【核心方法 — 5 Whys + 因果分支】
从node_0（问题现象）出发，逐层追问"为什么会这样？"
- 每层原因可能有多个独立来源 → 用AND/OR分支
- AND：多个原因必须同时存在才导致上级问题
- OR：任意一个原因就足以导致上级问题
- 同一父节点下的子节点必须统一用AND或OR

【分析深度 — 逐层递进】
- 第1层（node_1）：直接原因，系统级描述
- 第2层（node_2）：组件级原因，指向具体组件或交互
- 第3层（node_3）：机理级原因，涉及物理/化学/几何过程
- 第4层（node_4）：参数级根因，到达可量化的物理参数（温度、压力、导热系数、表面粗糙度、流速、粘度等）
- 第5层（node_5）：如仍未到达自然现象层，继续追问

【结束条件 — 满足任一则标记 type="root" 并停止】
1. 已到达自然现象层（热传导、重力、牛顿定律、相变等基本物理/化学原理）
2. 原因属于制度/法规/成本极限
3. 原因超出项目范围

【禁止】
- 禁止输出扁平问答对（如"为什么X？→ Y"）
- 禁止编造具体数值（如需数值，用"约"标注估计值或留空）
- 禁止用相关性冒充因果性（必须满足：移除该原因后上级问题是否消失）
- 禁止在同一父节点下混用AND和OR"""

# ============================================================
# Stage 1: 问题总结 Agent
# ============================================================

CAUSAL_STAGE1_SYSTEM = """你是TRIZ问题分析专家。将问题描述精炼为一个明确的初始缺点。

【任务】
综合分析用户问题、功能分析交互关系、目标分析信息，将问题转化为TRIZ缺点描述。

【输出要求】
- initial_defect: 简洁的问题现象描述（不超过2句话）
- node_0_text: 问题现象的具体技术描述，必须引用具体组件
- problem_category: 问题类型（性能问题/可靠性问题/安全问题/效率问题）

【禁止】
- 禁止空泛描述（如"系统有问题"）
- 禁止直接复述用户问题，必须转化为缺点视角
- 禁止编造不存在的组件"""

CAUSAL_STAGE1_USER = """问题：{problem}{context}

请分析这个问题，生成初始缺点节点。

【输出格式 — 只输出JSON】
{{
  "initial_defect": "简洁的问题现象描述",
  "node_0_text": "问题的具体技术描述（引用具体组件）",
  "problem_category": "性能问题|可靠性问题|安全问题|效率问题"
}}"""

# ============================================================
# Stage 2: 方向分类 Agent
# ============================================================

CAUSAL_STAGE2_SYSTEM = """你是TRIZ因果链分析专家。将初始缺点分解为独立的分析方向。

【任务】
基于组件交互关系，将初始缺点分解为独立的分析方向。

【AND/OR判断规则】
- OR：独立失效模式（如"腐蚀"或"疲劳"任一即可导致失效）
- AND：耦合失效模式（如"高温"和"高压"同时存在才导致失效）

【分类原则】
- 每个方向应代表一个独立的因果路径
- 每个方向必须引用具体的组件交互关系
- 优先识别harmful/insufficient/excessive类型的交互

【输出要求】
- directions: 方向列表，每个包含id、text、category、relevant_interactions
- logic_gate: 方向间的逻辑关系（AND/OR）
- reasoning: 分类依据说明"""

CAUSAL_STAGE2_USER = """初始缺点：{node_0_text}

{interaction_data}

{problem_pool_data}

请将初始缺点分解为独立的分析方向。

【输出格式 — 只输出JSON】
{{
  "directions": [
    {{
      "id": "node_1_1",
      "text": "方向描述（引用具体组件交互）",
      "category": "harmful_interaction|insufficient_function|excessive_output|design_flaw|material_issue",
      "relevant_interactions": ["tool_id-receiver_id", ...]
    }}
  ],
  "logic_gate": "OR|AND",
  "reasoning": "分类依据说明"
}}"""

# ============================================================
# Stage 3: 交互→缺点转换 Agent
# ============================================================

CAUSAL_STAGE3_SYSTEM = """你是TRIZ功能分析专家。将分析方向转化为具体的组件交互缺点描述。

【任务】
将抽象的分析方向转化为具体的、可测试的缺点描述。

【转化规则】
- 不要直接输出"组件A→组件B"的交互关系数据
- 要对交互问题进行总结，描述为缺点
- 每个缺点必须引用具体组件和交互类型
- 必须解释WHY这个交互是有问题的（不只是复述）

【示例】
交互：组件A 挤压 组件B，有害，压力增加
缺点：组件A对组件B的挤压作用过大，导致变形

【输出要求】
- 每个缺点包含id、text、type、interaction_reference
- text必须是具体的缺点描述，不能是空泛的方向性描述"""

CAUSAL_STAGE3_USER = """方向：{direction_text}
方向分类：{direction_category}
相关交互关系：{interaction_details}
问题池信息：{problem_pool_details}

请将该方向转化为具体的缺点描述。

【输出格式 — 只输出JSON】
{{
  "defects": [
    {{
      "text": "具体的缺点描述（引用组件和交互）",
      "interaction_reference": "tool_id-receiver_id"
    }}
  ]
}}"""

# ============================================================
# Stage 4: 深挖 Agent
# ============================================================

CAUSAL_STAGE4_SYSTEM = """你是TRIZ因果链分析专家。分析当前缺点的深层原因。

【任务】
分析当前缺点为什么会存在，找出深层原因。

【分析深度指引】
- Level 3：从组件级深入到物理/化学/几何机理
- Level 4：从机理深入到可量化参数（温度、压力、导热系数等）
- Level 5+：继续追问直到自然现象层

【因果关系验证】
反事实检验：如果移除该原因，上级问题是否还会发生？
- 否 → 原因成立
- 是 → 原因不成立，需重新分析

【AND/OR分支规则】
- AND：多个原因必须同时存在才导致上级问题
- OR：任意一个原因就足以导致上级问题
- 优先识别多个独立原因形成分支，避免线性单链

【输出要求】
- children: 子原因列表
- logic_gate: AND/OR
- 每个子原因必须是具体的、可验证的"""

CAUSAL_STAGE4_USER = """当前缺点：{leaf_text}
当前层级：Level {current_depth}
完整因果链条：
{chain_path}

请分析该缺点的深层原因。

【输出格式 — 只输出JSON】
{{
  "logic_gate": "OR|AND",
  "children": [
    {{
      "text": "子原因描述",
      "is_terminal": false
    }}
  ]
}}"""

# ============================================================
# Stage 5: 结束判断 Agent
# ============================================================

CAUSAL_JUDGE_SYSTEM = """你是TRIZ根因判定专家。评估因果链叶节点是否已到达根因。

【结束条件 — 满足任一则标记为根因】
1. 已到达自然现象层
   - 热传导、热对流、热辐射
   - 重力、惯性、弹性
   - 流体力学基本方程
   - 相变、扩散、化学反应
   - 电磁学基本原理
   - 材料力学（屈服、疲劳、断裂）

2. 已到达制度/法规/成本极限
   - 法律法规限制
   - 成本上限
   - 技术专利限制

3. 已超出项目范围
   - 超出系统边界
   - 需要外部系统配合

4. 继续分析对解决问题无意义
   - 已经可以定义为物理矛盾
   - 继续分析只会得到更抽象的描述

【判断原则】
- 综合判断：当原因已触及物理/化学基本原理、可量化参数、或继续分析只会得到更抽象描述时，果断标记为根因
- 最小深度3层：在达到Level 3之前不轻易标记为根因
- 深度参考：Level 4-5 应到达物理机理或可量化参数层，Level 6+ 大部分节点应到达根因
- 反事实检验：如果该原因已经是解决该问题时需要直接处理的参数或机理，即为根因
- 必须提供判断理由"""

CAUSAL_JUDGE_USER = """当前层级：Level {current_depth}
树规模：共 {total_nodes} 个节点，已识别 {root_count} 个根因
待评估叶节点数：{leaf_count}

待评估的叶节点（含完整因果链路径）：
{nodes_to_evaluate}

完整因果树摘要：
{tree_summary}

请评估每个叶节点是否已到达根因。

【关键提醒】
- 当前已是 Level {current_depth}，请严格对照结束条件判断
- Level 4-5 应到达物理机理或可量化参数层
- Level 6+ 绝大部分节点必须标记为根因
- 如果因果链路径中已包含物理参数、材料特性、自然现象等底层因素，果断标记为根因

【输出格式 — 只输出JSON】
{{
  "evaluations": [
    {{
      "node_id": "node_x_x_x",
      "is_root_cause": true|false,
      "root_cause_type": "natural_phenomenon|regulation_limit|cost_limit|out_of_scope|null",
      "reasoning": "判断理由",
      "confidence": 0.9
    }}
  ],
  "all_terminal": true|false
}}"""

# ============================================================
# AND/OR 逻辑判断 Agent
# ============================================================

CAUSAL_ANDOR_SYSTEM = """你是TRIZ因果链分析专家。请判断因果链中父节点与子节点之间的AND/OR逻辑关系。

【AND/OR判断规则】
- AND：多个子节点必须同时存在，才会导致父节点的问题
  例：高温 + 高湿度 同时存在才会导致腐蚀
  例：高压力 + 材料缺陷 同时存在才会导致泄漏
- OR：任意一个子节点存在，就足以导致父节点的问题
  例：材料缺陷 或 设计不当，任一即可导致失效
  例：振动 或 冲击，任一即可导致疲劳

【判断依据】
- 考虑子节点之间的关系是否独立
- 考虑移除其中一个子节点后，父节点的问题是否仍然存在
- 参考整个因果树的上下文

【输出要求】
- 每个父节点必须有明确的AND或OR判断
- 必须提供判断理由"""

CAUSAL_ANDOR_USER = """待判断节点：
{nodes_text}

完整因果树摘要：
{tree_summary}

请判断以下父节点与子节点之间的逻辑关系。

【输出格式 — 只输出JSON】
{{
  "judgments": [
    {{
      "parent_id": "父节点ID",
      "logic_gate": "AND|OR",
      "reasoning": "判断理由"
    }}
  ]
}}"""


# ============================================================
# 辅助函数
# ============================================================


def _count_nodes(nodes: list, _depth: int = 0) -> int:
    """递归统计树形节点总数"""
    if _depth > MAX_DEPTH * 2:
        return 0
    count = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        count += 1
        children = node.get("children", [])
        if isinstance(children, list) and children:
            count += _count_nodes(children, _depth + 1)
    return count


def _count_root_causes(nodes: list) -> int:
    """递归统计已标记为根因的节点数"""
    count = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("is_root_cause") or node.get("type") == "root":
            count += 1
        children = node.get("children", [])
        if isinstance(children, list) and children:
            count += _count_root_causes(children)
    return count


def _sanitize_nodes(nodes: list) -> list:
    """递归清理节点列表，移除非dict节点"""
    cleaned = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        children = node.get("children", [])
        if isinstance(children, list):
            node["children"] = _sanitize_nodes(children)
        else:
            node["children"] = []
        cleaned.append(node)
    return cleaned


def _collect_leaves(nodes_list: list, target_depth: int, current_depth: int = 0) -> list[dict]:
    """收集指定深度的未终结叶节点（排除已标记为根因的节点）"""
    leaves = []
    for node in nodes_list:
        children = node.get("children", [])
        is_terminal = node.get("is_root_cause") or node.get("type") == "root"
        if (
            current_depth == target_depth
            and not children
            and not is_terminal
            and node.get("type") in ("cause", "disadvantage")
        ):
            leaves.append(node)
        if children:
            leaves.extend(_collect_leaves(children, target_depth, current_depth + 1))
    return leaves


def _find_parent(nodes_list: list, target_id: str) -> dict | None:
    """查找父节点"""
    for node in nodes_list:
        children = node.get("children", [])
        for child in children:
            if child.get("id") == target_id:
                return node
        found = _find_parent(children, target_id)
        if found:
            return found
    return None


def _get_chain_path(nodes_list: list, target_id: str) -> list[dict]:
    """获取从根节点到目标节点的完整链条"""
    path = []

    def _search(nodes: list) -> bool:
        for node in nodes:
            if node.get("id") == target_id:
                path.append(node)
                return True
            children = node.get("children", [])
            if children and _search(children):
                path.append(node)
                return True
        return False

    _search(nodes_list)
    path.reverse()
    return path


def _summarize_tree(nodes_list: list, indent: int = 0, _out: list | None = None) -> str:
    """将树形结构转换为缩进文本摘要（单列表累加，避免深层递归字符串拼接）"""
    if _out is None:
        _out = []
    for node in nodes_list:
        nid = node.get("id", "")
        text = node.get("text", "")
        gate = node.get("logic_gate", "")
        is_root = node.get("is_root_cause", False)
        gate_str = f" [{gate}]" if gate else ""
        root_str = " ★根因" if is_root else ""
        _out.append(f"{'  ' * indent}{nid}: {text}{gate_str}{root_str}")
        children = node.get("children", [])
        if isinstance(children, list) and children:
            _summarize_tree(children, indent + 1, _out)
    if indent == 0:
        return "\n".join(_out)
    return ""


def _format_interactions(interactions: list[dict]) -> str:
    """格式化交互关系为文本"""
    if not interactions:
        return "【组件交互】无"

    lines = ["【组件交互】"]
    for inter in interactions:
        tool = inter.get("tool", "")
        receiver = inter.get("receiver", "")
        itype = inter.get("type", inter.get("interaction_type", ""))
        verb = inter.get("verb", "")
        param = inter.get("parameter", "")
        change = inter.get("change", "")

        type_label = {
            "harmful": "有害",
            "insufficient": "不足",
            "excessive": "过量",
            "useful": "有用",
        }.get(itype, itype)
        desc = f"  {tool} → {receiver}: {type_label}"
        if verb:
            desc += f", {verb}"
        if param:
            desc += f", {param}"
        if change:
            arrow = "↑" if change == "up" else "↓"
            desc += f" {arrow}"
        lines.append(desc)
    return "\n".join(lines)


def _format_problem_pool(problem_pool: list[dict]) -> str:
    """格式化问题池为文本"""
    if not problem_pool:
        return "【问题池】无"

    lines = ["【问题池】"]
    for entry in problem_pool:
        tool = entry.get("tool", "")
        receiver = entry.get("receiver", "")
        itype = entry.get("interaction_type", "")
        desc = entry.get("description", "")
        type_label = {
            "harmful": "有害",
            "insufficient": "不足",
            "excessive": "过量",
        }.get(itype, itype)
        lines.append(f"  - {tool}→{receiver} ({type_label}): {desc}")
    return "\n".join(lines)


def _ensure_tree_root(nodes: list, problem: str = "") -> list:
    """确保节点列表是单根树结构"""
    if len(nodes) <= 1:
        return nodes

    root = next((n for n in nodes if n.get("id") == "node_0"), None)
    if root:
        others = [n for n in nodes if n is not root]
        if others:
            existing = root.get("children", [])
            if not isinstance(existing, list):
                existing = []
            root["children"] = existing + others
        return [root]
    else:
        synthetic = {
            "id": "node_0",
            "text": problem or "系统问题",
            "type": "initial",
            "logic_gate": "OR",
            "children": list(nodes),
        }
        return [synthetic]


# ============================================================
# 根因分析器
# ============================================================


class RootCauseAnalyzer(AIAnalyzer):
    """因果链分析器 - 多Agent分层并行架构"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        """执行因果树分析（5阶段流水线）

        Stage 1: 问题总结 → node_0
        Stage 2: 方向分类 → node_1_x + AND/OR
        Stage 3: 交互→缺点（并行）→ node_2_x
        Stage 4+5: 深挖+结束判断（迭代并行）→ node_3_x+
        """
        func_ctx = kwargs.get("function_model_context", "")
        pool_ctx = kwargs.get("problem_pool_context", "")
        goal_ctx = kwargs.get("goal_context", "")

        # 构建上下文
        context_parts = []
        if func_ctx:
            context_parts.append(func_ctx)
        if pool_ctx:
            context_parts.append(pool_ctx)
        if goal_ctx:
            context_parts.append(goal_ctx)
        context_str = "\n\n".join(context_parts)
        if context_str:
            context_str = f"\n\n【背景信息】\n{context_str}"

        # === Stage 1: 问题总结 ===
        logger.info("因果链分析 Stage 1: 问题总结...")
        node_0 = await self._stage1_summarize(problem, context_str)
        if not node_0:
            logger.warning("Stage 1 失败")
            return None

        tree = {
            "initial_defect": node_0.get("initial_defect", problem),
            "nodes": [
                {
                    "id": "node_0",
                    "text": node_0.get("node_0_text", problem),
                    "type": "initial",
                    "logic_gate": None,
                    "children": [],
                }
            ],
        }
        logger.info(f"Stage 1 完成: node_0 = {node_0.get('node_0_text', '')[:50]}...")

        # === Stage 2: 方向分类 ===
        logger.info("因果链分析 Stage 2: 方向分类...")
        stage2_result = await self._stage2_classify(tree["nodes"][0], context_str)
        if not stage2_result:
            logger.warning("Stage 2 失败，使用默认单链")
            stage2_result = {
                "directions": [
                    {
                        "id": "node_1_1",
                        "text": "系统存在的问题",
                        "category": "design_flaw",
                        "relevant_interactions": [],
                    }
                ],
                "logic_gate": "OR",
            }

        directions = stage2_result.get("directions", [])

        # 创建node_1节点（logic_gate暂不设置，由专门的AND/OR Agent判断）
        node_1_list = []
        for d in directions:
            node_1_list.append(
                {
                    "id": d.get("id", "node_1_1"),
                    "text": d.get("text", ""),
                    "type": "disadvantage",
                    "logic_gate": None,
                    "children": [],
                    "category": d.get("category", ""),
                    "relevant_interactions": d.get("relevant_interactions", []),
                }
            )
        tree["nodes"][0]["children"] = node_1_list

        # === AND/OR逻辑判断（单Agent） ===
        logger.info("Stage 2: 进行AND/OR逻辑判断...")
        await self._judge_logic_gates(tree, ["node_0"], context_str)
        logic_gate = tree["nodes"][0].get("logic_gate", "OR")
        logger.info(f"Stage 2 完成: {len(directions)} 个方向, gate={logic_gate}")

        # === Stage 3: 交互→缺点（并行） ===
        logger.info("因果链分析 Stage 3: 交互→缺点转换...")
        await self._stage3_translate(tree, directions, context_str)
        logger.info(f"Stage 3 完成: {_count_nodes(tree['nodes'])} 节点")

        # === Stage 4+5: 深挖+结束判断（迭代） ===
        logger.info("因果链分析 Stage 4+5: 深挖+结束判断...")
        await self._stage4_and_5_deepen(tree, context_str)
        logger.info(f"Stage 4+5 完成: {_count_nodes(tree['nodes'])} 节点")

        # === 最终处理 ===
        final_nodes = _sanitize_nodes(tree["nodes"])
        root_cause_details = []

        def collect_roots(nodes_list: list):
            for node in nodes_list:
                if node.get("is_root_cause") or node.get("type") == "root":
                    root_cause_details.append(
                        {
                            "id": node.get("id", ""),
                            "text": node.get("text", ""),
                        }
                    )
                children = node.get("children", [])
                if isinstance(children, list):
                    collect_roots(children)

        collect_roots(final_nodes)

        # 如果没有标记根因，将最深层的叶节点标记为根因
        if not root_cause_details:
            deepest = _collect_leaves(final_nodes, MAX_DEPTH)
            if not deepest:
                # 找所有无子节点的叶节点
                def find_all_leaves(nodes_list):
                    result = []
                    for node in nodes_list:
                        children = node.get("children", [])
                        if isinstance(children, list) and children:
                            result.extend(find_all_leaves(children))
                        else:
                            result.append(node)
                    return result

                deepest = find_all_leaves(final_nodes)
            for d in deepest:
                if d.get("id") and d.get("text"):
                    d["is_root_cause"] = True
                    d["type"] = "root"
                    root_cause_details.append(
                        {
                            "id": d.get("id", ""),
                            "text": d.get("text", ""),
                        }
                    )

        logger.info(
            f"因果链分析完成: {_count_nodes(final_nodes)} 节点, {len(root_cause_details)} 根因"
        )
        return {
            "initial_defect": tree.get("initial_defect", problem),
            "nodes": final_nodes,
            "root_causes": [r["id"] for r in root_cause_details],
            "root_cause_details": root_cause_details,
            "key_insights": [],
            "analysis_summary": f"通过5阶段多Agent分析，构建了{_count_nodes(final_nodes)}个节点的因果树，识别出{len(root_cause_details)}个根因。",
        }

    # ============================================================
    # Stage 1: 问题总结
    # ============================================================

    async def _stage1_summarize(self, problem: str, context_str: str) -> dict | None:
        """单Agent：问题→初始缺点"""
        MAX_RETRIES = 3
        validation_error = ""

        for attempt in range(MAX_RETRIES):
            user_msg = CAUSAL_STAGE1_USER.format(problem=problem, context=context_str)
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_STAGE1_SYSTEM,
                user_msg,
                temperature=0.2,
                json_mode=True,
                logger_prefix=f"因果链-Stage1-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"Stage 1 尝试{attempt + 1}: {validation_error}")
                continue

            # 验证
            node_0_text = result.get("node_0_text", "")
            if not node_0_text or len(node_0_text) < 5:
                validation_error = f"node_0_text 过短或为空: '{node_0_text}'"
                logger.warning(f"Stage 1 尝试{attempt + 1}: {validation_error}")
                continue

            return result

        logger.warning(f"Stage 1 {MAX_RETRIES}次尝试均失败")
        return None

    # ============================================================
    # Stage 2: 方向分类
    # ============================================================

    async def _stage2_classify(self, node_0: dict, context_str: str) -> dict | None:
        """单Agent：初始缺点→方向分类"""
        MAX_RETRIES = 3
        validation_error = ""

        for attempt in range(MAX_RETRIES):
            # 从上下文中提取交互关系
            interaction_data = ""
            problem_pool_data = ""

            # 尝试从context_str中解析交互关系
            if "【组件交互】" in context_str:
                start = context_str.find("【组件交互】")
                end = (
                    context_str.find("【", start + 1)
                    if context_str.find("【", start + 1) != -1
                    else len(context_str)
                )
                interaction_data = context_str[start:end].strip()

            if "【问题池】" in context_str:
                start = context_str.find("【问题池】")
                end = (
                    context_str.find("【", start + 1)
                    if context_str.find("【", start + 1) != -1
                    else len(context_str)
                )
                problem_pool_data = context_str[start:end].strip()

            user_msg = CAUSAL_STAGE2_USER.format(
                node_0_text=node_0.get("text", ""),
                interaction_data=interaction_data or "【组件交互】无可用数据",
                problem_pool_data=problem_pool_data or "【问题池】无可用数据",
            )
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_STAGE2_SYSTEM,
                user_msg,
                temperature=0.3,
                json_mode=True,
                logger_prefix=f"因果链-Stage2-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"Stage 2 尝试{attempt + 1}: {validation_error}")
                continue

            directions = result.get("directions", [])
            if not directions or len(directions) == 0:
                validation_error = "directions 为空"
                logger.warning(f"Stage 2 尝试{attempt + 1}: {validation_error}")
                continue

            # 强制标准化每个direction的id和text（忽略AI返回的id）
            for i, d in enumerate(directions):
                d["id"] = f"node_1_{i + 1}"
                if "text" not in d:
                    d["text"] = f"方向{i + 1}"

            return result

        logger.warning(f"Stage 2 {MAX_RETRIES}次尝试均失败")
        return None

    # ============================================================
    # Stage 3: 交互→缺点转换（并行）
    # ============================================================

    async def _stage3_translate(
        self, tree: dict, directions: list[dict], context_str: str
    ) -> None:
        """多Agent并行：方向→具体缺点 + AND/OR逻辑判断"""
        if not directions:
            return

        # === 步骤1: 并行转换交互→缺点 ===
        tasks = []
        for direction in directions:
            task = asyncio.wait_for(
                self._translate_one_direction(direction, context_str), timeout=120.0
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果到树中
        translated_ids = []
        for direction, result in zip(directions, results, strict=True):
            direction_id = direction.get("id", "")
            if isinstance(result, Exception):
                logger.error(f"Stage 3 Agent 失败 ({direction_id}): {result}")
                continue
            if not isinstance(result, dict):
                continue

            defects = result.get("defects", [])
            if not defects:
                continue

            # 找到对应的node_1节点并添加子节点
            self._add_children_to_node(tree["nodes"], direction_id, defects)
            translated_ids.append(direction_id)

        # === 步骤2: AND/OR逻辑判断（单Agent） ===
        if translated_ids:
            logger.info("Stage 3: 进行AND/OR逻辑判断...")
            await self._judge_logic_gates(tree, translated_ids, context_str)

    async def _translate_one_direction(
        self, direction: dict, context_str: str
    ) -> dict | None:
        """单个方向的交互→缺点转换"""
        MAX_RETRIES = 3
        validation_error = ""

        # 从上下文中提取相关交互关系的详细信息
        relevant_ids = set(direction.get("relevant_interactions", []))
        interaction_details = self._extract_interaction_details(context_str, relevant_ids)
        problem_pool_details = self._extract_problem_pool_details(context_str, direction)

        for attempt in range(MAX_RETRIES):
            user_msg = CAUSAL_STAGE3_USER.format(
                direction_text=direction.get("text", ""),
                direction_category=direction.get("category", ""),
                interaction_details=interaction_details,
                problem_pool_details=problem_pool_details,
                parent_id=direction.get("id", ""),
            )
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_STAGE3_SYSTEM,
                user_msg + context_str,
                temperature=0.3,
                json_mode=True,
                logger_prefix=f"因果链-Stage3-{direction.get('id', '')}-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"Stage 3 尝试{attempt + 1}: {validation_error}")
                continue

            defects = result.get("defects", [])
            if not defects:
                validation_error = "defects 为空"
                logger.warning(f"Stage 3 尝试{attempt + 1}: {validation_error}")
                continue

            # 确保每个defect有id和text（强制使用方向ID作为前缀避免冲突）
            parent_id = direction.get("id", "node_1")
            for i, d in enumerate(defects):
                # 强制生成唯一ID，忽略AI返回的id
                d["id"] = f"{parent_id}_{i + 1}"
                if "text" not in d:
                    d["text"] = f"缺点{i + 1}"
                d["type"] = "disadvantage"

            return result

        return None

    def _add_children_to_node(
        self, nodes_list: list, parent_id: str, children: list[dict]
    ) -> bool:
        """递归查找父节点并添加子节点（防止重复添加）"""
        for node in nodes_list:
            if node.get("id") == parent_id:
                existing = node.get("children", [])
                if not isinstance(existing, list):
                    existing = []
                # 使用id和text双重检查防止重复
                existing_ids = {
                    n.get("id", "") for n in existing if isinstance(n, dict)
                }
                existing_texts = {
                    n.get("text", "") for n in existing if isinstance(n, dict)
                }
                for child in children:
                    if isinstance(child, dict):
                        child_id = child.get("id", "")
                        child_text = child.get("text", "")
                        # 如果id已存在，跳过（同一父节点下不允许重复）
                        if child_id and child_id in existing_ids:
                            continue
                        # 如果text已存在，跳过
                        if child_text and child_text in existing_texts:
                            continue
                        existing.append(child)
                node["children"] = existing
                return True
            ch = node.get("children", [])
            if isinstance(ch, list) and self._add_children_to_node(
                ch, parent_id, children
            ):
                return True
        return False

    def _extract_interaction_details(
        self, context_str: str, relevant_ids: set[str]
    ) -> str:
        """从上下文中提取相关交互关系的详细信息"""
        if not relevant_ids:
            return "无相关交互关系ID"

        # 尝试从上下文中解析交互关系
        lines = context_str.split("\n")
        interaction_lines = []
        in_interaction_section = False

        for line in lines:
            if "【组件交互】" in line:
                in_interaction_section = True
                continue
            if in_interaction_section:
                if line.startswith("【") or line.strip() == "":
                    if interaction_lines:
                        break
                    continue
                # 检查是否匹配相关ID（格式：tool_id-receiver_id）
                for rid in relevant_ids:
                    if rid in line:
                        interaction_lines.append(line.strip())
                        break

        if interaction_lines:
            return "相关交互关系：\n" + "\n".join(interaction_lines)
        return f"相关交互关系ID: {list(relevant_ids)}（详情请参考背景信息中的组件交互部分）"

    def _extract_problem_pool_details(
        self, context_str: str, direction: dict
    ) -> str:
        """从上下文中提取相关问题池信息"""
        category = direction.get("category", "")
        text = direction.get("text", "")

        # 尝试从上下文中解析问题池
        lines = context_str.split("\n")
        pool_lines = []
        in_pool_section = False

        for line in lines:
            if "【问题池】" in line:
                in_pool_section = True
                continue
            if in_pool_section:
                if line.startswith("【") or line.strip() == "":
                    if pool_lines:
                        break
                    continue
                # 简单匹配：如果方向文本或类别与问题池条目相关
                if any(keyword in line for keyword in [text[:10], category]):
                    pool_lines.append(line.strip())

        if pool_lines:
            return "相关问题池信息：\n" + "\n".join(pool_lines)
        return "参见背景信息中的问题池部分"

    # ============================================================
    # Stage 4+5: 深挖+结束判断（迭代）
    # ============================================================

    async def _stage4_and_5_deepen(self, tree: dict, context_str: str) -> None:
        """层级4+: 结束判断 → 并行深挖 → AND/OR逻辑判断（迭代）

        流程：
        1. 先用单Agent判断当前叶节点是否到达结束条件
        2. 对未结束的节点，多Agent并行深挖子缺点
        3. 单Agent进行AND/OR逻辑判断
        4. 如果所有节点都到达结束条件，停止
        """
        for depth in range(3, MAX_DEPTH + 1):
            # 收集当前深度的叶节点
            leaves = _collect_leaves(tree["nodes"], depth - 1)
            if not leaves:
                logger.info(f"Level {depth}: 无可扩展的叶节点，停止")
                break

            # === 步骤1: 结束条件判断（单Agent） ===
            logger.info(
                f"Level {depth}: 判断 {len(leaves)} 个叶节点是否到达结束条件..."
            )
            judgments = await self._judge_termination(leaves, tree, context_str)

            # 标记根因，筛选需要继续分析的节点
            nodes_to_deepen = []
            for j in judgments:
                node_id = j.get("node_id", "")
                if j.get("is_root_cause", False):
                    self._mark_as_root_cause(tree["nodes"], node_id)
                    logger.info(
                        f"  {node_id} 已标记为根因: {j.get('reasoning', '')[:50]}"
                    )
                else:
                    # 找到对应的叶节点
                    leaf_node = next(
                        (ln for ln in leaves if ln.get("id") == node_id), None
                    )
                    if leaf_node:
                        nodes_to_deepen.append(leaf_node)

            # 如果所有节点都到达结束条件，停止
            if not nodes_to_deepen:
                logger.info(f"Level {depth}: 所有叶节点已到达根因，停止")
                break

            logger.info(f"Level {depth}: {len(nodes_to_deepen)} 个节点需要继续深挖")

            # === 步骤2: 分批并行深挖 ===
            deepened_ids = []
            for batch_start in range(0, len(nodes_to_deepen), MAX_PARALLEL_AGENTS):
                batch = nodes_to_deepen[batch_start:batch_start + MAX_PARALLEL_AGENTS]
                batch_num = batch_start // MAX_PARALLEL_AGENTS + 1
                total_batches = (len(nodes_to_deepen) + MAX_PARALLEL_AGENTS - 1) // MAX_PARALLEL_AGENTS
                logger.info(f"  批次 {batch_num}/{total_batches}: 处理 {len(batch)} 个节点")

                tasks = []
                for leaf in batch:
                    chain_path = _get_chain_path(tree["nodes"], leaf.get("id", ""))
                    task = asyncio.wait_for(
                        self._deepen_one_leaf(leaf, chain_path, depth, context_str),
                        timeout=120.0,
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 合并本批次结果
                for leaf, result in zip(batch, results, strict=True):
                    leaf_id = leaf.get("id", "")
                    if isinstance(result, Exception):
                        logger.error(f"Level {depth} Agent 失败 ({leaf_id}): {result}")
                        continue
                    if not isinstance(result, dict):
                        continue

                    children = result.get("children", [])
                    if not children:
                        continue

                    # 强制生成唯一ID，忽略AI返回的id（使用父节点ID作为前缀）
                    for i, child in enumerate(children):
                        child["id"] = f"{leaf_id}_{i + 1}"
                        child["type"] = "cause"

                    # 添加到树中
                    self._add_children_to_node(tree["nodes"], leaf_id, children)
                    deepened_ids.append(leaf_id)

            if not deepened_ids:
                logger.info(f"Level {depth}: 无有效深挖结果，停止")
                break

            # === 步骤3: AND/OR逻辑判断（单Agent） ===
            logger.info(f"Level {depth}: 进行AND/OR逻辑判断...")
            await self._judge_logic_gates(tree, deepened_ids, context_str)

            logger.info(f"Level {depth} 完成: {_count_nodes(tree['nodes'])} 节点")

    async def _deepen_one_leaf(
        self, leaf: dict, chain_path: list[dict], depth: int, context_str: str
    ) -> dict | None:
        """单个叶节点的深挖"""
        MAX_RETRIES = 3
        validation_error = ""

        # 构建链条文本
        chain_text = "\n".join(
            [f"  {node.get('id', '')}: {node.get('text', '')}" for node in chain_path]
        )

        for attempt in range(MAX_RETRIES):
            user_msg = CAUSAL_STAGE4_USER.format(
                leaf_text=leaf.get("text", ""),
                current_depth=depth,
                chain_path=chain_text,
                parent_id=leaf.get("id", ""),
                next_depth=depth + 1,
            )
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_STAGE4_SYSTEM,
                user_msg + context_str,
                temperature=0.3,
                json_mode=True,
                logger_prefix=f"因果链-Stage4-{leaf.get('id', '')}-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"Stage 4 尝试{attempt + 1}: {validation_error}")
                continue

            children = result.get("children", [])
            if not children:
                # 无子节点可能是AI认为已到达终点
                validation_error = "children 为空（可能已到达终点）"
                logger.info(f"Stage 4 尝试{attempt + 1}: {validation_error}")
                return {"children": [], "logic_gate": "OR"}

            return result

        return None

    def _set_node_gate(self, nodes_list: list, node_id: str, gate: str) -> bool:
        """设置节点的logic_gate"""
        for node in nodes_list:
            if node.get("id") == node_id:
                node["logic_gate"] = gate
                return True
            ch = node.get("children", [])
            if isinstance(ch, list) and self._set_node_gate(ch, node_id, gate):
                return True
        return False

    def _mark_as_root_cause(self, nodes_list: list, node_id: str) -> bool:
        """标记节点为根因"""
        for node in nodes_list:
            if node.get("id") == node_id:
                node["is_root_cause"] = True
                node["type"] = "root"
                return True
            ch = node.get("children", [])
            if isinstance(ch, list) and self._mark_as_root_cause(ch, node_id):
                return True
        return False

    # ============================================================
    # Stage 5: 结束判断
    # ============================================================

    async def _judge_termination(
        self, leaves: list[dict], tree: dict, context_str: str
    ) -> list[dict]:
        """分批并行：判断叶节点是否到达根因"""
        if not leaves:
            return []

        # 构建树摘要（共享）
        tree_summary = _summarize_tree(tree["nodes"])

        # 分批处理
        all_evaluations = []
        for batch_start in range(0, len(leaves), MAX_PARALLEL_AGENTS):
            batch = leaves[batch_start:batch_start + MAX_PARALLEL_AGENTS]
            batch_num = batch_start // MAX_PARALLEL_AGENTS + 1
            total_batches = (len(leaves) + MAX_PARALLEL_AGENTS - 1) // MAX_PARALLEL_AGENTS
            logger.info(f"  结束判断批次 {batch_num}/{total_batches}: 处理 {len(batch)} 个节点")

            batch_result = await self._judge_termination_batch(
                batch, tree, tree_summary, context_str
            )
            all_evaluations.extend(batch_result)

        return all_evaluations

    async def _judge_termination_batch(
        self, leaves: list[dict], tree: dict, tree_summary: str, context_str: str
    ) -> list[dict]:
        """单批次：判断叶节点是否到达根因"""
        MAX_RETRIES = 3
        validation_error = ""

        # 统计信息
        total_nodes = _count_nodes(tree["nodes"])
        root_count = _count_root_causes(tree["nodes"])

        # 构建叶节点文本（含完整因果链路径）
        node_lines = []
        for leaf in leaves:
            chain = _get_chain_path(tree["nodes"], leaf.get("id", ""))
            chain_text = " → ".join(
                f"{n.get('id', '')}:{n.get('text', '')}" for n in chain
            )
            node_lines.append(
                f"  {leaf.get('id', '')}: {leaf.get('text', '')}\n"
                f"    因果链路径: {chain_text}"
            )
        nodes_text = "\n".join(node_lines)

        for attempt in range(MAX_RETRIES):
            current_depth = self._calc_node_depth(tree["nodes"], leaves[0].get("id", "")) if leaves else 0
            if current_depth < 0:
                current_depth = 0
            user_msg = CAUSAL_JUDGE_USER.format(
                current_depth=current_depth,
                total_nodes=total_nodes,
                root_count=root_count,
                leaf_count=len(leaves),
                nodes_to_evaluate=nodes_text,
                tree_summary=tree_summary,
            )
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_JUDGE_SYSTEM,
                user_msg,
                temperature=0.2,
                json_mode=True,
                logger_prefix=f"因果链-Stage5-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"Stage 5 尝试{attempt + 1}: {validation_error}")
                continue

            evaluations = result.get("evaluations", [])
            if not evaluations:
                validation_error = "evaluations 为空"
                logger.warning(f"Stage 5 尝试{attempt + 1}: {validation_error}")
                continue

            # 确保每个evaluation有node_id
            for i, e in enumerate(evaluations):
                if "node_id" not in e and i < len(leaves):
                    e["node_id"] = leaves[i].get("id", "")

            return evaluations

        # 失败时返回默认值（不标记为根因）
        return [
            {"node_id": leaf.get("id", ""), "is_root_cause": False} for leaf in leaves
        ]

    # ============================================================
    # AND/OR 逻辑判断
    # ============================================================

    async def _judge_logic_gates(
        self, tree: dict, parent_ids: list[str], context_str: str
    ) -> None:
        """单Agent：判断父节点与子节点之间的AND/OR逻辑关系"""
        if not parent_ids:
            return

        MAX_RETRIES = 3
        validation_error = ""

        # 收集需要判断的节点信息
        nodes_to_judge = []
        for pid in parent_ids:
            node = self._find_node_by_id(tree["nodes"], pid)
            if node and node.get("children"):
                nodes_to_judge.append(node)

        if not nodes_to_judge:
            return

        # 构建节点文本
        nodes_text = "\n".join(
            [
                f"  {node.get('id', '')}: {node.get('text', '')}\n"
                f"    子节点: {[c.get('text', '') for c in node.get('children', [])]}"
                for node in nodes_to_judge
            ]
        )

        # 构建树摘要
        tree_summary = _summarize_tree(tree["nodes"])

        for attempt in range(MAX_RETRIES):
            user_msg = CAUSAL_ANDOR_USER.format(
                nodes_text=nodes_text,
                tree_summary=tree_summary,
            )
            if attempt > 0:
                user_msg += f"\n\n【格式错误】上次输出不符合要求：{validation_error}\n请严格按照JSON格式输出。"

            result = await self.ai.call_ai_async(
                CAUSAL_ANDOR_SYSTEM,
                user_msg,
                temperature=0.2,
                json_mode=True,
                logger_prefix=f"因果链-ANDOR判断-尝试{attempt + 1}",
            )

            if not isinstance(result, dict):
                validation_error = "输出不是JSON对象"
                logger.warning(f"AND/OR判断 尝试{attempt + 1}: {validation_error}")
                continue

            judgments = result.get("judgments", [])
            if not judgments:
                validation_error = "judgments 为空"
                logger.warning(f"AND/OR判断 尝试{attempt + 1}: {validation_error}")
                continue

            # 应用逻辑判断
            for j in judgments:
                pid = j.get("parent_id", "")
                gate = j.get("logic_gate", "OR")
                if pid and gate in ("AND", "OR"):
                    self._set_node_gate(tree["nodes"], pid, gate)

            logger.info(f"AND/OR判断完成: {len(judgments)} 个节点")
            return

        logger.warning(f"AND/OR判断 {MAX_RETRIES}次尝试均失败，使用默认OR")

    def _find_node_by_id(self, nodes_list: list, node_id: str) -> dict | None:
        """按ID查找节点"""
        for node in nodes_list:
            if node.get("id") == node_id:
                return node
            children = node.get("children", [])
            if isinstance(children, list):
                found = self._find_node_by_id(children, node_id)
                if found:
                    return found
        return None

    def _calc_node_depth(self, nodes_list: list, target_id: str, current_depth: int = 0) -> int:
        """计算目标节点在树中的实际深度"""
        for node in nodes_list:
            if node.get("id") == target_id:
                return current_depth
            children = node.get("children", [])
            if isinstance(children, list) and children:
                depth = self._calc_node_depth(children, target_id, current_depth + 1)
                if depth >= 0:
                    return depth
        return -1

    # ============================================================
    # 向后兼容：deepen_node 方法
    # ============================================================

    async def deepen_node(
        self,
        problem: str,
        tree: dict,
        target_node_id: str,
        context_str: str = "",
    ) -> dict | None:
        """对指定节点深挖下一层原因（向后兼容）"""

        # 找到目标节点
        def find_node(nodes: list) -> dict | None:
            for node in nodes:
                if node.get("id") == target_node_id:
                    return node
                children = node.get("children", [])
                if isinstance(children, list) and children:
                    found = find_node(children)
                    if found:
                        return found
            return None

        target = find_node(tree.get("nodes", []))
        if not target:
            logger.warning(f"未找到目标节点: {target_node_id}")
            return None

        target_text = target.get("text", "")
        # 计算目标节点的实际深度（从根节点递归计算）
        current_depth = self._calc_node_depth(tree.get("nodes", []), target_node_id)

        # 找到父节点
        parent = _find_parent(tree.get("nodes", []), target_node_id)
        parent_text = parent.get("text", "") if parent else ""

        # 构建链条
        chain_path = _get_chain_path(tree.get("nodes", []), target_node_id)
        chain_text = "\n".join(
            [f"  {node.get('id', '')}: {node.get('text', '')}" for node in chain_path]
        )

        # 构造提示词（使用旧版prompt保持兼容）
        ctx = f"\n\n{context_str}" if context_str else ""
        parent_ctx = f'\n（这是对"{parent_text}"的回答）' if parent_text else ""
        extend_prompt = f"""问题：{problem}{ctx}

【已有因果链】
{chain_text}

请为以下节点追问"为什么"，生成子节点：

- {target_node_id}: {target_text}{parent_ctx}

【分析深度指引】
当前节点位于层级{current_depth}，请按以下粒度深入：
- 层级1：系统级原因，识别独立的失效模式方向
- 层级2：组件级原因，指向具体组件或交互
- 层级3：机理级原因，涉及物理/化学/几何过程
- 层级4：参数级根因，到达可量化参数（温度、压力、导热系数等）
- 层级5+：如仍未到达自然现象，继续追问直到到达

【因果关系验证】
反事实检验：如果移除该原因，上级问题是否还会发生？

【AND/OR 分支规则】
- AND：多个原因必须同时存在才导致上级问题
- OR：任意一个原因就足以导致上级问题

【结束条件 — 满足任一则标记为 type="root"】
1. 已达到自然现象层
2. 已达到制度/法规/成本极限
3. 已超出项目范围

输出JSON格式，只输出新增节点：
{{"nodes": [
  {{"id": "{target_node_id}", "children": [
    {{"text": "原因描述", "type": "cause", "logic_gate": "AND/OR/null"}}
  ]}}
]}}"""

        # 带验证重试
        deep_validation_error = ""
        result = None
        for attempt in range(3):
            deep_user_msg = extend_prompt
            if attempt > 0:
                deep_user_msg += f"\n\n【格式错误】上次输出不符合要求：{deep_validation_error}\n请严格按照JSON格式输出。"
            result = await self.ai.call_ai_async(
                ZHISHU_CAUSAL_CHAIN_SYSTEM_PROMPT,
                deep_user_msg,
                temperature=0.3,
                json_mode=True,
                logger_prefix=f"因果链-深挖-{target_node_id}-尝试{attempt + 1}",
            )
            if not isinstance(result, dict):
                deep_validation_error = "输出不是JSON对象"
                continue
            # 简单验证
            nodes = result.get("nodes", [])
            if not isinstance(nodes, list) or not nodes:
                deep_validation_error = "nodes 为空"
                continue
            break
        else:
            logger.warning(f"深挖 {target_node_id} {3}次尝试均失败")
            return None

        if not isinstance(result, dict):
            return None

        # 合并新节点到树（兼容多种返回格式）
        new_nodes = result.get("nodes", [])
        # 格式2：直接返回 children（无外层 nodes）
        if not new_nodes and "children" in result and "id" in result:
            new_nodes = [result]
        # 格式3：返回单个节点对象（无 children 包装）
        if not new_nodes and "children" in result:
            new_nodes = [{"id": target_node_id, "children": result["children"]}]

        if new_nodes:
            parent_children: dict[str, list] = {}
            for item in new_nodes:
                pid = item.get("id", "")
                children = item.get("children", [])
                if pid and isinstance(children, list) and children:
                    parent_children[pid] = children

            def merge_children(nodes_list: list) -> bool:
                modified = False
                for node in nodes_list:
                    nid = node.get("id", "")
                    if nid in parent_children:
                        existing = node.get("children", [])
                        if not isinstance(existing, list):
                            existing = []
                        new_children = parent_children[nid]
                        # 使用id和text双重检查防止重复
                        existing_ids = {
                            n.get("id", "") for n in existing if isinstance(n, dict)
                        }
                        existing_texts = {
                            n.get("text", "") for n in existing if isinstance(n, dict)
                        }
                        for nc in new_children:
                            if isinstance(nc, dict):
                                nc_id = nc.get("id", "")
                                nc_text = nc.get("text", "")
                                if nc_id and nc_id in existing_ids:
                                    continue
                                if nc_text and nc_text in existing_texts:
                                    continue
                                existing.append(nc)
                        node["children"] = existing
                        modified = True
                    ch = node.get("children", [])
                    if isinstance(ch, list) and merge_children(ch):
                        modified = True
                return modified

            merge_children(tree.get("nodes", []))
            logger.info(
                f"深挖 {target_node_id} 完成: 新增 {len(new_nodes)} 个父节点的子节点"
            )

        # AND/OR 逻辑判断（与主流程 _stage4_and_5_deepen 保持一致）
        if context_str:
            await self._judge_logic_gates(tree, [target_node_id], context_str)

        return tree
