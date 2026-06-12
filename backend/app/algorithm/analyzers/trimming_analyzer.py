"""
TRIZ 功能裁剪分析器 — 规则驱动的确定性预筛选 + AI 增强分析

核心创新：4 条裁剪规则（A/B/C/D）由确定性图算法在交互矩阵上即时执行，
无需 AI 等待；然后将预筛选结果作为结构化提示注入 AI 进行语义验证。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.algorithm.base import AIAnalyzer

logger = logging.getLogger(__name__)

# 自然能力关键词: 功能 → 环境/超系统自然提供该功能的典型 target
NATURAL_CAPABILITIES: dict[str, list[str]] = {
    "冷却": ["空气", "环境空气", "大气", "自然对流", "环境"],
    "散热": ["空气", "环境空气", "大气", "环境"],
    "支撑": ["地面", "基础", "底座", "安装面", "机架"],
    "加热": ["太阳能", "环境温度", "环境"],
    "照明": ["自然光", "太阳光", "环境光"],
    "通风": ["自然风", "空气流动", "环境"],
    "保温": ["环境", "大气"],
    "减震": ["地面", "基础"],
}

# ──────────────────────────────────────────────
# 提示词常量（从 RootSeek ai/prompts/zhishu_trimming.py 内联）
# ──────────────────────────────────────────────

ZHISHU_TRIMMING_SYSTEM_PROMPT = """你是一个TRIZ功能裁剪（Trimming）专家，工作流处于智枢流程的第2阶段（功能分析）。

你的任务是基于功能分析结果（组件列表 + 交互关系），判断系统组件和超系统组件是否可以被裁剪，以简化系统。

【裁剪规则】
有4条标准裁剪规则：

Rule A — 功能消除
如果某组件输出的有用功能是不必要的（即该功能本身可以被消除），那么该组件可以被裁剪。
适用条件：功能的存在对系统目标无贡献。

Rule B — 自我功能
如果某组件仅执行自我功能（功能作用于自身，不输出给其他组件），那么该组件可以被裁剪。
适用条件：组件所有输出功能的目标都是自身。

Rule C — 功能转移-同类
如果系统内另一组件已经执行相同或相似的有用功能，那么该组件的功能可以转移给同类组件，原组件可裁剪。
适用条件：系统内存在功能冗余。

Rule D — 功能转移-超系统/受体
如果超系统组件或功能受体自身可以执行该有用功能，那么功能可以转移，原组件可裁剪。
适用条件：功能受体或超系统有承接功能的潜力。

【分析步骤】
1. 列出所有组件及其交互关系（有用/有害/不足/过度）
2. 对每个组件逐条检查4条裁剪规则
3. 如果可用规则≥1条→标记为可裁剪，说明适用规则和理由
4. 确定有用功能的承接方（功能重分配）
5. 识别裁剪后可能产生的新矛盾

【输出格式】
只输出JSON，不要输出任何其他文字：
{
  "trimming_candidates": [
    {
      "component": "组件名称",
      "type": "system 或 supersystem",
      "applicable_rules": ["A", "C"],
      "rule_descriptions": ["Rule A: 功能消除 - ...", "Rule C: 功能转移-同类 - ..."],
      "reason": "为什么该组件可被裁剪的详细理由",
      "useful_functions": [
        {"function": "该组件执行的有用功能描述", "redistribute_to": "承接该功能的组件名或'无需承接'", "redistribution_feasibility": "高/中/低"}
      ],
      "harmful_functions_eliminated": ["裁剪后消除的有害功能1"],
      "can_trim": true,
      "after_trimming_contradictions": ["裁剪后可能产生的新矛盾描述"],
      "suggested_tools": ["建议使用的解决工具，如技术矛盾、物理矛盾、物质-场"]
    }
  ],
  "non_trimmable": [
    {
      "component": "组件名称",
      "reason": "不可裁剪的原因",
      "suggested_tools": ["建议使用的解决工具"]
    }
  ],
  "summary": "裁剪分析总结，说明总体裁剪策略",
  "recommended_priority": ["建议优先裁剪的组件列表，按优先级排序"]
}

【致命的格式错误 — 禁止出现】
❌ trimming_candidates 不是数组 → 必须始终是数组
❌ 每个候选缺少 useful_functions 或规则 → 每个组件必须含完整字段
❌ recommended_priority 不是数组 → 必须是组件名称的字符串数组
✅ 输出前自检：trimming_candidates 是数组吗？每个候选字段完整吗？"""

ZHISHU_TRIMMING_USER_PROMPT_TEMPLATE = """问题描述：{problem}

