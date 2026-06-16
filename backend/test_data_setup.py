"""
Step 1 & 2: Enrich knowledge base and add patents via SQL + embedding API
"""
import asyncio
import json
import sys
import os
import uuid

# Ensure PostgreSQL connection
os.environ.setdefault("DATABASE_URL", "postgresql://innovos:innovos_secret@localhost:5432/innovos")
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db
from app.algorithm.model_resolver import model_resolver
from app.algorithm.knowledge.embedder import Embedder

KNOWLEDGE_NOTES = [
    {
        "title": "手机散热TRIZ资源分析",
        "content": """TRIZ资源分析——手机散热系统资源盘点

【物质资源】
- 手机内部空间资源：主板与屏幕之间存在0.8-1.2mm的空气夹层，可作为导热介质空间
- 石墨片：已广泛使用的各向异性导热材料，面内导热率1500W/mK
- VC均热板：铜质密封腔体，内部工质相变传热，等效导热率可达10000W/mK以上
- 手机外壳：铝合金/玻璃材质，本身具有导热能力，但热阻较大

【能量资源】
- 芯片废热：处理器功耗3-8W，是需要消散的热源，但也蕴含可利用的温差能
- 环境空气：室温25°C与芯片80°C之间存在55°C温差，是天然散热驱动力
- 电池化学能：快充时电能转化为化学能再转化为热能的转化链中，化学反应热可被预估和管理

【信息资源】
- 温度传感器数据：CPU/GPU/电池多点测温，可实时反馈热状态
- 用户使用模式数据：游戏/视频/充电等场景可预判发热模式
- 历史温度曲线：可预测温度变化趋势，提前干预

【时间资源】
- 间歇性高负载：游戏帧间间隙（16ms）可插入降频窗口
- 充电初期：恒流阶段发热最大，恒压阶段可利用自然冷却
- 开机预热时间：用户对初始温度上升有一定容忍度

【空间资源】
- 手机侧面边框：未被充分散热利用的区域
- 摄像头模组周围：金属结构件可兼做散热路径
- SIM卡槽下方空间：可布置微型导热元件

【功能资源】
- NFC线圈：铜质线圈可兼做辅助导热路径
- 无线充电线圈：本身具备导热属性
- 扬声器腔体：空气通道可引导散热气流

【系统资源】
- 手机支架/底座：外部配件可增加散热面积
- 蓝牙耳机充电盒：可设计为手机散热底座
- 汽车车载支架：利用车载空调辅助散热"""
    },
    {
        "title": "手机散热理想最终结果IFR分析",
        "content": """理想最终结果(IFR)分析——手机散热系统

【IFR-1：理想系统】
手机自行散热，不需要任何外部散热设备或额外散热结构。
处理器在满负载运行时不产生超过手感温度（38°C）的热量。
实现方式：芯片本身通过材料创新实现自散热，如基于石墨烯的自散热芯片基板。

【IFR-2：理想子系统】
散热功能由手机已有的部件自然承担，不增加任何重量和体积。
屏幕在显示的同时充当散热面板——透明散热薄膜技术。
手机壳体本身就是散热器——相变材料集成到外壳中。

【X-Element（未知解决方案元素）】
一种能够在芯片温度升高时自动激活的智能导热材料。
该材料在常温下是绝缘体（不影响电子元件），高温时变为高导热导体。
可能的候选：液态金属合金（如镓铟合金），熔点约15°C，室温液态，高温时导热率极高。

【物理矛盾分析】
矛盾1：手机需要散热（需要大导热面积）vs 手机需要轻薄（需要小体积）
  - 分离原理：时间分离——高负载时展开散热结构，低负载时收回
  - 空间分离：内部采用超薄高导热材料（石墨烯），外部通过配件扩展面积

矛盾2：散热需要空气流通 vs 手机需要防水防尘
  - 分离原理：系统级别分离——内部密封循环散热，外部开放对流散热
  - 采用液冷回路在内部传递热量到边框，边框表面自然对流

矛盾3：快充需要高功率输入 vs 高功率带来大量热量
  - 分离原理：条件分离——充电管理芯片根据温度动态调整充电功率
  - 充电路径与散热路径解耦"""
    },
    {
        "title": "手机散热技术矛盾与创新方向",
        "content": """技术矛盾矩阵——手机散热创新方向

【技术矛盾1】
改善：温度降低 -> 恶化：手机厚度增加
TRIZ发明原理：#35参数变化 #14曲面化 #1抽取
创新方向：使用超薄石墨烯+VC均热板组合，在0.3mm厚度内实现高效散热

【技术矛盾2】
改善：散热效率提高 -> 恶化：电池续航降低（主动散热耗电）
TRIZ发明原理：#28机械系统替代 #10预先作用 #25自服务
创新方向：利用芯片废热驱动热电制冷（塞贝克效应），不需要额外电能

【技术矛盾3】
改善：散热面积增大 -> 恶化：手持舒适度下降
TRIZ发明原理：#15动态化 #3局部质量 #17空间维度变化
创新方向：可折叠散热背夹，仅在游戏/重载时展开

【技术矛盾4】
改善：导热速度加快 -> 恶化：成本增加
TRIZ发明原理：#28机械系统替代 #13反向操作 #35参数变化
创新方向：用石墨烯替代银纳米粒子导热膏，成本降低但性能相当

【技术矛盾5】
改善：散热噪音降低 -> 恶化：散热效率降低（无风扇方案散热差）
TRIZ发明原理：#10预先作用 #25自服务 #21快速通过
创新方向：基于相变材料的被动散热，完全无噪音，利用相变潜热缓冲温度峰值

【技术进化路线】
S曲线位置：手机散热处于成长期向成熟期过渡
下一代趋势：从被动散热到主动散热到智能散热到自适应散热
关键突破点：AI温控调度+相变材料+液态金属导热"""
    },
    {
        "title": "手机散热用户需求与市场分析",
        "content": """手机散热用户需求与市场分析

【核心用户需求】
1. 游戏不掉帧（45%用户）：持续满负载30分钟以上不降频
2. 手不烫手（30%用户）：表面温度控制在40°C以下
3. 充电不发烫（15%用户）：快充过程中温度可控
4. 轻薄不受影响（10%用户）：散热方案不增加明显厚度和重量

【用户使用场景痛点】
- 王者荣耀/原神等大型游戏运行10分钟后面板温度超过45°C
- 夏天户外导航+充电时手机温度超过50°C触发保护关机
- 长时间视频通话手机边框烫手无法握持
- 直播场景手机持续高负载发热严重

【市场现有解决方案对比】
方案 石墨烯膜：散热效果3星，厚度增加0.03mm，成本低，功耗0
方案 VC均热板：散热效果4星，厚度增加0.4mm，成本中，功耗0
方案 微型风扇：散热效果5星，厚度增加2mm，成本高，功耗0.5W
方案 半导体制冷：散热效果5星，厚度增加1mm，成本高，功耗3W
方案 相变材料：散热效果3.5星，厚度增加0.5mm，成本中，功耗0

【行业发展趋势】
- 2024年旗舰机普遍采用VC+石墨烯+导热凝胶三件套
- 游戏手机开始集成半导体散热背夹
- 折叠屏手机需要更创新的散热方案（空间受限）
- AI手机概念下功耗进一步增加，散热需求持续上升"""
    },
    {
        "title": "手机散热物场分析与进化路线",
        "content": """物场分析与技术进化路线——手机散热

【物场模型分析】
基本物场：S1(芯片热) - F(热传导) - S2(散热结构)

问题物场1：S1(芯片热) - F(传导) - S2(空气层)
- 效果不足：空气导热率仅0.026W/mK，热阻过大
- 解决方案：用高导热材料替换空气层（石墨烯/液态金属）

问题物场2：S1(芯片热) - F(传导) - S2(散热器)
- 有害效应：散热器占据宝贵空间
- 解决方案：物场扩大——引入F2(相变吸热)辅助散热

问题物场3：S1(芯片热) - F1(传导) + F2(辐射) - S2(外壳)
- 效果过度：外壳温度过高影响用户体验
- 解决方案：物场分割——内层快速传导+外层缓慢释放

【技术进化八大法则应用】
1. 提高理想度：散热功能从外挂配件到内置结构到芯片自散热
2. 子系统不均衡进化：散热系统落后于芯片性能进化
3. 向超系统进化：单机散热到手机+配件系统散热到手机+环境协同散热
4. 向微观级进化：宏观散热结构到纳米级导热材料到分子级热管理
5. 向动态化进化：固定散热结构到可变散热到自适应智能散热
6. 趋向完整性和连通性：散热路径从局部到全路径到闭环循环
7. 从宏观向微观转移：风扇到热管到VC到石墨烯到碳纳米管
8. 协调性进化：散热系统与电源管理系统协调，与用户行为协调

【进化路线图】
第1代：金属中框散热（被动，低效）
第2代：石墨烯+VC散热（被动，中效）
第3代：微型风扇+VC散热（主动，高效）
第4代：相变材料+智能调度（被动+AI，高效+节能）
第5代：自适应散热系统（AI预测+多模态切换）
第6代：芯片级自散热（材料革命，终极方案）"""
    },
]

