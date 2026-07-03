"""
Mock 种子数据 — 手机发热主题
专利 30+ 条 / 知识笔记 10+ 条 / 历史方案 5-6 个

启动时幂等执行：已存在则跳过。
"""

import json
import logging

from app.database import get_db

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  专利数据（30+ 条，手机发热主题）
# ══════════════════════════════════════════════════════════

MOCK_PATENTS = [
    {
        "title": "一种智能手机石墨烯散热结构",
        "abstract": "本发明涉及手机散热技术领域，公开一种智能手机石墨烯散热结构，包括石墨烯导热层和石墨烯散热膜，通过石墨烯的高导热系数实现快速均温散热，有效降低手机局部热点温度。",
        "applicants": ["华为技术有限公司"],
        "inventors": ["张明", "李华"],
        "filing_date": "2023-03-15",
        "publication_date": "2023-09-20",
        "patent_number": "CN115672345A",
        "ipc_codes": ["H01M10/6533", "H05K7/20"],
        "relevance_score": 96,
        "claims": "1.一种智能手机石墨烯散热结构，其特征在于包括石墨烯导热层...",
        "description": "详细描述石墨烯散热结构的层叠设计、制备工艺及散热性能测试结果。",
    },
    {
        "title": "手机均热板VC散热装置",
        "abstract": "本发明公开一种手机均热板VC散热装置，利用真空腔体内工质相变实现高效热量传递，散热功率较传统石墨片提升3倍以上。",
        "applicants": ["OPPO广东移动通信有限公司"],
        "inventors": ["王强", "刘伟"],
        "filing_date": "2023-01-20",
        "publication_date": "2023-07-15",
        "patent_number": "CN115432189A",
        "ipc_codes": ["H05K7/20", "H01M10/625"],
        "relevance_score": 94,
        "claims": "1.一种手机均热板VC散热装置，其特征在于包括真空腔体、毛细吸液芯...",
        "description": "描述VC均热板的结构设计、毛细吸液芯材料选择及充液率优化。",
    },
    {
        "title": "基于相变材料的手机热管理系统",
        "abstract": "本发明涉及手机热管理技术，采用石蜡基相变材料作为储热介质，在手机发热峰值时吸收潜热，延缓温度上升速率。",
        "applicants": ["小米通讯技术有限公司"],
        "inventors": ["陈晓", "赵磊"],
        "filing_date": "2023-05-10",
        "publication_date": "2023-11-25",
        "patent_number": "CN115890123A",
        "ipc_codes": ["H05K7/20", "H01M10/6586"],
        "relevance_score": 92,
        "claims": "1.一种基于相变材料的手机热管理系统，其特征在于包括相变储热层...",
        "description": "详细描述相变材料的封装结构、导热增强填料及热响应特性。",
    },
    {
        "title": "手机芯片液冷散热模组",
        "abstract": "本发明公开一种手机芯片液冷散热模组，采用微通道液冷板配合微型泵驱动冷却液循环，实现芯片定点高效散热。",
        "applicants": ["维沃移动通信有限公司"],
        "inventors": ["孙杰", "周涛"],
        "filing_date": "2023-02-18",
        "publication_date": "2023-08-30",
        "patent_number": "CN115567890A",
        "ipc_codes": ["H05K7/20", "H01L23/427"],
        "relevance_score": 90,
        "claims": "1.一种手机芯片液冷散热模组，其特征在于包括微通道散热板...",
        "description": "描述微通道液冷板的结构、流道设计及泵驱动控制策略。",
    },
    {
        "title": "智能手机多级散热架构",
        "abstract": "本发明涉及手机多级散热架构，通过导热硅脂、石墨片、VC均热板三级串联，实现从芯片到外壳的高效热传导路径。",
        "applicants": ["荣耀终端有限公司"],
        "inventors": ["吴敏", "郑华"],
        "filing_date": "2023-04-05",
        "publication_date": "2023-10-18",
        "patent_number": "CN115789012A",
        "ipc_codes": ["H05K7/20"],
        "relevance_score": 89,
        "claims": "1.一种智能手机多级散热架构，其特征在于包括三级导热层...",
        "description": "描述三级散热架构的层间界面热阻优化及温度梯度控制。",
    },
    {
        "title": "手机AI智能温控方法及系统",
        "abstract": "本发明公开一种手机AI智能温控方法，通过机器学习预测芯片发热趋势，动态调节CPU频率和屏幕亮度以降低发热。",
        "applicants": ["华为技术有限公司"],
        "inventors": ["黄涛", "林峰"],
        "filing_date": "2023-06-12",
        "publication_date": "2023-12-20",
        "patent_number": "CN115901234A",
        "ipc_codes": ["H05K7/20", "G06N20/00"],
        "relevance_score": 88,
        "claims": "1.一种手机AI智能温控方法，其特征在于包括温度预测模型...",
        "description": "描述基于LSTM的温度预测模型训练及动态调频策略。",
    },
    {
        "title": "手机石墨片导热结构",
        "abstract": "本发明涉及手机石墨散热技术，采用高定向热解石墨片，导热系数达1500W/mK，实现大面积均温散热。",
        "applicants": ["三星电子株式会社"],
        "inventors": ["Kim Sanghoon", "Lee Minho"],
        "filing_date": "2023-02-28",
        "publication_date": "2023-08-15",
        "patent_number": "CN115456789A",
        "ipc_codes": ["H05K7/20", "C01B32/00"],
        "relevance_score": 87,
        "claims": "1.一种手机石墨片导热结构，其特征在于包括高定向热解石墨层...",
        "description": "描述石墨片的制备工艺、厚度优化及贴合方式。",
    },
    {
        "title": "手机散热风冷结构",
        "abstract": "本发明公开一种手机散热风冷结构，利用手机内部空气对流通道，配合微型风扇实现主动风冷散热。",
        "applicants": ["联想创新有限公司"],
        "inventors": ["胡军", "郭明"],
        "filing_date": "2023-03-22",
        "publication_date": "2023-09-28",
        "patent_number": "CN115678901A",
        "ipc_codes": ["H05K7/20", "F28D9/00"],
        "relevance_score": 85,
        "claims": "1.一种手机散热风冷结构，其特征在于包括内部对流通道...",
        "description": "描述风冷通道设计、微型风扇布局及气流组织优化。",
    },
    {
        "title": "手机电池热管理装置",
        "abstract": "本发明涉及手机电池热管理，采用导热凝胶包裹电池，配合温度传感器实现电池过热保护和寿命延长。",
        "applicants": ["宁德时代新能源科技股份有限公司"],
        "inventors": ["曾毓群", "李晨"],
        "filing_date": "2023-04-18",
        "publication_date": "2023-10-30",
        "patent_number": "CN115812345A",
        "ipc_codes": ["H01M10/6533", "H01M10/625"],
        "relevance_score": 84,
        "claims": "1.一种手机电池热管理装置，其特征在于包括导热凝胶层...",
        "description": "描述导热凝胶配方、电池包覆工艺及热失控防护策略。",
    },
    {
        "title": "手机柔性屏散热背板",
        "abstract": "本发明公开一种手机柔性屏散热背板，采用超薄石墨烯-铜箔复合散热层，兼顾柔性与高导热。",
        "applicants": ["京东方科技集团股份有限公司"],
        "inventors": ["徐明", "高伟"],
        "filing_date": "2023-05-25",
        "publication_date": "2023-11-30",
        "patent_number": "CN115923456A",
        "ipc_codes": ["H05K7/20", "H01L23/367"],
        "relevance_score": 83,
        "claims": "1.一种手机柔性屏散热背板，其特征在于包括石墨烯-铜箔复合层...",
        "description": "描述复合散热层的层叠结构、柔性测试及导热性能。",
    },
    {
        "title": "手机游戏场景智能散热方法",
        "abstract": "本发明涉及手机游戏场景散热，根据游戏负载动态调节散热策略，结合帧率与温度协同控制。",
        "applicants": ["腾讯科技（深圳）有限公司"],
        "inventors": ["马化腾", "张志东"],
        "filing_date": "2023-07-08",
        "publication_date": "2024-01-15",
        "patent_number": "CN116012345A",
        "ipc_codes": ["H05K7/20", "G06F9/50"],
        "relevance_score": 82,
        "claims": "1.一种手机游戏场景智能散热方法，其特征在于包括负载预测模块...",
        "description": "描述游戏场景识别、负载预测及散热策略动态切换。",
    },
    {
        "title": "手机超薄VC均热板制备方法",
        "abstract": "本发明公开一种手机超薄VC均热板制备方法，厚度仅0.3mm，通过蚀刻工艺形成微毛细结构。",
        "applicants": ["瑞声科技控股有限公司"],
        "inventors": ["潘政民", "吴春媛"],
        "filing_date": "2023-01-15",
        "publication_date": "2023-07-08",
        "patent_number": "CN115423456A",
        "ipc_codes": ["H05K7/20", "B23K26/00"],
        "relevance_score": 81,
        "claims": "1.一种手机超薄VC均热板制备方法，其特征在于包括蚀刻毛细结构步骤...",
        "description": "描述超薄VC的蚀刻工艺、毛细结构设计及性能测试。",
    },
    {
        "title": "手机散热石墨烯涂层",
        "abstract": "本发明涉及手机散热涂层技术，在手机内壳表面涂覆石墨烯散热涂层，实现大面积辐射散热。",
        "applicants": ["比亚迪股份有限公司"],
        "inventors": ["王传福", "廉玉波"],
        "filing_date": "2023-06-20",
        "publication_date": "2023-12-28",
        "patent_number": "CN115934567A",
        "ipc_codes": ["H05K7/20", "C09D5/00"],
        "relevance_score": 80,
        "claims": "1.一种手机散热石墨烯涂层，其特征在于包括石墨烯分散液...",
        "description": "描述石墨烯涂层的配方、涂覆工艺及辐射散热系数测试。",
    },
    {
        "title": "手机热管散热模组",
        "abstract": "本发明公开一种手机热管散热模组，采用扁平热管将芯片热量快速传导至手机中框，实现远端散热。",
        "applicants": ["东莞华贝电子科技有限公司"],
        "inventors": ["陈明", "杨光"],
        "filing_date": "2023-03-08",
        "publication_date": "2023-09-15",
        "patent_number": "CN115645678A",
        "ipc_codes": ["H05K7/20", "H01L23/427"],
        "relevance_score": 79,
        "claims": "1.一种手机热管散热模组，其特征在于包括扁平热管...",
        "description": "描述扁平热管的结构、工质选择及弯曲性能测试。",
    },
    {
        "title": "手机多热源协同散热系统",
        "abstract": "本发明涉及手机多热源散热，针对CPU、GPU、电池、充电IC多热源设计协同散热路径。",
        "applicants": ["中兴通讯股份有限公司"],
        "inventors": ["李自学", "王喜瑜"],
        "filing_date": "2023-08-12",
        "publication_date": "2024-02-15",
        "patent_number": "CN116023456A",
        "ipc_codes": ["H05K7/20"],
        "relevance_score": 78,
        "claims": "1.一种手机多热源协同散热系统，其特征在于包括多热源温度采集...",
        "description": "描述多热源温度采集、热流分配算法及协同控制策略。",
    },
    {
        "title": "手机充电散热一体化结构",
        "abstract": "本发明公开一种手机充电散热一体化结构，在快充时启动辅助散热，降低充电发热。",
        "applicants": ["OPPO广东移动通信有限公司"],
        "inventors": ["刘作虎", "沈义人"],
        "filing_date": "2023-04-22",
        "publication_date": "2023-10-25",
        "patent_number": "CN115745678A",
        "ipc_codes": ["H05K7/20", "H02J7/00"],
        "relevance_score": 77,
        "claims": "1.一种手机充电散热一体化结构，其特征在于包括充电散热联动...",
        "description": "描述充电散热联动控制、快充温升抑制及安全保护。",
    },
    {
        "title": "手机散热仿真优化方法",
        "abstract": "本发明涉及手机散热仿真技术，通过CFD仿真优化手机内部散热结构设计，减少热阻。",
        "applicants": ["北京字节跳动网络技术有限公司"],
        "inventors": ["梁汝波", "张利东"],
        "filing_date": "2023-09-15",
        "publication_date": "2024-03-20",
        "patent_number": "CN116034567A",
        "ipc_codes": ["H05K7/20", "G06F30/15"],
        "relevance_score": 76,
        "claims": "1.一种手机散热仿真优化方法，其特征在于包括CFD建模步骤...",
        "description": "描述CFD仿真建模、热阻分析及结构优化迭代。",
    },
    {
        "title": "手机导热凝胶组合物",
        "abstract": "本发明公开一种手机导热凝胶组合物，导热系数达8W/mK，用于芯片与散热片之间界面导热。",
        "applicants": ["深圳新宙邦科技股份有限公司"],
        "inventors": ["覃九三", "邓先红"],
        "filing_date": "2023-02-10",
        "publication_date": "2023-08-05",
        "patent_number": "CN115434567A",
        "ipc_codes": ["H05K7/20", "C08L83/04"],
        "relevance_score": 75,
        "claims": "1.一种手机导热凝胶组合物，其特征在于包括硅橡胶基体...",
        "description": "描述导热凝胶配方、氧化铝填料改性及界面热阻测试。",
    },
    {
        "title": "手机外壳辐射散热涂层",
        "abstract": "本发明涉及手机外壳散热，在外壳表面涂覆高发射率红外辐射涂层，提升辐射散热效率。",
        "applicants": ["富士康科技集团有限公司"],
        "inventors": ["郭台铭", "戴正吴"],
        "filing_date": "2023-05-18",
        "publication_date": "2023-11-20",
        "patent_number": "CN115845678A",
        "ipc_codes": ["H05K7/20", "C09D5/33"],
        "relevance_score": 74,
        "claims": "1.一种手机外壳辐射散热涂层，其特征在于包括高发射率填料...",
        "description": "描述辐射散热涂层的配方、发射率测试及耐久性评估。",
    },
    {
        "title": "手机散热翅片结构",
        "abstract": "本发明公开一种手机散热翅片结构，在手机中框集成微型散热翅片，增加散热面积。",
        "applicants": ["闻泰科技股份有限公司"],
        "inventors": ["张学政", "肖学礼"],
        "filing_date": "2023-07-22",
        "publication_date": "2024-01-28",
        "patent_number": "CN116045678A",
        "ipc_codes": ["H05K7/20", "F28F3/02"],
        "relevance_score": 73,
        "claims": "1.一种手机散热翅片结构，其特征在于包括微型翅片阵列...",
        "description": "描述微型翅片的几何设计、加工工艺及散热性能提升。",
    },
    {
        "title": "手机热分区管理方法",
        "abstract": "本发明涉及手机热分区管理，将手机内部分为多个热区，独立采集温度并分区控制散热。",
        "applicants": ["魅族科技有限公司"],
        "inventors": ["黄章", "白永祥"],
        "filing_date": "2023-03-28",
        "publication_date": "2023-10-05",
        "patent_number": "CN115656789A",
        "ipc_codes": ["H05K7/20", "G06F1/20"],
        "relevance_score": 72,
        "claims": "1.一种手机热分区管理方法，其特征在于包括热区划分...",
        "description": "描述热区划分策略、分区温度采集及独立散热控制。",
    },
    {
        "title": "手机石墨烯-碳纳米管复合散热膜",
        "abstract": "本发明公开一种手机石墨烯-碳纳米管复合散热膜，结合石墨烯面内导热和碳纳米管轴向导热优势。",
        "applicants": ["深圳烯旺先进材料技术有限公司"],
        "inventors": ["冯冠平", "李俊江"],
        "filing_date": "2023-04-15",
        "publication_date": "2023-10-22",
        "patent_number": "CN115756789A",
        "ipc_codes": ["H05K7/20", "C01B32/00"],
        "relevance_score": 71,
        "claims": "1.一种手机石墨烯-碳纳米管复合散热膜，其特征在于包括复合层...",
        "description": "描述复合散热膜的制备、界面结合及各向异性导热测试。",
    },
    {
        "title": "手机散热自适应控制方法",
        "abstract": "本发明涉及手机散热自适应控制，根据环境温度和使用场景动态调整散热策略。",
        "applicants": ["努比亚技术有限公司"],
        "inventors": ["里强", "倪飞"],
        "filing_date": "2023-08-28",
        "publication_date": "2024-02-28",
        "patent_number": "CN116056789A",
        "ipc_codes": ["H05K7/20", "G06F1/20"],
        "relevance_score": 70,
        "claims": "1.一种手机散热自适应控制方法，其特征在于包括场景识别...",
        "description": "描述场景识别、环境温度补偿及散热策略自适应切换。",
    },
    {
        "title": "手机3D均热板结构",
        "abstract": "本发明公开一种手机3D均热板结构，采用立体腔体设计，实现多面散热和折叠屏适配。",
        "applicants": ["柔宇科技股份有限公司"],
        "inventors": ["刘自鸿", "余晓军"],
        "filing_date": "2023-06-08",
        "publication_date": "2023-12-15",
        "patent_number": "CN115967890A",
        "ipc_codes": ["H05K7/20", "H01L23/427"],
        "relevance_score": 69,
        "claims": "1.一种手机3D均热板结构，其特征在于包括立体腔体...",
        "description": "描述3D均热板的立体腔体设计、折叠适配及散热性能。",
    },
    {
        "title": "手机散热微胶囊相变材料",
        "abstract": "本发明涉及手机散热相变材料，采用微胶囊封装石蜡，实现相变材料的稳定性和可加工性。",
        "applicants": ["中国科学技术大学"],
        "inventors": ["陈初升", "陈春华"],
        "filing_date": "2023-01-08",
        "publication_date": "2023-07-05",
        "patent_number": "CN115412345A",
        "ipc_codes": ["H05K7/20", "C09K5/02"],
        "relevance_score": 68,
        "claims": "1.一种手机散热微胶囊相变材料，其特征在于包括微胶囊壁材...",
        "description": "描述微胶囊制备、壁材选择及相变储热性能测试。",
    },
    {
        "title": "手机热感应变色警示结构",
        "abstract": "本发明公开一种手机热感应变色警示结构，在手机外壳集成热敏变色材料，直观显示发热区域。",
        "applicants": ["深圳传音控股股份有限公司"],
        "inventors": ["竺兆江", "阿里夫"],
        "filing_date": "2023-09-22",
        "publication_date": "2024-03-15",
        "patent_number": "CN116067890A",
        "ipc_codes": ["H05K7/20", "C09K9/02"],
        "relevance_score": 67,
        "claims": "1.一种手机热感应变色警示结构，其特征在于包括热敏变色层...",
        "description": "描述热敏变色材料选择、变色阈值设计及警示显示方案。",
    },
    {
        "title": "手机散热石墨片贴合工艺",
        "abstract": "本发明涉及手机石墨片贴合工艺，采用自动化贴合设备实现石墨片高精度无气泡贴合。",
        "applicants": ["伯恩光学（惠州）有限公司"],
        "inventors": ["杨建文", "吴明"],
        "filing_date": "2023-02-25",
        "publication_date": "2023-08-20",
        "patent_number": "CN115445678A",
        "ipc_codes": ["H05K7/20", "B32B37/00"],
        "relevance_score": 66,
        "claims": "1.一种手机散热石墨片贴合工艺，其特征在于包括预定位步骤...",
        "description": "描述贴合工艺流程、气泡消除及贴合精度控制。",
    },
    {
        "title": "手机液冷+风冷混合散热系统",
        "abstract": "本发明公开一种手机液冷+风冷混合散热系统，结合液冷高导热和风冷主动散热优势。",
        "applicants": ["黑鲨科技有限公司"],
        "inventors": ["吴世敏", "罗语周"],
        "filing_date": "2023-05-05",
        "publication_date": "2023-11-10",
        "patent_number": "CN115856789A",
        "ipc_codes": ["H05K7/20", "H01L23/427"],
        "relevance_score": 65,
        "claims": "1.一种手机液冷+风冷混合散热系统，其特征在于包括液冷回路...",
        "description": "描述混合散热系统的液冷回路设计、风扇布局及协同控制。",
    },
    {
        "title": "手机散热性能测试方法",
        "abstract": "本发明涉及手机散热性能测试，采用红外热像仪和多点温度传感器组合测试方案。",
        "applicants": ["中国信息通信研究院"],
        "inventors": ["王志勤", "何宝宏"],
        "filing_date": "2023-10-12",
        "publication_date": "2024-04-15",
        "patent_number": "CN116078901A",
        "ipc_codes": ["H05K7/20", "G01K13/00"],
        "relevance_score": 64,
        "claims": "1.一种手机散热性能测试方法，其特征在于包括红外热像采集...",
        "description": "描述测试方案设计、温度采集点布置及散热性能评估指标。",
    },
    {
        "title": "手机散热均温板表面处理方法",
        "abstract": "本发明公开一种手机散热均温板表面处理方法，通过亲水涂层提升毛细吸液芯的毛细力。",
        "applicants": ["双鸿科技股份有限公司"],
        "inventors": ["蔡文斌", "林建宏"],
        "filing_date": "2023-03-15",
        "publication_date": "2023-09-22",
        "patent_number": "CN115667890A",
        "ipc_codes": ["H05K7/20", "C23C14/00"],
        "relevance_score": 63,
        "claims": "1.一种手机散热均温板表面处理方法，其特征在于包括亲水涂层沉积...",
        "description": "描述亲水涂层材料、沉积工艺及毛细力提升效果。",
    },
    {
        "title": "手机折叠屏散热铰链结构",
        "abstract": "本发明涉及折叠屏手机散热，在铰链处集成柔性导热件，实现展开和折叠状态下的持续散热。",
        "applicants": ["三星电子株式会社"],
        "inventors": ["Park Jihyun", "Choi Donghoon"],
        "filing_date": "2023-07-15",
        "publication_date": "2024-01-20",
        "patent_number": "CN116089012A",
        "ipc_codes": ["H05K7/20", "H04M1/02"],
        "relevance_score": 62,
        "claims": "1.一种手机折叠屏散热铰链结构，其特征在于包括柔性导热件...",
        "description": "描述柔性导热件设计、铰链集成及折叠耐久测试。",
    },
    {
        "title": "手机散热AI预测温控算法",
        "abstract": "本发明公开一种手机散热AI预测温控算法，基于使用习惯和环境数据预测未来温度趋势，提前调节散热。",
        "applicants": ["高通股份有限公司"],
        "inventors": ["Cristiano Amon", "Alex Katouzian"],
        "filing_date": "2023-11-08",
        "publication_date": "2024-05-10",
        "patent_number": "CN116090123A",
        "ipc_codes": ["H05K7/20", "G06N20/00"],
        "relevance_score": 61,
        "claims": "1.一种手机散热AI预测温控算法，其特征在于包括温度趋势预测模型...",
        "description": "描述预测模型训练、特征工程及提前散热调节策略。",
    },
    {
        "title": "手机散热超薄热管阵列",
        "abstract": "本发明涉及手机超薄热管阵列，多根微型热管并联布置，实现大面积高效均温。",
        "applicants": ["奇鋐科技股份有限公司"],
        "inventors": ["沈庆洲", "黄俊雄"],
        "filing_date": "2023-04-28",
        "publication_date": "2023-11-05",
        "patent_number": "CN115778901A",
        "ipc_codes": ["H05K7/20", "H01L23/427"],
        "relevance_score": 60,
        "claims": "1.一种手机散热超薄热管阵列，其特征在于包括多根微型热管...",
        "description": "描述热管阵列布局、并联设计及均温性能测试。",
    },
]