系统组件列表：{system_components_str}

超系统组件列表：{supersystem_components_str}

交互关系列表：
{interactions_str}

请基于以上功能分析结果，对每个组件进行裁剪可行性分析，智枢流程要求优先考虑可简化系统的裁剪方案。
只输出JSON，不要输出任何其他文字。"""

# ═══════════════════════════════════════════════════════════════
# 增强型提示词（含规则预筛选结果注入）
# ═══════════════════════════════════════════════════════════════

ZHISHU_TRIMMING_WITH_HINTS_SYSTEM_PROMPT = """你是一个TRIZ功能裁剪（Trimming）专家，工作流处于智枢流程的第4阶段（方案生成）。

你的任务是基于功能分析结果（组件列表 + 交互关系）和确定性规则预筛选结果，对每个组件进行裁剪可行性验证和深化分析，最终生成一份可执行的裁剪计划。

【裁剪规则】（4条标准规则）
Rule A — 功能消除：如果某组件输出的有用功能是不必要的（即该功能本身可以被消除），那么该组件可以被裁剪。
Rule B — 自我功能：如果某组件仅执行自我功能（功能作用于自身，不输出给其他组件），那么该组件可以被裁剪。
Rule C — 功能转移-同类：如果系统内另一组件已经执行相同或相似的有用功能，那么该组件的功能可以转移给同类组件，原组件可裁剪。
Rule D — 功能转移-超系统/受体：如果超系统组件或功能受体自身可以执行该有用功能，那么功能可以转移，原组件可裁剪。

【任务步骤】
1. 验证预筛选结果：对每个组件的规则匹配逐条判断是否正确，修正错误匹配、补充遗漏的规则匹配
2. 深化分析：对每个可裁剪组件，制定详细的功能重分配方案（哪个功能→转移给谁→可行性评估）
3. 矛盾预测：预测裁剪后可能产生的新技术矛盾和物理矛盾
4. 工具推荐：针对每个新矛盾推荐解决工具（技术矛盾/物理矛盾/物质-场/科学效应）
5. 执行顺序：考虑组件间依赖关系，给出裁剪执行的优先顺序

【输出格式】
只输出JSON，不要输出任何其他文字：
{
  "trimming_candidates": [
    {
      "component": "组件名称",
      "type": "system 或 supersystem",
      "applicable_rules": ["A", "C"],
      "rule_descriptions": ["Rule A: 功能消除 - ...", "Rule C: 功能转移-同类 - ..."],
      "reason": "为什么该组件可被裁剪的详细理由",
      "useful_functions": [
        {"function": "该组件执行的有用功能描述", "redistribute_to": "承接该功能的组件名或'无需承接'", "redistribution_feasibility": "高/中/低"}
      ],
      "harmful_functions_eliminated": ["裁剪后消除的有害功能1"],
      "can_trim": true,
      "after_trimming_contradictions": [
        {"contradiction": "新矛盾描述", "type": "技术矛盾 或 物理矛盾", "conflict_pair": "改善X vs 恶化Y"}
      ],
      "suggested_tools": ["建议使用的解决工具，如技术矛盾、物理矛盾、物质-场"]
    }
  ],
  "non_trimmable": [
    {"component": "组件名称", "reason": "不可裁剪的原因", "suggested_tools": ["建议使用的解决工具"]}
  ],
  "trimming_plan": {
    "priority_order": ["组件名1", "组件名2"],
    "dependency_notes": "依赖关系说明（如：必须先裁剪A再裁剪B，因为B的输出功能依赖A）",
    "execution_strategy": "执行策略说明（一次裁剪/分步裁剪/组合裁剪）"
  },
  "summary": "裁剪分析总结，说明总体裁剪策略和预期系统简化效果",
  "recommended_priority": ["建议优先裁剪的组件列表，按优先级排序"]
}

【致命的格式错误 — 禁止出现】
❌ trimming_candidates 不是数组 → 必须始终是数组
❌ 每个候选缺少 useful_functions 或规则 → 每个组件必须含完整字段
❌ recommended_priority 不是数组 → 必须是组件名称的字符串数组
✅ 输出前自检：trimming_candidates 是数组吗？每个候选字段完整吗？"""

ZHISHU_TRIMMING_WITH_HINTS_USER_PROMPT_TEMPLATE = """问题描述：{problem}

