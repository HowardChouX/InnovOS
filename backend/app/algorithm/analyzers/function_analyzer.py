"""
功能分析器 - 组件识别、交互分析和问题类型判断
智枢流程阶段0：基于系统描述提取组件和交互
"""

import asyncio
import json
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer

logger = logging.getLogger(__name__)

MAX_PARALLEL_PAIRS = 10  # 逐对交互分析的最大并行数

# ──────────────────────────────────────────────
# 提示词常量（从 RootSeek ai/prompts/function_analysis.py 内联）
# ──────────────────────────────────────────────

PAIRWISE_INTERACTION_SYSTEM_PROMPT = """判断组件对（工具→受体）之间是否存在真实的工程交互作用，并识别系统的设计功能。

【TRIZ功能定义】
功能 = 一个组件（工具）改变或维持另一个组件（受体）的参数。
验证方法（魔法棒测试）：如果移除工具组件，受体组件的状态是否会发生变化？
→ 是则存在功能；否则不存在功能。

【功能描述准则 — 必须严格遵守】

1. 非负面定义：❌"防止生锈" ✅"隔离氧气和水分" → 描述做了什么，不是没做什么
2. 非陈述性定义：❌"玻璃是透明的" ✅"玻璃透过可见光" → 描述动作，不是属性
3. 尽可能具体：❌"影响" ✅"加热/冷却/磨损" → 动词必须具体到物理动作
4. 标准格式：X改变Y的Z参数 → 当找不到精确动词时使用
5. 仅按因果关系：工具是原因，受体是结果

【设计功能定义】
设计功能 = 系统被设计来完成的最高层级技术功能。
从工具的功能描述中提炼：工具对受体做了什么，汇聚成系统的整体功能。

【设计功能 — 常见错误与正确答案】

❌ 错误类型1：写成用户需求
- "让玻璃干净"、"保护墙面"、"防止迟到"
→ 这些是目标/需求，不是系统做什么

❌ 错误类型2：写成系统属性/特性
- "透光"、"透气"、"透明"、"坚硬"
→ 这些是属性，不是功能。功能必须是动作。

❌ 错误类型3：写成实现机制
- "形成涂层"、"折射光线"
→ 这是手段，不是目的。涂层是为了什么？折射是为了什么？

✅ 正确：描述系统对环境/对象产生的实际效果
- 油漆刷墙 → 反射光线（油漆让墙面反射特定波长的光）
- 窗户 → 挡风挡雨（窗户阻隔风雨同时保持视觉连通）
- 抹布擦玻璃 → 吸附表面附着物（抹布捕获并移除污物颗粒）
- 手表 → 显示时间流逝（手表将时间间隔转化为可读信号）
- 椅子 → 支撑人体重量并维持坐姿稳定

【功能的类别】

功能分为两大类：有用的功能 和 有害的功能。

一、有用的功能（Useful Function）
工具对受体执行了设计预期的、对系统有益的功能。进一步细分为三种：

  1. 正常的功能（Normal Function）→ 实线箭头 →
     功能效果恰好满足系统要求，不多不少。
     示例：齿轮正常传递扭矩、散热片正常散热

  2. 不足的功能（Insufficient Function）→ 虚线箭头 - - →
     功能存在但效果不达标，需要增强。
     判断标准：功能存在但无法满足系统的正常工作要求，需要显著提升
     示例：润滑不足、冷却不足、密封不严、支撑不稳、定位不准

  3. 过量的功能（Excessive Function）→ 粗实线箭头 ══>
     功能存在但作用过头，超出所需范围，导致副作用或资源浪费。
     判断标准：功能强度超出所需，产生不必要的副作用
     示例：过热、过压、过载、过剩润滑、过度约束

二、有害的功能（Harmful Function）→ 锯齿线 ~~~
工具对受体产生了非预期的、需要消除或减轻的负面作用。
判断标准：该交互的存在降低了系统的某个性能参数（如可靠性、效率、寿命）
示例：磨损、腐蚀、振动、摩擦、堵塞、泄露、变形、断裂、污染

【类型判断流程 — 严格按以下顺序】
第1步：判断是否存在功能（魔法棒测试）
第2步：如果是有害的 → harmful
第3步：如果是有用的功能，结合系统问题描述来确定子类型：
  - 该交互与系统问题无关，功能效果恰好满足要求 → useful（正常）
  - 该交互与系统问题相关，且功能效果不达标、需要增强 → insufficient（不足）
  - 该交互与系统问题相关，且功能作用过头、超出所需 → excessive（过量）
  请结合系统描述中的问题来判断，不要在缺乏依据时猜测不足或过量。

【类型判断关键区分】
useful（正常）：功能效果恰好满足系统要求，且与当前系统问题无关。
insufficient（不足）：功能存在但效果不达标，且该不足与系统问题相关。关键词：不足、不够、偏低、偏弱、未达到、无法满足。
excessive（过量）：功能存在但作用过头，且该过量与系统问题相关。关键词：过度、过剩、偏高、偏强、超出、多余。
harmful（有害）：对受体产生非预期的负面作用。

【强制检查 — 每个有用功能必须回答】
对于每个判定为 useful 的交互，问自己：这个功能的效果真的恰好满足要求吗？
- 如果有任何迹象表明效果不足（如"冷却效果不够"、"支撑力偏弱"）→ 改为 insufficient
- 如果有任何迹象表明效果过头（如"加热过快"、"压力过高"）→ 改为 excessive
- 只有在确实没有不足或过头的证据时，才保留 useful

【四种类型的示例对比 — 散热系统】
- 散热片 → 空气: type="useful"（正常散热，效果恰好）
- 散热片 → 空气: type="insufficient"（散热不足，芯片过热）
- 散热片 → 空气: type="excessive"（过度散热，浪费能源或产生噪音）
- 齿轮 → 轴承: type="harmful"（磨损轴承，产生有害摩擦）

【关系度评分要求】
- 每次输出必须包含 relationship_strength 字段（0-100的整数）
- 0-20：基本不存在交互（组件名称无意义或属于完全不同的系统）
- 21-40：可能存在弱交互（名称暗示可能有关联但不明确）
- 41-60：可能存在交互（名称暗示有关联，但无明确工程机理）
- 61-80：很可能存在交互（名称表明明确的工程关系）
- 81-100：确定存在交互（标准工程组件对，关系明确）

【输出要求】
只输出JSON，不要输出任何其他文字。不要使用markdown代码块包裹。

【输出示例 — 四种类型各一个】
正常：{"exists": true, "tool": "散热片", "receiver": "芯片", "type": "useful", "verb": "散热", "parameter": "温度", "change_direction": "down", "relationship_strength": 90, "designed_function": "降低芯片温度"}
不足：{"exists": true, "tool": "散热片", "receiver": "芯片", "type": "insufficient", "verb": "散热不足", "parameter": "温度", "change_direction": "down", "relationship_strength": 75, "designed_function": "降低芯片温度"}
过量：{"exists": true, "tool": "散热片", "receiver": "芯片", "type": "excessive", "verb": "过度散热", "parameter": "温度", "change_direction": "down", "relationship_strength": 70, "designed_function": "降低芯片温度"}
有害：{"exists": true, "tool": "齿轮", "receiver": "轴承", "type": "harmful", "verb": "磨损", "parameter": "接触面粗糙度", "change_direction": "up", "relationship_strength": 85, "designed_function": "传递并变换扭矩"}

不存在交互时输出：
{"exists": false, "relationship_strength": 15, "designed_function": ""}

【影响参数要求】
- parameter：被影响的受体参数名称（如温度、转速、压力、粗糙度、强度）
- change_direction：参数变化方向，"up"表示增大，"down"表示减小
- 必须有具体参数名，不能为空

【功能方向要求】
- 组件对是无序的，由你判断谁对谁产生作用
- tool：功能载体（主动作用的组件）
- receiver：功能受体（被作用的组件）
- 如果组件A对组件B有作用，tool为A、receiver为B
- 如果组件B对组件A有作用，tool为B、receiver为A
- 必须有明确的tool和receiver，不能为空"""