PATENTS = [
    {"title": "一种基于石墨烯的手机超薄散热结构", "abstract": "本发明公开了一种基于石墨烯的手机超薄散热结构，包括铜箔基底层、石墨烯导热层和绝缘保护层。石墨烯层采用化学气相沉积法制备，面内导热率达到1500W/mK以上，整体厚度仅0.03mm。通过多层石墨烯叠加设计，实现热量从芯片区域向手机背板的快速均匀扩散，可将手机表面最高温度降低5-8°C。适用于5G智能手机、游戏手机等高功耗移动设备。", "applicants": '["华为技术有限公司"]', "inventors": '["张明", "李华"]', "filing_date": "2023-06-15", "publication_date": "2024-01-10", "patent_number": "CN202310XXXXX1", "ipc_codes": '["H01M10/6556", "H05K7/20"]', "relevance_score": 0.95},
    {"title": "手机用超薄VC均热板及其制造方法", "abstract": "本发明涉及一种厚度为0.3mm的超薄均热板(VC)，包括铜质上盖板、铜质下盖板和内部烧结铜粉毛细结构。内部填充去离子水作为工质，通过蒸发-冷凝循环实现高效均温传热。等效导热率超过10000W/mK，可将芯片热点温度均匀扩散至整个均热板表面，温差控制在3°C以内。适用于空间受限的轻薄手机。", "applicants": '["中兴通讯股份有限公司"]', "inventors": '["王强", "赵丽"]', "filing_date": "2023-08-20", "publication_date": "2024-03-15", "patent_number": "CN202310XXXXX2", "ipc_codes": '["H01M10/6556", "F28D15/02"]', "relevance_score": 0.93},
    {"title": "一种手机用相变储热散热模组", "abstract": "本发明公开了一种手机用相变储热散热模组，采用石蜡基相变材料(PCM)与导热石墨烯复合，封装在0.5mm厚的铝制腔体内。相变温度设定为42度，利用相变潜热(约200J/g)在芯片温度突升时吸收大量热量，延缓温升速度。可持续吸收热量约15分钟，为用户提供充足的散热缓冲时间，特别适合游戏等短时高负载场景。", "applicants": '["小米科技有限责任公司"]', "inventors": '["刘伟", "陈芳"]', "filing_date": "2023-09-01", "publication_date": "2024-02-20", "patent_number": "CN202310XXXXX3", "ipc_codes": '["H01M10/6556", "F28F21/00"]', "relevance_score": 0.91},
    {"title": "智能手机液态金属导热界面材料", "abstract": "本发明涉及一种用于智能手机的液态金属导热界面材料，由镓铟锡合金制成。室温下为液态，导热系数73W/mK，远高于传统导热硅脂(3-8W/mK)。采用微胶囊封装技术防止液态金属泄漏和腐蚀，接触热阻降低80%。可将芯片至散热器的热传导效率提升3倍，特别适用于高性能游戏手机。", "applicants": '["苹果公司"]', "inventors": '["John Smith", "王磊"]', "filing_date": "2023-04-10", "publication_date": "2023-12-05", "patent_number": "CN202310XXXXX4", "ipc_codes": '["H01M10/6556", "C22C28/00"]', "relevance_score": 0.89},
    {"title": "一种手机散热背夹的半导体制冷方案", "abstract": "本发明公开了一种手机散热背夹的半导体制冷方案。采用微型热电制冷器(TEC)，冷端通过铝合金导冷板紧贴手机背面，热端通过微型风扇散热。制冷功率5W，可将手机背面温度降低10-15度。集成温度传感器和PID控制算法，根据手机温度自动调节制冷功率。配备磁吸式安装结构，兼容不同尺寸手机。", "applicants": '["努比亚技术有限公司"]', "inventors": '["周杰", "吴明"]', "filing_date": "2023-07-25", "publication_date": "2024-01-20", "patent_number": "CN202310XXXXX5", "ipc_codes": '["H01M10/6556", "H01L35/30"]', "relevance_score": 0.88},
    {"title": "一种手机热管散热结构优化设计", "abstract": "本发明涉及一种手机热管散热结构优化设计方法。采用0.4mm超薄烧结热管，通过有限元仿真优化热管弯曲路径和蒸发段冷凝段布局。热管内部采用铜粉烧结毛细结构，工质为去离子水。将热管蒸发段紧贴芯片，冷凝段延伸至手机边框区域，利用金属边框辅助散热。优化后散热效率提升40%，芯片温度降低6度。", "applicants": '["OPPO广东移动通信有限公司"]', "inventors": '["黄勇", "林雪"]', "filing_date": "2023-05-18", "publication_date": "2023-11-28", "patent_number": "CN202310XXXXX6", "ipc_codes": '["F28D15/02", "H01M10/6556"]', "relevance_score": 0.86},
    {"title": "手机芯片级微通道液冷散热系统", "abstract": "本发明公开了一种手机芯片级微通道液冷散热系统。在芯片封装内部集成微通道结构（通道宽度50-200um），通过微型泵驱动冷却液循环。冷却液从芯片热区吸收热量后流经手机内部蛇形管路，最终在手机背部散热鳍片处释放热量。系统总厚度0.8mm，散热功率可达10W，比传统方案效率提升200%。", "applicants": '["三星电子株式会社"]', "inventors": '["金在勋", "朴智妍"]', "filing_date": "2023-10-12", "publication_date": "2024-04-18", "patent_number": "CN202310XXXXX7", "ipc_codes": '["H01L23/473", "F28D15/00"]', "relevance_score": 0.85},
    {"title": "基于AI温控的手机智能散热调度方法", "abstract": "本发明涉及一种基于AI温控的手机智能散热调度方法。通过部署在芯片上的多点温度传感器实时采集温度数据，利用轻量化LSTM神经网络预测未来30秒的温度变化趋势。根据预测结果提前调整CPU/GPU频率、激活散热背夹风扇、调节充电功率。预测准确率达92%，可将温度超标时间减少60%，同时保持95%的性能输出。", "applicants": '["vivo移动通信有限公司"]', "inventors": '["孙鹏", "马丽"]', "filing_date": "2023-11-05", "publication_date": "2024-05-10", "patent_number": "CN202310XXXXX8", "ipc_codes": '["G06N3/08", "H01M10/6556"]', "relevance_score": 0.84},
    {"title": "手机用柔性石墨烯散热膜及其制备方法", "abstract": "本发明公开了一种手机用柔性石墨烯散热膜，采用还原氧化石墨烯(rGO)与聚酰亚胺(PI)复合制备。厚度0.02mm，面内导热率1200W/mK，可弯曲半径小于5mm。通过真空抽滤加热压工艺制备，成本仅为CVD石墨烯的三分之一。适用于折叠屏手机等需要弯曲散热路径的场景，可沿铰链区域铺设实现跨区域导热。", "applicants": '["常州碳材料科技有限公司"]', "inventors": '["钱学明", "杨柳"]', "filing_date": "2023-03-20", "publication_date": "2023-10-15", "patent_number": "CN202310XXXXX9", "ipc_codes": '["H01M10/6556", "C01B32/198"]', "relevance_score": 0.82},
    {"title": "一种手机散热与无线充电一体化结构", "abstract": "本发明涉及一种手机散热与无线充电一体化结构。将无线充电接收线圈与VC均热板集成，线圈铜层兼做均热板上盖板。充电时产生的热量通过VC快速扩散，同时VC将芯片热量传导至线圈区域增大散热面积。一体化设计节省0.3mm厚度空间，散热效率提升25%。支持Qi2/MagSafe标准，最大充电功率15W时温度控制在42度以下。", "applicants": '["苹果公司"]', "inventors": '["Tim Cook", "赵鑫"]', "filing_date": "2023-08-30", "publication_date": "2024-02-28", "patent_number": "CN202310XXXXX10", "ipc_codes": '["H02J7/00", "H01M10/6556"]', "relevance_score": 0.80},
    {"title": "一种热管式服务器散热系统", "abstract": "本发明公开了一种热管式服务器散热系统，采用多根环路热管将服务器CPU热量传导至机箱外部散热器。系统包括蒸发段、绝热段和冷凝段，工质采用R134a制冷剂。散热功率可达200W，适用于1U/2U机架式服务器。热管路径优化设计减少了80%的风道依赖，降低风扇噪音。", "applicants": '["联想集团"]', "inventors": '["张伟", "李娜"]', "filing_date": "2022-12-01", "publication_date": "2023-06-15", "patent_number": "CN202210XXXXX11", "ipc_codes": '["G06F1/20", "F28D15/02"]', "relevance_score": 0.65},
    {"title": "笔记本电脑用石墨烯散热垫", "abstract": "本发明涉及一种笔记本电脑用石墨烯散热垫，采用多层石墨烯复合材料与铝制底座一体化设计。散热垫通过热管与笔记本底部接触，将CPU热量传导至散热垫大面积铝基板自然散热。表面积是笔记本底面积的3倍，被动散热功率可达30W。无需外接电源，适合移动办公场景。", "applicants": '["深圳散热科技有限公司"]', "inventors": '["陈明", "王芳"]', "filing_date": "2023-02-15", "publication_date": "2023-09-20", "patent_number": "CN202310XXXXX12", "ipc_codes": '["G06F1/20", "H05K7/20"]', "relevance_score": 0.60},
    {"title": "LED灯具用微通道液冷散热器", "abstract": "本发明公开了一种LED灯具用微通道液冷散热器。采用铝合金微通道基板（通道宽0.3mm，深1mm），通过自然对流循环冷却液。微通道结构增大换热面积5倍，散热效率比传统翅片散热器提升150%。适用于大功率LED路灯、工矿灯等场景，散热功率50W。", "applicants": '["佛山照明股份有限公司"]', "inventors": '["赵刚", "刘洋"]', "filing_date": "2023-01-10", "publication_date": "2023-08-05", "patent_number": "CN202310XXXXX13", "ipc_codes": '["F21V29/00", "F28D15/00"]', "relevance_score": 0.55},
    {"title": "电动汽车电池包相变材料热管理", "abstract": "本发明涉及一种电动汽车电池包相变材料热管理系统。在电池模组间填充石蜡基相变材料(PCM)，利用相变潜热吸收充放电过程中的热量，将电芯温差控制在5度以内。PCM与导热泡沫复合，增强径向导热。系统无需液冷管路和水泵，降低复杂度和成本。适用于快充场景下电池温度管理。", "applicants": '["宁德时代新能源科技股份有限公司"]', "inventors": '["曾毓群", "吴凯"]', "filing_date": "2023-05-20", "publication_date": "2023-12-10", "patent_number": "CN202310XXXXX14", "ipc_codes": '["H01M10/6556", "H01M10/6568"]', "relevance_score": 0.50},
    {"title": "可穿戴设备微型散热结构", "abstract": "本发明公开了一种可穿戴设备微型散热结构。采用薄膜热管(厚度0.2mm)与柔性石墨片组合，沿表带路径散热。热管蒸发端贴合芯片，冷凝端延伸至表带与皮肤接触区域，利用皮肤作为散热体。散热效率比纯石墨方案提升60%，芯片温度降低4度。结构总重仅5g，不影响佩戴舒适度。", "applicants": '["华为技术有限公司"]', "inventors": '["何刚", "周丽"]', "filing_date": "2023-04-05", "publication_date": "2023-11-18", "patent_number": "CN202310XXXXX15", "ipc_codes": '["G04G21/00", "H05K7/20"]', "relevance_score": 0.48},
    {"title": "一种智能手表散热结构", "abstract": "本发明涉及一种智能手表散热结构，采用钛合金中框作为散热路径，芯片热量通过石墨烯导热膜传导至中框，再通过中框外表面自然辐射散热。中框表面处理采用高辐射率涂层，增强辐射散热效果。配合间歇性降频策略，将芯片温度控制在安全范围内，无需风扇等主动散热器件。", "applicants": '["苹果公司"]', "inventors": '["Jeff Williams", "张明"]', "filing_date": "2023-06-28", "publication_date": "2024-01-05", "patent_number": "CN202310XXXXX16", "ipc_codes": '["G04G21/00", "H01L23/473"]', "relevance_score": 0.45},
    {"title": "数据中心浸没式液冷散热系统", "abstract": "本发明公开了一种数据中心浸没式液冷散热系统。将服务器主板完全浸泡在绝缘冷却液(如氟化液)中，通过液-液或液-气相变直接冷却所有电子元件。散热效率是传统风冷的100倍，PUE值降至1.03以下。冷却液循环系统采用无泵设计，利用自然对流和沸点差驱动循环。", "applicants": '["阿里巴巴集团"]', "inventors": '["施坚松", "刘飞"]', "filing_date": "2023-02-28", "publication_date": "2023-10-20", "patent_number": "CN202310XXXXX17", "ipc_codes": '["G06F1/20", "H05K7/20"]', "relevance_score": 0.42},
    {"title": "一种基于热电效应的温差发电装置", "abstract": "本发明涉及一种基于热电效应的温差发电装置。利用塞贝克效应，通过热电偶材料(如Bi2Te3)将温差直接转换为电能。热端温度100度、冷端25度时，输出功率密度可达5W/cm2。可用于工业废热回收、物联网传感器自供电等场景。", "applicants": '["中国科学院"]', "inventors": '["陈立泉", "黄学杰"]', "filing_date": "2022-11-15", "publication_date": "2023-05-30", "patent_number": "CN202210XXXXX18", "ipc_codes": '["H02N11/00", "H01L35/30"]', "relevance_score": 0.30},
    {"title": "一种建筑外墙隔热涂层材料", "abstract": "本发明公开了一种建筑外墙隔热涂层材料，采用空心玻璃微珠与气凝胶复合制备。涂层厚度2mm，隔热系数0.02W/mK，可将室内温度降低3-5度。具有防火A级、耐候性强、施工方便等优点。适用于绿色建筑和节能改造项目。", "applicants": '["北新建材集团股份有限公司"]', "inventors": '["王兵", "张丽"]', "filing_date": "2023-01-25", "publication_date": "2023-08-15", "patent_number": "CN202310XXXXX19", "ipc_codes": '["C09D5/00", "E04B1/88"]', "relevance_score": 0.20},
    {"title": "一种汽车发动机水冷散热系统", "abstract": "本发明涉及一种汽车发动机水冷散热系统。采用铝制板翅式散热器，配合电动水泵驱动冷却液循环。系统包括节温器、散热风扇和膨胀水箱，工作温度控制在85-95度。散热功率可达50kW，满足2.0T发动机的散热需求。集成智能温控模块，根据工况动态调节风扇转速和水泵流量。", "applicants": '["比亚迪股份有限公司"]', "inventors": '["廉玉波", "罗红斌"]', "filing_date": "2022-09-10", "publication_date": "2023-03-25", "patent_number": "CN202210XXXXX20", "ipc_codes": '["F01P11/00", "F28D15/00"]', "relevance_score": 0.18},
    {"title": "一种光伏板散热优化结构", "abstract": "本发明公开了一种光伏板散热优化结构。在光伏组件背面集成微通道散热器，通过自然对流冷却光伏电池。散热器采用铝合金挤压成型，通道高度5mm。降低光伏电池温度10-15度，提高发电效率3-5%。适用于地面光伏电站和屋顶光伏系统。", "applicants": '["隆基绿能科技股份有限公司"]', "inventors": '["李振国", "王宇"]', "filing_date": "2023-03-15", "publication_date": "2023-10-01", "patent_number": "CN202310XXXXX21", "ipc_codes": '["H02S40/42", "F28D15/00"]', "relevance_score": 0.15},
    {"title": "工业电机散热风扇降噪设计", "abstract": "本发明涉及一种工业电机散热风扇降噪设计。采用仿生猫头鹰翅膀前缘锯齿结构优化风扇叶片形状，在保持同等风量的前提下降低噪音5dB(A)。叶片采用玻纤增强尼龙材料注塑成型，工作转速1500-3000RPM可调。适用于工业电机、变频器等设备的强制风冷散热。", "applicants": '["美的集团股份有限公司"]', "inventors": '["方洪波", "李强"]', "filing_date": "2023-02-10", "publication_date": "2023-09-15", "patent_number": "CN202310XXXXX22", "ipc_codes": '["F04D29/66", "F04D25/06"]', "relevance_score": 0.12},
]