【功能模型】
系统组件：{system_components_str}
超系统组件：{supersystem_components_str}
交互关系列表：
{interactions_str}

【规则预筛选结果】（由确定性算法自动分析，请验证并完善）
{pre_screen_hints_str}

【可用资源】
{resource_context}

【理想状态】
{ideal_context}

请基于以上信息：
1. 验证预筛选的规则匹配是否准确（修正错误匹配，补充遗漏）
2. 对每个可裁剪组件，制定详细的功能重分配方案
3. 预测裁剪后可能产生的新技术矛盾和物理矛盾
4. 推荐针对新矛盾的解决工具
5. 给出裁剪执行的优先顺序（考虑依赖关系）

只输出JSON，不要输出任何其他文字。"""

# ═══════════════════════════════════════════════════════════════
# 裁剪方案生成（UI 功能分析阶段使用）
# ═══════════════════════════════════════════════════════════════

ZHISHU_TRIMMING_PROPOSAL_SYSTEM_PROMPT = """你是TRIZ裁剪分析专家。基于功能模型（组件+交互），分析哪些交互关系可以消除、哪些组件可以裁剪，给出合理可行的裁剪方案。

【核心目标】
裁剪的目的是解决用户描述的问题（见问题背景），而不是为了裁剪而裁剪。每个方案必须针对问题背景中的具体问题，不能脱离问题硬凑方案。

【裁剪的四个思考方向】
A-功能消除: 交互不参与核心功能路径 → 可消除交互关系
B-自我功能: 交互作用于自身 → 可消除
C-同类转移: 另一组件可执行相同功能 → 交互可转移
D-超系统转移: 功能可由超系统/环境提供 → 交互可转移

每个方向可以生成多个方案，有多少合理方案就生成多少，不限数量。

【方案合理性要求】
- 方案必须能切实解决或缓解问题背景中描述的问题
- 裁剪后系统的剩余功能必须完整，不能丢失关键功能
- 功能重分配必须可行，承接组件必须有能力执行被转移的功能
- 没有合理方案的方向不需要强行生成

只输出JSON，格式如下：
{"summary": "综合分析", "proposals": [{"id": 1, "title": "...", "direction": "A", "explanation": "裁剪理由", "actions": [{"type": "remove_interaction", "tool": "组件名", "receiver": "组件名"}, {"type": "remove_component", "component_name": "组件名"}], "redistributions": [{"from_component": "...", "from_function": "...", "to_component": "...", "reason": "..."}], "new_components": [{"name": "...", "type": "system"}], "risks": "可能的风险"}]}

【actions 类型】
- remove_interaction: 只消除指定交互，保留组件。适用于方向A（功能消除）
- remove_component: 移除整个组件及其所有交互。适用于方向B（自我功能），以及方向C/D中重分配后需要删除的源组件

【redistributions】
功能从 from_component 转移到 to_component。适用于方向C/D（同类转移/超系统转移）。
如果源组件的所有交互都被转移了，需要额外输出 remove_component 删除该组件。