# ══════════════════════════════════════════════════════════
#  知识笔记（10+ 条，手机发热解决笔记）
# ══════════════════════════════════════════════════════════

MOCK_NOTES = [
    {
        "title": "石墨烯散热膜在手机中的应用",
        "content": "石墨烯散热膜利用石墨烯超高面内导热系数（~5000 W/mK）实现快速均温。实际应用中，厚度通常为25-50μm，需配合导热凝胶贴合在芯片表面。测试表明，石墨烯膜可使手机热点温度降低3-5°C。关键工艺挑战在于石墨烯薄膜的大面积转移和无缺陷贴合。",
        "tags": ["石墨烯", "散热膜", "导热"],
    },
    {
        "title": "VC均热板工作原理与设计要点",
        "content": "VC均热板利用真空腔体内工质（通常为纯水）的相变循环实现高效散热：蒸发段吸热汽化 → 蒸汽流向冷凝段 → 冷凝放热 → 凝液经毛细吸液芯回流。散热功率可达石墨片的3-5倍。设计要点：毛细吸液芯的毛细力需大于工质回流阻力；充液率通常为20-30%；超薄VC厚度可做到0.3mm。",
        "tags": ["VC均热板", "相变散热", "毛细结构"],
    },
    {
        "title": "手机发热问题根因分析",
        "content": "手机发热主要热源：1) SoC芯片（CPU/GPU高负载，游戏/视频场景）；2) 快充充电（大电流产生焦耳热）；3) 电池内阻发热（老化电池内阻增大）；4) 射频PA（5G高功率发射）；5) 屏幕背光（高亮度持续工作）。发热会导致降频卡顿、电池老化加速、用户烫手感不适。核心矛盾：性能需求 vs 散热空间受限。",
        "tags": ["发热根因", "热源分析", "性能矛盾"],
    },
    {
        "title": "相变储热材料在手机散热中的应用",
        "content": "相变材料（PCM）通过固-液相变吸收潜热，延缓温度上升。手机中常用石蜡基PCM，相变温度40-45°C，潜热约200J/g。优势：无需能耗、无噪音、可填充于狭小空间。局限：储热容量有限（仅延缓非消除）、导热系数低（需添加石墨/金属填料增强）、封装需防泄漏。微胶囊化可提升可加工性。",
        "tags": ["相变材料", "储热", "石蜡"],
    },
    {
        "title": "手机热设计功率（TDP）评估方法",
        "content": "手机热设计需评估各场景TDP：待机0.5-1W、日常使用2-4W、游戏5-8W、快充充电6-10W。散热能力需覆盖最恶劣场景。评估方法：1) 红外热像仪测绘温度分布；2) 多点热电偶采集关键点温度；3) CFD仿真模拟热流路径。关键指标：热点温度（≤45°C触感舒适）、温度均匀性（温差≤5°C）、降频阈值余量。",
        "tags": ["TDP", "热设计", "评估方法"],
    },
    {
        "title": "导热界面材料（TIM）选型指南",
        "content": "芯片与散热片之间的界面热阻是散热瓶颈。常用TIM：1) 导热硅脂（导热系数1-3 W/mK，易干涸）；2) 导热凝胶（3-8 W/mK，长效稳定）；3) 导热垫（1-6 W/mK，易装配）；4) 液态金属（20-80 W/mK，需防腐蚀封装）。选型需平衡导热系数、界面热阻、长期稳定性、装配工艺和成本。手机中多用导热凝胶兼顾性能与可靠性。",
        "tags": ["TIM", "界面热阻", "导热材料"],
    },
    {
        "title": "手机AI温控策略优化",
        "content": "传统温控基于阈值反馈（温度超限→降频），存在滞后性。AI温控通过机器学习预测温度趋势，提前调节：1) 采集CPU/GPU负载、环境温度、历史温度时序；2) LSTM/Transformer模型预测未来5-10秒温度；3) 预测超限则提前降频/降亮度。优势：减少温度峰值、降低降频次数、提升用户体验。挑战：模型轻量化、在线推理延迟、个性化适配。",
        "tags": ["AI温控", "预测调频", "机器学习"],
    },
    {
        "title": "手机散热结构集成度演进",
        "content": "手机散热结构演进：1) 第一代：导热硅脂+石墨片（被动散热，覆盖日常）；2) 第二代：VC均热板（相变散热，覆盖游戏场景）；3) 第三代：VC+石墨烯+相变材料复合（多机制协同）；4) 第四代：液冷+风冷+AI主动散热（游戏手机）。趋势：从被动到主动、从单点到全域、从硬件到软硬协同。",
        "tags": ["散热演进", "集成度", "技术趋势"],
    },
    {
        "title": "5G手机发热挑战与对策",
        "content": "5G手机发热较4G更严重：1) 毫米波PA功耗高（发射功率大）；2) 天线数量多（MIMO）；3) 基带处理复杂（高频段信号处理）；4) 高速数据传输（GPU/内存负载）。对策：1) PA近端独立散热；2) 天线隔离避免热耦合；3) 动态调制（信号弱时降速降功耗）；4) 智能切换4G/5G（非高速场景用4G）。",
        "tags": ["5G", "功耗", "PA散热"],
    },
    {
        "title": "手机快充发热抑制技术",
        "content": "快充发热主要来自充电IC和电池内阻。抑制技术：1) 电荷泵技术（降压比固定，效率达97%+，减少IC发热）；2) 分流充电（双电芯串联充电并联放电，降低单芯电流）；3) 隔离式充电（充电IC外置充电头，手机端仅接收低压）；4) 动态功率调节（温度升高时降低充电功率）；5) 充电散热联动（快充时启动辅助散热）。",
        "tags": ["快充", "电荷泵", "充电发热"],
    },
    {
        "title": "手机散热CFD仿真建模要点",
        "content": "CFD仿真用于手机热设计优化。建模要点：1) 几何简化（保留关键散热路径，忽略小特征）；2) 材料属性（各向异性导热，如石墨片面内vs面外导热差异大）；3) 边界条件（自然对流5-25 W/m²K、辐射ε=0.9、手持热阻）；4) 网格（芯片区加密，y+适配湍流模型）；5) 求解（稳态+瞬态结合）。验证：与红外热像仪实测对比，误差<2°C。",
        "tags": ["CFD", "仿真", "热设计"],
    },
    {
        "title": "手机散热材料导热系数对比",
        "content": "常用散热材料导热系数（W/mK）：铜（400）、铝（237）、石墨烯面内（3000-5000）、高定向热解石墨（1500-2000）、普通石墨片（400-1500）、导热凝胶（3-8）、导热硅脂（1-3）、相变材料（0.2-0.5，需增强）。选型需综合考虑导热、厚度、柔性、成本、可加工性。手机中石墨片性价比最高，VC性能最优，石墨烯为前沿方向。",
        "tags": ["导热系数", "材料对比", "选型"],
    },
]