def get_embedder():
    s = model_resolver.get_assigned_settings()
    embed_model = s.get("embedding_model") or ""
    resolved = model_resolver.resolve(embed_model)
    if not resolved:
        print("ERROR: embed model not configured")
        return None
    return Embedder(api_key=resolved.api_key, api_host=resolved.api_host, model=resolved.model_id)


async def setup_knowledge_base():
    print("\n=== Step 1: Enrich Knowledge Base ===")
    db = get_db()
    base_id = "7b94518b-e8d4-4ca3-b9ac-3fd663d4852c"

    db.execute("DELETE FROM knowledge_vectors WHERE base_id=?", (base_id,))
    db.execute("DELETE FROM knowledge_items WHERE base_id=?", (base_id,))
    db.commit()
    print(f"  Cleared old KB data")

    embedder = get_embedder()
    if not embedder:
        return

    for note in KNOWLEDGE_NOTES:
        item_id = str(uuid.uuid4())
        item_data = json.dumps({"title": note["title"], "content": note["content"]}, ensure_ascii=False)
        db.execute(
            "INSERT INTO knowledge_items (id, base_id, type, data, status) VALUES (?, ?, 'note', ?, 'completed')",
            (item_id, base_id, item_data)
        )
        db.commit()

        text = note["content"]
        chunk_size = 512
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

        for idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            try:
                vectors = await embedder.embed([chunk])
                if vectors and vectors[0]:
                    vec = vectors[0]
                    db.execute(
                        "INSERT INTO knowledge_vectors (user_id, base_id, item_id, chunk_index, text, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                        (6, base_id, item_id, idx, chunk, json.dumps(vec))
                    )
            except Exception as e:
                print(f"  Embed fail [{note['title']}] chunk {idx}: {e}")

        db.commit()
        print(f"  + {note['title']} ({len(chunks)} chunks)")

    db.close()
    print(f"  KB enriched: {len(KNOWLEDGE_NOTES)} TRIZ documents")