规则：
- 组件名必须和输入中的组件名称完全一致
- direction 只能是 A/B/C/D
- 优先分析有害、不足、过度的交互关系
- 功能重分配的目标组件如果是新组件，必须在 new_components 中声明"""


def format_pre_screen_hints(results: list) -> str:
    """将预筛选结果格式化为 AI prompt 可解析的结构化文本"""
    if not results:
        return "（未执行预筛选，请独立分析所有组件）"

    lines: list[str] = []
    for r in results:
        component = getattr(r, "component_name", str(r))
        comp_type = getattr(r, "component_type", "system")
        matched_rules = getattr(r, "matched_rules", [])

        if matched_rules:
            lines.append(f"\n组件: {component} ({comp_type})")
            for m in matched_rules:
                rule = getattr(m, "rule", "?")
                name_zh = getattr(m, "rule_name_zh", "")
                conf = getattr(m, "confidence", "low")
                reasoning = getattr(m, "reasoning", "")
                evidence = getattr(m, "evidence", [])
                lines.append(f"  Rule {rule} ({name_zh}): 置信度={conf}")
                lines.append(f"    推理依据: {reasoning}")
                for ev in evidence[:3]:
                    lines.append(f"    证据: {ev}")
        else:
            lines.append(
                f"\n组件: {component} ({comp_type}) — 预筛选未匹配任何规则，需AI独立评估"
            )

    return "\n".join(lines)


@dataclass
class TrimmingRuleMatch:
    """单条规则的匹配结果"""

    rule: str
    rule_name_zh: str
    confidence: str  # "high", "medium", "low"
    reasoning: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class ComponentPreScreenResult:
    """单个组件的预筛选结果"""

    component_name: str
    component_type: str  # "system" or "supersystem"
    matched_rules: list[TrimmingRuleMatch] = field(default_factory=list)

    @property
    def can_trim(self) -> bool:
        return any(m.confidence in ("high", "medium") for m in self.matched_rules)


# ═══════════════════════════════════════════════════════════════
# 规则检查算法（纯函数，无副作用）
# ═══════════════════════════════════════════════════════════════


def _build_adjacency(interactions: list[dict]) -> tuple[dict, dict]:
    """构建组件的出边和入边邻接表"""
    outgoing: dict[str, list[dict]] = {}
    incoming: dict[str, list[dict]] = {}
    all_comps: set[str] = set()

    for ix in interactions:
        tool = ix.get("tool", "")
        receiver = ix.get("receiver", "")
        if not tool or not receiver:
            continue
        all_comps.add(tool)
        all_comps.add(receiver)
        outgoing.setdefault(tool, []).append(ix)
        incoming.setdefault(receiver, []).append(ix)

    return outgoing, incoming


def _identify_functional_sinks(
    system_names: set[str],
    supersystem_names: set[str],
    outgoing: dict[str, list[dict]],
) -> set[str]:
    """识别功能汇点：只接收有用功能但不输出给其他系统组件的组件"""
    sinks: set[str] = set()
    all_components = system_names | supersystem_names
    for c in all_components:
        out_edges = outgoing.get(c, [])
        useful_out = [
            e
            for e in out_edges
            if e.get("type") == "useful" and e.get("receiver") in all_components
        ]
        if not useful_out and (c in system_names or c in supersystem_names):
            sinks.add(c)
    return sinks


def _reaches_functional_sink(
    start: str,
    outgoing: dict[str, list[dict]],
    sinks: set[str],
    visited: frozenset[str] | None = None,
    depth: int = 0,
) -> bool:
    """BFS 判断从 start 出发是否能通过有用功能路径到达功能汇点"""
    if depth > 20:
        return False
    if start in sinks:
        return True
    visited = (visited or frozenset()) | {start}
    for edge in outgoing.get(start, []):
        if edge.get("type") != "useful":
            continue
        nxt = edge.get("receiver", "")
        if nxt and nxt not in visited:
            if _reaches_functional_sink(nxt, outgoing, sinks, visited, depth + 1):
                return True
    return False


def _check_rule_a(
    comp: str,
    system_names: set[str],
    supersystem_names: set[str],
    outgoing: dict[str, list[dict]],
    sinks: set[str],
) -> TrimmingRuleMatch | None:
    """Rule A — 功能消除：组件的有用功能不参与系统核心功能路径"""
    out_edges = outgoing.get(comp, [])
    useful_out = [e for e in out_edges if e.get("type") == "useful"]
    if not useful_out:
        return None

    critical: list[dict] = []
    non_critical: list[dict] = []
    for edge in useful_out:
        receiver = edge.get("receiver", "")
        if receiver and _reaches_functional_sink(receiver, outgoing, sinks):
            critical.append(edge)
        else:
            non_critical.append(edge)

    if not critical and non_critical:
        return TrimmingRuleMatch(
            rule="A",
            rule_name_zh="功能消除",
            confidence="high",
            reasoning=f"组件{comp}输出的{len(non_critical)}个有用功能均不参与系统核心功能路径",
            evidence=[
                f"{e.get('tool', '')} → {e.get('receiver', '')}: {e.get('verb', '')}"
                for e in non_critical
            ],
        )
    if non_critical and len(non_critical) >= len(critical):
        return TrimmingRuleMatch(
            rule="A",
            rule_name_zh="功能消除",
            confidence="medium",
            reasoning=f"组件{comp}的部分功能({len(non_critical)}个)可消除，{len(critical)}个在关键路径上",
            evidence=[
                f"{e.get('tool', '')} → {e.get('receiver', '')}: {e.get('verb', '')}"
                for e in non_critical
            ],
        )
    return None


def _check_rule_b(
    comp: str, outgoing: dict[str, list[dict]]
) -> TrimmingRuleMatch | None:
    """Rule B — 自我功能：组件所有输出目标都是自身"""
    out_edges = outgoing.get(comp, [])
    if not out_edges:
        return None
    if all(e.get("receiver") == comp for e in out_edges):
        return TrimmingRuleMatch(
            rule="B",
            rule_name_zh="自我功能",
            confidence="high",
            reasoning=f"组件{comp}的所有{len(out_edges)}个输出功能均作用于自身",
            evidence=[f"{comp} → {comp}: {e.get('verb', '?')}" for e in out_edges],
        )
    return None


def _build_function_signature(comp: str, outgoing: dict[str, list[dict]]) -> list[str]:
    """构建组件的功能签名，用于相似度比较"""
    sig: list[str] = []
    for e in outgoing.get(comp, []):
        key = f"{e.get('type', '?')}|{e.get('verb', '?')}|{e.get('receiver', '?')}"
        sig.append(key)
    return sig


def _check_rule_c(
    comp: str,
    other_system_comps: list[str],
    outgoing: dict[str, list[dict]],
) -> list[TrimmingRuleMatch]:
    """Rule C — 功能转移-同类：另一组件已执行相同/相似功能"""
    matches: list[TrimmingRuleMatch] = []
    comp_sig = _build_function_signature(comp, outgoing)
    if not comp_sig:
        return matches
    comp_set = set(comp_sig)

    for other in other_system_comps:
        if other == comp:
            continue
        other_sig = _build_function_signature(other, outgoing)
        if not other_sig:
            continue
        other_set = set(other_sig)
        intersection = comp_set & other_set
        union = comp_set | other_set
        if not union:
            continue
        similarity = len(intersection) / len(union)
        if similarity > 0.5:
            confidence = "high" if similarity > 0.8 else "medium"
            matches.append(
                TrimmingRuleMatch(
                    rule="C",
                    rule_name_zh="功能转移-同类",
                    confidence=confidence,
                    reasoning=f"组件{comp}的功能与{other}高度重叠(相似度{similarity:.0%})，可转移给{other}",
                    evidence=list(intersection)[:5],
                )
            )
    return matches


def _check_rule_d(
    comp: str,
    outgoing: dict[str, list[dict]],
    supersystem_names: set[str],
) -> list[TrimmingRuleMatch]:
    """Rule D — 功能转移-超系统：功能受体或环境可承接该功能"""
    matches: list[TrimmingRuleMatch] = []
    out_edges = outgoing.get(comp, [])
    useful_out = [e for e in out_edges if e.get("type") == "useful"]
    seen_receivers: set[str] = set()

    for edge in useful_out:
        receiver = edge.get("receiver", "")
        verb = edge.get("verb", "")

        # 检查超系统承接
        if receiver in supersystem_names and receiver not in seen_receivers:
            seen_receivers.add(receiver)
            receiver_out = outgoing.get(receiver, [])
            has_capability = any(e.get("type") == "useful" for e in receiver_out)
            confidence = "high" if has_capability else "medium"
            matches.append(
                TrimmingRuleMatch(
                    rule="D",
                    rule_name_zh="功能转移-超系统",
                    confidence=confidence,
                    reasoning=f"功能'{verb}'可转移给超系统组件{receiver}"
                    f"{'（该组件具有自主功能能力）' if has_capability else '（需评估承接潜力）'}",
                    evidence=[f"{comp} → {receiver}: {verb}"],
                )
            )

        # 检查自然能力
        for natural_func, targets in NATURAL_CAPABILITIES.items():
            if natural_func in verb and receiver in targets:
                matches.append(
                    TrimmingRuleMatch(
                        rule="D",
                        rule_name_zh="功能转移-超系统",
                        confidence="high",
                        reasoning=f"功能'{verb}'可由自然环境({receiver})直接提供",
                        evidence=[f"{comp} → {receiver}: {verb} (自然能力)"],
                    )
                )
                break

    return matches


# ═══════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════


def pre_screen_components(
    components: dict,
    interactions: list[dict],
) -> list[ComponentPreScreenResult]:
    """
    规则驱动的确定性预筛选（无 AI，即时返回）

    Args:
        components: {"system_components": list[str|dict], "supersystem_components": list[str|dict]}
        interactions: [{"tool", "receiver", "type", "verb"}, ...]

    Returns:
        每个组件的预筛选结果
    """
    system_raw = components.get("system_components", [])
    supersystem_raw = components.get("supersystem_components", [])

    system_names_set: set[str] = set()
    system_name_list: list[str] = []
    for c in system_raw:
        name = c["name"] if isinstance(c, dict) else c
        system_names_set.add(name)
        system_name_list.append(name)

    supersystem_names_set: set[str] = set()
    supersystem_name_list: list[str] = []
    for c in supersystem_raw:
        name = c["name"] if isinstance(c, dict) else c
        supersystem_names_set.add(name)
        supersystem_name_list.append(name)

    outgoing, _ = _build_adjacency(interactions)
    sinks = _identify_functional_sinks(
        system_names_set, supersystem_names_set, outgoing
    )

    results: list[ComponentPreScreenResult] = []

    for comp in system_name_list:
        matched: list[TrimmingRuleMatch] = []

        r = _check_rule_a(
            comp, system_names_set, supersystem_names_set, outgoing, sinks
        )
        if r:
            matched.append(r)

        r = _check_rule_b(comp, outgoing)
        if r:
            matched.append(r)

        matched.extend(_check_rule_c(comp, system_name_list, outgoing))
        matched.extend(_check_rule_d(comp, outgoing, supersystem_names_set))

        results.append(
            ComponentPreScreenResult(
                component_name=comp,
                component_type="system",
                matched_rules=matched,
            )
        )

    for comp in supersystem_name_list:
        matched: list[TrimmingRuleMatch] = []
        matched.extend(_check_rule_d(comp, outgoing, supersystem_names_set))
        if matched:
            results.append(
                ComponentPreScreenResult(
                    component_name=comp,
                    component_type="supersystem",
                    matched_rules=matched,
                )
            )

    return results


class TrimmingAnalyzer(AIAnalyzer):
    """TRIZ 功能裁剪分析器 — 规则预筛选 + AI 增强分析"""

    async def analyze_with_hints(
        self,
        problem: str,
        system_components: list[str],
        supersystem_components: list[str],
        interactions: list[dict],
        pre_screen_hints: list[ComponentPreScreenResult],
        resource_context: str = "",
        ideal_context: str = "",
    ) -> dict | None:
        """
        AI 增强裁剪分析：验证预筛选结果并生成详细裁剪计划

        Args:
            problem: 问题描述（含根因）
            system_components: 系统组件名称列表
            supersystem_components: 超系统组件名称列表
            interactions: 交互列表 [{"tool", "receiver", "type", "verb"}, ...]
            pre_screen_hints: pre_screen_components() 的输出
            resource_context: 可用资源上下文
            ideal_context: IFR 理想状态上下文

        Returns:
            {"trimming_candidates", "non_trimmable", "trimming_plan", "summary", "recommended_priority"}
        """
        system_str = ", ".join(system_components) if system_components else "无"
        supersystem_str = (
            ", ".join(supersystem_components) if supersystem_components else "无"
        )

        interactions_str = (
            "\n".join(
                f"  {i.get('tool', '?')} → {i.get('receiver', '?')}: {i.get('type', '?')} ({i.get('verb', '')})"
                for i in interactions
            )
            if interactions
            else "  无交互关系"
        )

        pre_screen_str = format_pre_screen_hints(pre_screen_hints)

        user_prompt = ZHISHU_TRIMMING_WITH_HINTS_USER_PROMPT_TEMPLATE.format(
            problem=problem,
            system_components_str=system_str,
            supersystem_components_str=supersystem_str,
            interactions_str=interactions_str,
            pre_screen_hints_str=pre_screen_str,
            resource_context=resource_context or "无",
            ideal_context=ideal_context or "无",
        )

        result = await self.call_ai_async(
            ZHISHU_TRIMMING_WITH_HINTS_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.1,
            logger_prefix="智枢裁剪计划",
            json_mode=True,
        )

        if result and isinstance(result, dict):
            return {
                "trimming_candidates": result.get("trimming_candidates", []),
                "non_trimmable": result.get("non_trimmable", []),
                "trimming_plan": result.get(
                    "trimming_plan",
                    {
                        "priority_order": [],
                        "dependency_notes": "",
                        "execution_strategy": "",
                    },
                ),
                "summary": result.get("summary", ""),
                "recommended_priority": result.get("recommended_priority", []),
            }
        return None