# ══════════════════════════════════════════════════════════
#  历史方案（5-6 个，工程方案问题）
# ══════════════════════════════════════════════════════════

MOCK_HISTORY_TASKS = [
    {
        "title": "手机发热问题综合解决方案",
        "description": "针对智能手机在高负载场景（游戏、快充、5G）下的发热问题，设计多级协同散热方案，降低热点温度并提升用户体验。",
        "solutions": [
            {
                "title": "石墨烯-VC复合多级散热方案",
                "description": "采用石墨烯导热层（芯片界面）+ VC均热板（中段均温）+ 石墨片（外壳均温）三级串联散热架构。芯片热量经导热凝胶传至石墨烯层快速扩散，VC均热板通过相变将热量传导至大面积冷凝区，最终由石墨片均匀分布至手机外壳。实测热点温度降低6-8°C，温差控制在3°C以内。",
                "principles": ["分割原理", "局部质量原理", "多孔材料原理"],
                "confidence_score": 92,
                "patent_references": ["一种智能手机石墨烯散热结构", "手机均热板VC散热装置"],
                "rating": 5,
                "evaluation": {"可行性": 90, "创新性": 85, "成本": 75, "转化价值": 88},
            },
            {
                "title": "AI预测+相变储热智能温控方案",
                "description": "结合AI温度预测模型和相变储热材料，实现主动+被动协同温控。AI模型基于CPU/GPU负载、环境温度预测未来10秒温度趋势，提前降频；相变材料（石蜡基，相变温度42°C）在发热峰值吸收潜热，延缓温度上升。双重机制使温度峰值降低4-5°C，降频次数减少60%。",
                "principles": ["动态性原理", "相变原理", "预先作用原理"],
                "confidence_score": 88,
                "patent_references": ["手机AI智能温控方法及系统", "基于相变材料的手机热管理系统"],
                "rating": 4,
                "evaluation": {"可行性": 82, "创新性": 90, "成本": 70, "转化价值": 85},
            },
            {
                "title": "液冷+风冷混合主动散热方案",
                "description": "针对游戏手机场景，设计液冷+风冷混合散热系统。微通道液冷板覆盖SoC和充电IC，微型泵驱动冷却液循环；手机内部对流通道配合微型风扇实现主动风冷。液冷负责高功率热源定点散热，风冷负责全域均温。散热功率达15W，支持满载游戏2小时无降频。",
                "principles": ["复合材料原理", "分割原理", "动态性原理"],
                "confidence_score": 85,
                "patent_references": ["手机芯片液冷散热模组", "手机液冷+风冷混合散热系统"],
                "rating": 4,
                "evaluation": {"可行性": 78, "创新性": 88, "成本": 65, "转化价值": 80},
            },
        ],
    },
    {
        "title": "5G手机射频前端发热优化方案",
        "description": "5G毫米波PA功耗高导致射频前端发热严重，设计PA近端独立散热与动态功率调节方案。",
        "solutions": [
            {
                "title": "PA近端独立散热+动态功率调节方案",
                "description": "为5G PA设计独立散热岛，采用超薄热管将PA热量传导至手机中框远端散热；配合动态功率控制，信号弱时降低PA输出功率减少发热。实测PA区域温度降低5°C，5G续航提升12%。",
                "principles": ["分割原理", "动态性原理", "预先作用原理"],
                "confidence_score": 86,
                "patent_references": ["手机热管散热模组", "手机散热自适应控制方法"],
                "rating": 4,
                "evaluation": {"可行性": 85, "创新性": 80, "成本": 78, "转化价值": 82},
            },
        ],
    },
    {
        "title": "手机快充发热抑制方案",
        "description": "快充场景充电IC和电池发热严重，设计电荷泵+分流充电+散热联动方案。",
        "solutions": [
            {
                "title": "电荷泵+双电芯分流+散热联动快充方案",
                "description": "采用电荷泵技术将充电效率提升至97%以上，减少IC发热；双电芯串联充电并联放电降低单芯电流；快充时启动VC均热板辅助散热。综合方案使充电温升降低8°C，100W快充全程温度<42°C。",
                "principles": ["分割原理", "局部质量原理", "动态性原理"],
                "confidence_score": 89,
                "patent_references": ["手机充电散热一体化结构", "手机电池热管理装置"],
                "rating": 5,
                "evaluation": {"可行性": 88, "创新性": 82, "成本": 72, "转化价值": 90},
            },
        ],
    },
    {
        "title": "折叠屏手机散热结构设计",
        "description": "折叠屏手机铰链区域散热路径中断，设计柔性导热件实现展开/折叠状态持续散热。",
        "solutions": [
            {
                "title": "铰链集成柔性石墨烯导热件方案",
                "description": "在折叠铰链处集成柔性石墨烯-聚酰亚胺复合导热件，展开时导热件平直导热，折叠时导热件弯曲保持热路连通。配合3D均热板实现多面散热。实测展开/折叠状态热点温差<2°C，折叠耐久>30万次。",
                "principles": ["柔性壳体原理", "分割原理", "复合材料原理"],
                "confidence_score": 84,
                "patent_references": ["手机折叠屏散热铰链结构", "手机3D均热板结构"],
                "rating": 4,
                "evaluation": {"可行性": 80, "创新性": 88, "成本": 70, "转化价值": 85},
            },
        ],
    },
    {
        "title": "手机多热源协同热管理方案",
        "description": "手机内SoC、GPU、电池、充电IC、PA多热源相互热耦合，设计热分区独立管理与协同散热方案。",
        "solutions": [
            {
                "title": "热分区隔离+协同调度多热源管理方案",
                "description": "将手机内部分为5个热区（SoC区、GPU区、电池区、充电IC区、PA区），各区独立温度采集与散热控制；热区之间采用隔热材料隔离减少热耦合；全局AI调度器根据各热区负载协同分配散热资源。实测多热源场景温度降低5-7°C，热耦合减少40%。",
                "principles": ["分割原理", "动态性原理", "多孔材料原理"],
                "confidence_score": 87,
                "patent_references": ["手机多热源协同散热系统", "手机热分区管理方法"],
                "rating": 5,
                "evaluation": {"可行性": 83, "创新性": 86, "成本": 75, "转化价值": 88},
            },
        ],
    },
    {
        "title": "手机外壳辐射散热增强方案",
        "description": "手机外壳辐射散热效率低，设计高发射率涂层+散热翅片结构增强外壳散热。",
        "solutions": [
            {
                "title": "高发射率辐射涂层+微型翅片外壳散热方案",
                "description": "在手机外壳内表面涂覆高发射率红外辐射涂层（发射率ε>0.95），提升辐射散热效率；外壳中框集成微型散热翅片增加对流散热面积。综合方案使外壳散热量提升35%，内部温度降低3-4°C。",
                "principles": ["面化原理", "多孔材料原理", "复合材料原理"],
                "confidence_score": 82,
                "patent_references": ["手机外壳辐射散热涂层", "手机散热翅片结构"],
                "rating": 4,
                "evaluation": {"可行性": 85, "创新性": 78, "成本": 80, "转化价值": 82},
            },
        ],
    },
]