async def setup_patents():
    print("\n=== Step 2: Add Patents ===")
    db = get_db()

    db.execute("DELETE FROM patent_vectors")
    db.execute("DELETE FROM patents")
    db.commit()
    print("  Cleared old patents")

    for p in PATENTS:
        db.execute(
            """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
               publication_date, patent_number, ipc_codes, relevance_score, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["title"], p["abstract"], p["applicants"], p["inventors"],
             p["filing_date"], p["publication_date"], p["patent_number"],
             p["ipc_codes"], p["relevance_score"], p["abstract"])
        )
    db.commit()
    print(f"  Inserted {len(PATENTS)} patents")

    embedder = get_embedder()
    if not embedder:
        db.close()
        return

    rows = db.execute("SELECT id, title, abstract FROM patents").fetchall()
    db.close()

    count = 0
    for row in rows:
        try:
            text = f"{row['title']}。{row['abstract']}"
            vector = await embedder.embed([text])
            if vector and vector[0]:
                vec = vector[0][:4000]
                db2 = get_db()
                db2.execute(
                    """INSERT INTO patent_vectors (patent_id, embedding, updated_at)
                       VALUES (?, ?, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                       ON CONFLICT (patent_id)
                       DO UPDATE SET embedding=excluded.embedding, updated_at=excluded.updated_at""",
                    (row["id"], json.dumps(vec))
                )
                db2.commit()
                db2.close()
                count += 1
                print(f"  [{count}/{len(rows)}] {row['title'][:40]}...")
        except Exception as e:
            print(f"  FAIL {row['title'][:30]}: {e}")

    print(f"  Patent vectors: {count}/{len(rows)}")


async def main():
    print("=" * 60)
    print("  InnovOS Test Data Setup")
    print("=" * 60)
    await setup_knowledge_base()
    await setup_patents()
    print("\nDone! Data ready for workflow test.")


if __name__ == "__main__":
    asyncio.run(main())