class FunctionAnalyzer(AIAnalyzer):
    """功能分析器 - 组件识别、交互分析和问题类型判断"""

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        return await self.analyze_components(problem)

    async def analyze_components(
        self, problem: str, root_cause: str = ""
    ) -> dict[str, Any] | None:
        """识别系统组件和超系统组件（3步通用方案）

        适用于硬件、软件、流程、服务等各类系统：
        1. 系统定义 + 超系统组件识别（先识别外部要素）
        2. 系统组件枚举（排除已识别的超系统）
        3. 扩展补全（子组件拆分 + 遗漏检查）

        Args:
            problem: 系统描述
            root_cause: （已废弃，保持参数兼容）
        """
        # === 第一步：系统定义 + 超系统组件识别（先识别外部要素）===
        step1_prompt = f"""你是一个TRIZ功能分析专家。请分析以下系统，先明确系统边界和主功能，再识别**系统外部**的超系统组件。

【系统定义 — 适用于所有类型】
系统 = 被分析对象本身（可以是设备、软件、流程、服务或其组合）。
先判断系统类型，再识别超系统组件。

【关键概念：系统边界】
- 系统组件 = 系统**内部**的组成部分（下一步识别）
- 超系统组件 = 系统**外部**但与系统交互的要素（本步识别）

系统类型判断：
- 硬件系统：由物理部件组成的设备/工具（如电机、杯子、发动机）
- 软件系统：由代码模块/数据/接口组成的程序/平台（如电商系统、ERP）
- 流程系统：由步骤/节点/规则组成的业务流程（如审批流程、生产流程）
- 服务系统：由角色/触点/交付物组成的服务体系（如快递服务、医疗服务）
- 混合系统：以上类型的组合

【超系统定义】
超系统 = 系统边界**之外**但与系统存在交互或影响关系的要素。

【判断标准（满足任一即为超系统组件）】
1. 被系统处理/作用的对象（如：杯中的水、被审批的申请、被分析的数据）
2. 为系统提供输入的来源（如：电源、用户提交、上游系统输出）
3. 承接系统输出的对象（如：被加热的空气、审批结果、下游系统）
4. 影响系统运行的环境/约束（如：温度、法规、网络延迟）
5. 与系统交互的外部角色（如：操作者、管理员、第三方服务）

【各类系统的超系统示例】
硬件：水、空气、操作者、重力、温度、热量
软件：用户、第三方API、网络环境、操作系统
流程：申请人、审批人、法规政策、时间约束
服务：客户、供应商、监管机构、市场环境

【重要提示】
几乎所有系统都有超系统组件。请仔细检查：
- 系统处理的物质/对象是什么？
- 谁在使用/操作这个系统？
- 环境因素（温度、湿度、重力等）如何影响系统？
- 系统的输入来源和输出去向是什么？

【粒度标准】
- 与系统组件保持同一分析层级
- 相同类型合并（如多个操作者 → "操作者"）

【系统描述】
{problem}

【任务】
1. 判断系统类型
2. 明确系统的主功能
3. 识别所有超系统组件（至少3个），为每个提供描述

只输出JSON，不要输出任何其他文字：
{{"system_type": "硬件|软件|流程|服务|混合", "main_function": "系统的主功能描述", "supersystem_components": [{{"name": "超系统组件1", "description": "与系统的交互角色"}}]}}"""

        step1_result = await self.ai.call_ai_async(
            step1_prompt,
            "请分析系统并枚举所有组件。",
            temperature=0.1,
            logger_prefix="组件分析-第1步",
            json_mode=True,
        )
        if not step1_result or not isinstance(step1_result, dict):
            logger.warning("第1步未返回有效结果")
            return None

        # 收集超系统组件
        supersystem_components: list[dict] = []
        raw_super = step1_result.get("supersystem_components", [])
        for item in raw_super:
            if isinstance(item, dict):
                supersystem_components.append(item)
            elif isinstance(item, str):
                supersystem_components.append({"name": item, "description": ""})

        supersystem_names = {c.get("name", "") for c in supersystem_components if c.get("name")}

        logger.info(
            f"第1步完成: 系统类型={step1_result.get('system_type', '未指定')}, "
            f"主功能={step1_result.get('main_function', '')[:50]}, "
            f"超系统组件={len(supersystem_components)} 个"
        )

        # === 第二步：系统组件枚举（排除超系统）===
        super_str = json.dumps(list(supersystem_names), ensure_ascii=False)
        step2_prompt = f"""你是一个TRIZ功能分析专家。请分析以下系统，枚举所有**系统内部**组件。

【系统描述】
{problem}

【系统类型】
{step1_result.get('system_type', '未指定')}

【主功能】
{step1_result.get('main_function', '')}

【已识别的超系统组件（以下不是系统组件，不能重复列出）】
{super_str}

【关键概念：系统边界】
- 系统组件 = 系统**内部**的组成部分，在系统边界**之内**
- 超系统组件 = 系统**外部**但与系统交互的要素（已在上一步识别）
- **以下超系统组件不能作为系统组件列出**

【系统组件定义 — 仅限系统边界内的要素】
组件 = 系统**内部**承担独立功能角色的要素。
判断标准（魔法棒测试）：移除该要素后，系统的功能或行为是否改变？
→ 是则为组件；否则不是。

【各类系统的系统组件示例】
硬件：杯身、电机、齿轮、密封圈、内壁、涂层
软件：用户模块、数据库、API接口、消息队列、配置文件
流程：申请提交、审批节点、数据校验、结果通知
服务：客服系统、交付渠道、支付接口、反馈机制

【常见遗漏清单 — 请逐项检查】
1. 连接/密封/紧固要素（接口、协议、胶水、垫圈）
2. 内部通道/空腔/数据流（管道、缓存、消息队列）
3. 表面/层/修饰（涂层、处理层、UI主题）
4. 辅助/支撑/导向结构（支架、路由、中间件）
5. 控制/传感/反馈要素（传感器、配置项、监控模块）

【粒度标准】
- 输出承担独立功能的最小有意义单元
- 相同类型合并（如四条椅腿 → "椅腿"）
- 组件名称用名词

【组件描述要求】
- 每个组件用一句话描述其功能角色

【任务】
枚举所有系统内部组件（排除超系统组件），为每个组件提供功能描述。

只输出JSON，不要输出任何其他文字：
{{"components": [{{"name": "组件A", "description": "功能描述"}}]}}"""

        step2_result = await self.ai.call_ai_async(
            step2_prompt,
            "请枚举系统内部组件。",
            temperature=0.1,
            logger_prefix="组件分析-第2步",
            json_mode=True,
        )

        # 收集系统组件
        seen: set[str] = set()
        all_system_components: list[str] = []
        component_descriptions: dict[str, str] = {}

        if step2_result and isinstance(step2_result, dict):
            raw_components = step2_result.get("components", [])
            for c in raw_components:
                if isinstance(c, dict):
                    cname = c.get("name", "")
                    cdesc = c.get("description", "")
                else:
                    cname = str(c)
                    cdesc = ""
                # 排除已在超系统中的组件
                if cname and cname not in seen and cname not in supersystem_names:
                    seen.add(cname)
                    all_system_components.append(cname)
                    if cdesc:
                        component_descriptions[cname] = cdesc

        logger.info(f"第2步完成: 识别出 {len(all_system_components)} 个系统组件")

        # === 第三步：扩展补全 ===
        components_to_remove: set[str] = set()
        components_to_add: list[str] = []

        if all_system_components:
            comps_str = json.dumps(all_system_components, ensure_ascii=False)
            step3_prompt = f"""你是一个TRIZ功能分析专家。以下系统已完成初步组件识别，请从多个角度检查是否有遗漏，并对需要拆分的组件进行拆分。

【系统描述】
{problem}

【已识别的系统组件】
{comps_str}

【已识别的超系统组件（不需要再添加）】
{super_str}

【任务1：子组件拆分】
对每个已识别组件，判断是否需要拆分：
- 拆分条件（两个条件必须同时满足）：
  · 功能方向分叉 — 组件的不同部分执行不同的功能
  · 可分离 — 这些部分是可独立存在的要素
- 不拆分的情况：各部分始终作为整体工作、同一要素的不同面/区域

【任务2：遗漏检查 — 从以下3个视角检查】
1. 交互视角：与已识别组件直接交互但还未列出的系统内部要素有哪些？
2. 问题视角：问题涉及哪些参数？哪些系统内部要素影响这些参数但未被列出？
3. 结构视角：系统内部是否有被忽略的通道、接口、辅助结构？

【任务3：为新增组件生成描述】
每个新增组件用一句话描述其功能角色。

只输出JSON，不要输出任何其他文字：
{{"splits": {{"原组件A": [{{"name": "子组件1", "description": "描述"}}, {{"name": "子组件2", "description": "描述"}}]}}, "additions": [{{"name": "新组件", "description": "描述"}}]}}"""

            step3_result = await self.ai.call_ai_async(
                step3_prompt,
                "请检查遗漏并拆分需要拆分的组件。",
                temperature=0.1,
                logger_prefix="组件分析-第3步",
                json_mode=True,
            )

            if step3_result and isinstance(step3_result, dict):
                # 处理拆分
                splits = step3_result.get("splits", {})
                for parent, children in splits.items():
                    if isinstance(children, list) and children:
                        components_to_remove.add(parent)
                        for child in children:
                            if isinstance(child, dict):
                                cname = child.get("name", "")
                                cdesc = child.get("description", "")
                            else:
                                cname = str(child)
                                cdesc = ""
                            if cname and cname not in seen and cname not in supersystem_names:
                                seen.add(cname)
                                components_to_add.append(cname)
                                if cdesc:
                                    component_descriptions[cname] = cdesc
                        logger.info(f"组件 '{parent}' 拆分为: {[c.get('name', c) if isinstance(c, dict) else c for c in children]}")

                # 处理新增
                additions = step3_result.get("additions", [])
                for item in additions:
                    if isinstance(item, dict):
                        cname = item.get("name", "")
                        cdesc = item.get("description", "")
                    else:
                        cname = str(item)
                        cdesc = ""
                    if cname and cname not in seen and cname not in supersystem_names:
                        seen.add(cname)
                        components_to_add.append(cname)
                        if cdesc:
                            component_descriptions[cname] = cdesc

        # 构建最终系统组件列表
        final_system_components = [
            c for c in all_system_components if c not in components_to_remove
        ]
        final_system_components.extend(components_to_add)

        logger.info(
            f"第3步完成: 拆分 {len(components_to_remove)} 个, "
            f"新增 {len(components_to_add)} 个, "
            f"最终 {len(final_system_components)} 个系统组件"
        )

        # 构建最终结果
        system_comps_with_desc = [
            {"name": name, "description": component_descriptions.get(name, "")}
            for name in final_system_components
        ]

        result = {
            "system_components": system_comps_with_desc,
            "supersystem_components": supersystem_components,
            "system_type": step1_result.get("system_type", ""),
            "main_function": step1_result.get("main_function", ""),
            "analysis": f"通过三步分析：系统类型={step1_result.get('system_type', '未指定')}，{len(final_system_components)}个系统组件，{len(supersystem_components)}个超系统组件",
        }

        return result

    async def analyze_pairwise_interactions(
        self,
        problem: str,
        system_components: list[str] | list[dict],
        supersystem_components: list[str] | list[dict],
        progress_callback=None,
    ) -> dict[str, Any] | None:
        """逐对分析：先判断接触，再判断交互关系（并行）"""
        # 提取组件名称和描述
        comp_descriptions: dict[str, str] = {}

        def _extract(items: list) -> list[str]:
            names = []
            for item in items:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    desc = item.get("description", "")
                else:
                    name = str(item)
                    desc = ""
                if name:
                    names.append(name)
                    if desc:
                        comp_descriptions[name] = desc
            return names

        all_components = _extract(system_components) + _extract(supersystem_components)
        pairs = [(a, b) for a in all_components for b in all_components if a != b]

        logger.info(f"逐对交互分析，共 {len(pairs)} 对，并行数 {MAX_PARALLEL_PAIRS}")
        interactions: list[dict] = []
        no_contact_count = 0
        completed = 0

        for batch_start in range(0, len(pairs), MAX_PARALLEL_PAIRS):
            batch = pairs[batch_start:batch_start + MAX_PARALLEL_PAIRS]
            tasks = [
                asyncio.wait_for(
                    self._analyze_one_pair(problem, tool, receiver, comp_descriptions), timeout=120.0
                )
                for tool, receiver in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (tool, receiver), result in zip(batch, results, strict=True):
                completed += 1
                if isinstance(result, Exception):
                    logger.error(f"[{completed}/{len(pairs)}] {tool}→{receiver}: {result}")
                    continue
                if result is None:
                    no_contact_count += 1
                    continue
                interactions.append(result)

            if progress_callback:
                cb = progress_callback(completed, len(pairs), f"批次 {batch_start // MAX_PARALLEL_PAIRS + 1}")
                if cb is not None:
                    await cb

        logger.info(
            f"接触分析完成: {no_contact_count}/{len(pairs)} 对无接触，{len(interactions)} 个交互关系"
        )

        return {
            "interactions": interactions,
            "total_pairs": len(pairs),
            "no_contact_pairs": no_contact_count,
            "contact_pairs": len(pairs) - no_contact_count,
        }

    async def _analyze_one_pair(
        self, problem: str, tool: str, receiver: str, comp_descriptions: dict[str, str] | None = None
    ) -> dict | None:
        """分析单个组件对的接触和交互关系"""
        contact_prompt = """你是一个TRIZ功能分析专家。请判断两个组件之间是否存在物理接触。

【接触定义】
接触是指两个组件在空间上直接相邻或接触，存在物理上的连接或邻近关系。

【判断标准】
- 直接接触：两个组件的表面直接接触（如齿轮与轴、轮胎与地面）
- 间接接触：通过其他介质接触（如通过液体、气体、场）
- 空间邻近：组件在空间上非常接近，可能产生交互

【组件A】{component_a}
【组件B】{component_b}

【系统描述】
{problem}

只输出JSON，不要输出任何其他文字：
{{"has_contact": true/false, "contact_type": "直接接触/间接接触/空间邻近/无接触", "description": "接触描述"}}"""

        # 第一步：判断是否有接触
        contact_result = await self.ai.call_ai_async(
            contact_prompt.format(component_a=tool, component_b=receiver, problem=problem),
            f"判断{tool}和{receiver}是否有接触。",
            temperature=0.1,
            json_mode=True,
            logger_prefix=f"接触分析-{tool}→{receiver}",
        )

        if not contact_result or not isinstance(contact_result, dict):
            return None

        if not contact_result.get("has_contact", False):
            return None

        # 第二步：有接触，分析交互关系
        tool_desc = (comp_descriptions or {}).get(tool, "")
        receiver_desc = (comp_descriptions or {}).get(receiver, "")
        desc_context = ""
        if tool_desc or receiver_desc:
            desc_lines = []
            if tool_desc:
                desc_lines.append(f"  {tool}：{tool_desc}")
            if receiver_desc:
                desc_lines.append(f"  {receiver}：{receiver_desc}")
            desc_context = "\n【组件描述】\n" + "\n".join(desc_lines)

        pair_prompt = f"""系统描述：{problem}

判断组件对：{tool} → {receiver}
{desc_context}

【接触信息】
接触类型：{contact_result.get("contact_type", "未知")}
接触描述：{contact_result.get("description", "")}

该组件对是否存在工程交互？如果存在，功能动词是什么？

【类型判断 — 必须从以下四种中选择】
判断依据（魔法棒测试）：如果移除{tool}，{receiver}的状态是否会发生变化？

1. harmful（有害）：{tool}对{receiver}产生非预期的负面作用（磨损、腐蚀、干扰、泄漏等）
2. useful（正常）：{tool}对{receiver}执行设计功能，效果恰好满足系统要求
3. insufficient（不足）：{tool}对{receiver}有功能作用，但效果不达标、偏弱、不够
4. excessive（过量）：{tool}对{receiver}有功能作用，但效果过头、偏强、超出需要

【自检 — 对每个判定为 useful 的交互必须回答】
问自己：这个功能的效果真的恰好满足要求吗？
- 如果有任何迹象表明效果不足（偏弱、不够、未达标）→ 改为 insufficient
- 如果有任何迹象表明效果过头（偏强、过多、超出需要）→ 改为 excessive
- 只有在确实没有不足或过头的证据时，才保留 useful

请结合系统描述中的问题上下文来判断交互类型。"""

        pair_result = await self.ai.call_ai_async(
            PAIRWISE_INTERACTION_SYSTEM_PROMPT,
            pair_prompt,
            temperature=0.1,
            json_mode=True,
            logger_prefix=f"逐对分析-{tool}→{receiver}",
        )
        if not pair_result or not isinstance(pair_result, dict):
            return None

        if pair_result.get("exists") and pair_result.get("type"):
            return {
                "tool": tool,
                "receiver": receiver,
                "type": pair_result["type"],
                "verb": pair_result.get("verb", ""),
                "parameter": pair_result.get("parameter", ""),
                "change": pair_result.get("change_direction", "") or pair_result.get("change", ""),
                "description": pair_result.get("description", ""),
                "designed_function": pair_result.get("designed_function", ""),
            }
        return None

    async def analyze_designed_function(
        self,
        problem: str,
        system_components: list[str],
        supersystem_components: list[str],
        interactions: list[dict],
    ) -> dict[str, Any] | None:
        """基于交互关系分析系统的设计功能"""
        ix_lines = []
        for ix in interactions[:30]:
            verb = ix.get("verb", "")
            param = ix.get("parameter", "")
            change = ix.get("change", "")
            change_symbol = {"up": "↑", "down": "↓"}.get(change, "")
            param_str = f"{param}{change_symbol}" if param else ""
            ix_lines.append(
                f"  {ix.get('tool', '?')} → {ix.get('receiver', '?')}: "
                f"{verb}({param_str}) [{ix.get('type', '?')}]"
            )
        ix_str = "\n".join(ix_lines) if ix_lines else "无交互数据"

        sys_str = "、".join(system_components) if system_components else "无"
        super_str = (
            "、".join(supersystem_components) if supersystem_components else "无"
        )

        prompt = f"""你是一个TRIZ功能分析专家。请基于以下组件交互关系，识别系统的设计功能。

【系统边界】
系统 = 被分析的技术设备/工具本身，不是整个操作场景。

【系统描述】
{problem}

【系统组件】
{sys_str}

【超系统组件】
{super_str}

【组件交互关系】
{ix_str}

【功能描述准则 — 必须严格遵守】

1. 非负面定义
   ❌ "防止生锈"、"避免过热"、"减少摩擦"
   ✅ "隔离氧气和水分"、"带走热量"、"降低摩擦力"
   → 描述功能做了什么，而不是没做什么

2. 非陈述性定义
   ❌ "玻璃是透明的"、"抹布是柔软的"
   ✅ "玻璃透过可见光"、"抹布贴合不规则表面"
   → 描述动作，不是属性

3. 尽可能具体
   ❌ "影响"、"作用于"、"改变"
   ✅ "加热"、"冷却"、"加速"、"磨损"、"密封"
   → 动词必须具体到物理动作

4. 标准格式：X改变Y的Z参数
   当找不到精确动词时，使用：工具改变受体的参数

5. 仅按因果关系定义
   工具是原因，受体是结果。
   确认：移除工具后，受体的参数是否真的会变化？

【设计功能定义】
设计功能 = 系统被设计来完成的最高层级技术功能。

【常见错误与正确答案】
❌ 写成用户需求："让玻璃干净"、"保护墙面" → 这是目标，不是功能
❌ 写成系统属性："透光"、"透气"、"透明" → 这是属性，功能必须是动作
❌ 写成实现机制："形成涂层"、"折射光线" → 这是手段，不是目的
✅ 描述系统对环境/对象产生的实际效果：
  - 油漆 → 反射光线
  - 窗户 → 挡风挡雨
  - 抹布 → 吸附表面附着物
  - 手表 → 显示时间流逝
  - 椅子 → 支撑人体重量并维持坐姿稳定

只输出JSON：
{{"system": "系统名称", "designed_function": "设计功能描述"}}"""

        result = await self.ai.call_ai_async(
            prompt,
            "请分析系统的设计功能。",
            temperature=0.1,
            logger_prefix="功能建模-设计功能",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        designed_function = result.get("designed_function", "")
        system_name = result.get("system", "")

        if designed_function:
            logger.info(f"设计功能: {system_name} — {designed_function}")

        return {
            "system": system_name,
            "designed_function": designed_function,
        }

    async def detect_problem_type(
        self,
        problem: str,
        interactions: list[dict],
    ) -> dict[str, Any] | None:
        """判断问题类型（技术矛盾/物理矛盾/物场问题/测量问题）"""
        ix_str = "\n".join(
            [
                f"  · {ix['tool']} → {ix['receiver']}: {ix.get('type', '?')} ({ix.get('verb', '')})"
                for ix in interactions[:20]
            ]
        )

        prompt = f"""系统描述：{problem}

交互关系：
{ix_str}

请判断这个系统面临的主要问题类型（可多选）：
A. 技术矛盾：改善一个参数导致另一个参数恶化
B. 物理矛盾：同一参数需要满足相反需求
C. 物场问题：物质-场模型不完整/存在有害作用/作用不足
D. 测量问题：需要测量但无法直接测量

只输出JSON：
{{"problem_types": ["A", "B"], "primary": "A", "explanation": "判断理由"}}"""

        result = await self.ai.call_ai_async(
            PAIRWISE_INTERACTION_SYSTEM_PROMPT,
            prompt,
            temperature=0.2,
            logger_prefix="问题类型判断",
            json_mode=True,
        )
        return result if isinstance(result, dict) else None