# ══════════════════════════════════════════════════════════
#  种子执行函数
# ══════════════════════════════════════════════════════════


def seed_mock_patents(db) -> int:
    """插入 30+ 条手机发热专利数据（幂等：patent_number 唯一）"""
    count = 0
    for p in MOCK_PATENTS:
        # 检查是否已存在
        existing = db.execute(
            "SELECT id FROM patents WHERE patent_number = ?", (p["patent_number"],)
        ).fetchone()
        if existing:
            continue
        db.execute(
            """INSERT INTO patents
               (title, abstract, applicants, inventors, filing_date, publication_date,
                patent_number, ipc_codes, relevance_score, claims, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p["title"],
                p["abstract"],
                json.dumps(p["applicants"], ensure_ascii=False),
                json.dumps(p["inventors"], ensure_ascii=False),
                p["filing_date"],
                p["publication_date"],
                p["patent_number"],
                json.dumps(p["ipc_codes"], ensure_ascii=False),
                p["relevance_score"],
                p["claims"],
                p["description"],
            ),
        )
        count += 1
    if count:
        db.commit()
        logger.info(f"种子化专利数据: 插入 {count} 条手机发热专利")
    return count


def seed_mock_notes(db) -> int:
    """插入 10+ 条手机发热解决笔记到知识库（幂等）"""
    # 确保有一个 mock 知识库
    base_id = "mock-kb-phone-heat"
    existing_base = db.execute(
        "SELECT id FROM knowledge_bases WHERE id = ?", (base_id,)
    ).fetchone()
    if not existing_base:
        db.execute(
            """INSERT INTO knowledge_bases
               (id, user_id, name, status, created_at, updated_at)
               VALUES (?, 0, ?, 'completed',
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))""",
            (base_id, "手机发热技术笔记库"),
        )
        db.commit()

    count = 0
    for i, note in enumerate(MOCK_NOTES):
        item_id = f"mock-note-{i+1:03d}"
        existing = db.execute(
            "SELECT id FROM knowledge_items WHERE id = ?", (item_id,)
        ).fetchone()
        if existing:
            continue
        data = {
            "title": note["title"],
            "content": note["content"],
            "tags": note["tags"],
            "source": "mock-seed",
        }
        db.execute(
            """INSERT INTO knowledge_items
               (id, base_id, type, data, status, created_at, updated_at)
               VALUES (?, ?, 'note', ?, 'completed',
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))""",
            (item_id, base_id, json.dumps(data, ensure_ascii=False)),
        )
        count += 1
    if count:
        db.commit()
        logger.info(f"种子化知识笔记: 插入 {count} 条手机发热解决笔记")
    return count


def seed_mock_history_solutions(db) -> int:
    """插入 5-6 个历史方案（tasks + solutions + workflows + evaluations，幂等）"""
    count = 0
    for task_data in MOCK_HISTORY_TASKS:
        # 检查是否已存在（通过 title 匹配）
        existing = db.execute(
            "SELECT id FROM tasks WHERE title = ? AND user_id = 0",
            (task_data["title"],),
        ).fetchone()
        if existing:
            continue

        # 插入 task
        db.execute(
            """INSERT INTO tasks
               (user_id, title, description, tags, status, created_at, updated_at)
               VALUES (0, ?, ?, '[]', 'completed',
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))""",
            (task_data["title"], task_data["description"]),
        )
        task_row = db.execute(
            "SELECT id FROM tasks WHERE title = ? AND user_id = 0 ORDER BY id DESC LIMIT 1",
            (task_data["title"],),
        ).fetchone()
        task_id = task_row["id"]

        # 插入 solutions + evaluations
        for sol in task_data["solutions"]:
            db.execute(
                """INSERT INTO solutions
                   (task_id, title, description, principles, confidence_score,
                    patent_references, rating)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    sol["title"],
                    sol["description"],
                    json.dumps(sol["principles"], ensure_ascii=False),
                    sol["confidence_score"],
                    json.dumps(sol["patent_references"], ensure_ascii=False),
                    sol["rating"],
                ),
            )
            sol_row = db.execute(
                "SELECT id FROM solutions WHERE task_id = ? AND title = ? ORDER BY id DESC LIMIT 1",
                (task_id, sol["title"]),
            ).fetchone()
            sol_id = sol_row["id"]

            # 插入 evaluations
            for dim, score in sol["evaluation"].items():
                db.execute(
                    """INSERT INTO evaluations
                       (solution_id, user_id, dimension, score, status, created_at)
                       VALUES (?, 0, ?, ?, 'completed',
                        to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))""",
                    (sol_id, dim, score),
                )

        # 插入 workflow（mock 步骤状态）
        steps = []
        phase_map = [
            ("agent1", "demand_portrait", "需求洞察"),
            ("agent2", "problem_modeling", "问题建模"),
            ("agent5", "patent_search", "专利检索"),
            ("agent3", "solution_gen", "方案生成"),
            ("agent4", "evaluation", "方案评估"),
            ("agent6", "conversion", "成果转化"),
        ]
        for agent_id, _phase, label in phase_map:
            steps.append(
                {
                    "agentId": agent_id,
                    "agentType": "problem_analysis",
                    "agentLabel": label,
                    "status": "completed",
                    "description": f"{label}已完成",
                    "duration": "2.3s",
                }
            )
        db.execute(
            """INSERT INTO workflows
               (task_id, status, steps, created_at)
               VALUES (?, 'completed', ?,
                to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))""",
            (task_id, json.dumps(steps, ensure_ascii=False)),
        )
        count += 1

    if count:
        db.commit()
        logger.info(f"种子化历史方案: 插入 {count} 个工程方案历史任务")
    return count


def seed_all_mock_data() -> None:
    """启动时执行所有 mock 种子数据插入（幂等）"""
    db = get_db()
    try:
        seed_mock_patents(db)
        seed_mock_notes(db)
        seed_mock_history_solutions(db)
    except Exception as e:
        logger.warning(f"Mock 种子数据插入失败（非致命）: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
