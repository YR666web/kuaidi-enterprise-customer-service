from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUT = "栈语项目_AI应用开发实习面试手册.docx"
NAVY = "17365D"
BLUE = "2F5597"
PALE = "EAF1F8"
GRAY = "F3F5F7"
BORDER = "D9D9D9"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_border(cell, color=BORDER):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_keep_with_next(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    keep = OxmlElement("w:keepNext")
    p_pr.append(keep)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_shading(cell, NAVY)
        set_cell_border(cell)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9)
    for ridx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cell = cells[i]
            set_cell_border(cell)
            set_cell_margins(cell)
            if ridx % 2:
                set_cell_shading(cell, "F7F9FC")
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.add_run(str(value))
            if widths:
                cell.width = Cm(widths[i])
        if widths:
            for i, w in enumerate(widths):
                cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_bullets(doc, items, level=0):
    for item in items:
        p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
        p.paragraph_format.space_after = Pt(3)
        p.add_run(item)


def add_numbered(doc, items):
    for index, item in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.55)
        p.paragraph_format.first_line_indent = Cm(-0.55)
        p.paragraph_format.space_after = Pt(4)
        p.add_run(f"{index}. {item}")


def add_qa(doc, question, answer):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("问：" + question)
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(BLUE)
    p2 = doc.add_paragraph("答：" + answer)
    p2.paragraph_format.left_indent = Cm(0.45)
    p2.paragraph_format.space_after = Pt(5)


doc = Document()
sec = doc.sections[0]
sec.page_width = Cm(21)
sec.page_height = Cm(29.7)
sec.top_margin = Cm(2.1)
sec.bottom_margin = Cm(1.8)
sec.left_margin = Cm(2.25)
sec.right_margin = Cm(2.25)

styles = doc.styles
styles["Normal"].font.name = "Microsoft YaHei"
styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
styles["Normal"].font.size = Pt(10.5)
styles["Normal"].paragraph_format.line_spacing = 1.25
styles["Normal"].paragraph_format.space_after = Pt(5)
for name, size, before, after in [
    ("Title", 25, 0, 16), ("Subtitle", 12, 0, 10),
    ("Heading 1", 17, 16, 7), ("Heading 2", 13, 12, 5), ("Heading 3", 11, 8, 3),
]:
    s = styles[name]
    s.font.name = "Microsoft YaHei"
    s._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    s.font.size = Pt(size)
    s.font.color.rgb = RGBColor(0, 0, 0)
    if name != "Subtitle":
        s.font.bold = True
    s.paragraph_format.space_before = Pt(before)
    s.paragraph_format.space_after = Pt(after)

# Header and footer
header = sec.header.paragraphs[0]
header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = header.add_run("栈语项目  AI 应用开发实习面试手册")
run.font.name = "Microsoft YaHei"
run.font.size = Pt(8)
run.font.color.rgb = RGBColor(100, 100, 100)
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run("面试准备资料  ·  以当前代码实现为准")
run.font.name = "Microsoft YaHei"
run.font.size = Pt(8)
run.font.color.rgb = RGBColor(110, 110, 110)

# Cover
p = doc.add_paragraph(style="Title")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(95)
p.add_run("栈语智能客服项目").font.color.rgb = RGBColor(0, 0, 0)
p = doc.add_paragraph(style="Title")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("AI 应用开发实习面试手册")
p = doc.add_paragraph(style="Subtitle")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("项目叙事  核心原理  高频追问  演示路线  复习清单")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(25)
r = p.add_run("适用方向：AI 应用开发  Python 后端  智能体与 RAG 工程")
r.bold = True
r.font.color.rgb = RGBColor.from_string(BLUE)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(75)
p.add_run("核心判断").bold = True
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.left_indent = Cm(2)
p.paragraph_format.right_indent = Cm(2)
p.add_run("项目已经足以作为实习面试的核心项目。准备重点不应是继续堆功能，而应是讲清楚如何把不确定的大模型能力放进可控、可验证、可降级的业务系统。")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(65)
p.add_run("整理日期  2026 年 10 月")

doc.add_page_break()

doc.add_heading("使用说明", level=1)
doc.add_paragraph("这份手册面向以栈语项目申请 AI 应用开发实习的候选人。阅读目标不是背诵术语，而是能从一次用户请求出发，完整解释数据如何流转、为什么这样设计、系统失败时如何处理，以及当前实现还有哪些边界。")
add_table(doc, ["准备目标", "你应达到的程度"], [
    ["项目介绍", "1 分钟内讲清定位、难点、方案和结果"],
    ["技术深挖", "能解释 LangGraph、Workflow、RAG、GraphRAG 与降级链"],
    ["工程判断", "能指出安全、一致性、部署和性能上的真实问题"],
    ["现场演示", "能稳定跑通三个核心场景，并解释日志和结果"],
    ["诚实边界", "明确哪些是真实实现、哪些是 Mock、哪些尚未生产化"],
], [4.0, 11.8])

doc.add_heading("一 项目定位与面试结论", level=1)
doc.add_heading("1 适合申请的岗位", level=2)
add_table(doc, ["岗位方向", "匹配度", "说明"], [
    ["AI 应用开发实习", "高", "Agent 编排、RAG、GraphRAG、评测和工程治理形成完整故事"],
    ["Python 后端实习", "高", "FastAPI、SQLAlchemy、RBAC、限流、服务分层和自动化测试较完整"],
    ["NLP 算法实习", "中低", "项目偏应用工程，不包含训练、微调和算法创新"],
    ["AI Infra 实习", "中", "有部署与监控基础，但分布式、吞吐优化和大规模评测仍需加强"],
], [3.3, 2.0, 10.5])
doc.add_heading("2 面试中的核心定位", level=2)
doc.add_paragraph("建议把项目定义为一个强调可控性和可靠性的企业级智能客服原型，而不是简单的聊天页面或大模型 API 封装。项目的价值在于将开放式语言理解与确定性业务流程结合，并为模型失败建立验证、拒答和降级机制。")
doc.add_heading("3 一句话介绍", level=2)
p = doc.add_paragraph()
r = p.add_run("推荐版本：")
r.bold = True
p.add_run("这是一个基于 FastAPI、LangGraph 和 Vue 3 的多租户智能客服系统。我重点解决了多轮业务中的状态管理与意图漂移、混合检索与拒答，以及模型失败后的验证和降级问题。")

doc.add_heading("二 项目架构与一次请求的完整链路", level=1)
doc.add_heading("1 技术架构", level=2)
add_table(doc, ["层次", "主要组件", "职责"], [
    ["展示层", "Vue 3  TypeScript  Pinia  Element Plus", "对话、坐席工作台、知识库和运营界面"],
    ["接入层", "FastAPI  SSE", "接口校验、认证、限流、流式响应"],
    ["编排层", "LangGraph", "状态管理、节点执行、条件路由与 checkpoint"],
    ["能力层", "Workflow  RAG  GraphRAG", "业务办理、文档问答和关系查询"],
    ["数据层", "SQLite  Chroma  Neo4j  Redis", "业务数据、向量、图谱和会话状态"],
    ["治理层", "JWT  RBAC  Metrics  Audit", "租户隔离、权限、监控与审计"],
], [2.4, 5.5, 7.9])
doc.add_heading("2 一次请求如何流转", level=2)
add_numbered(doc, [
    "前端携带 JWT 和 session_id 发送消息；流式接口使用 SSE 接收增量内容。",
    "中间件解析 JWT，得到 user_id、tenant_id 和 roles，并执行接口级权限校验与限流。",
    "LangGraph 根据 tenant_id 与 session_id 生成 thread_id，从 checkpoint 恢复会话状态。",
    "understand 节点记录用户输入并完成意图识别；存在活跃业务流程时优先处理当前流程。",
    "execute 节点选择 Workflow、RAG 或 GraphRAG，并通过降级链处理能力失败。",
    "respond 节点组装最终回答、引用、工具轨迹和降级路径，再写回会话历史。",
    "SSE 将模型 token 或工具最终结果返回前端，前端更新消息状态。",
])
doc.add_heading("3 为什么使用 LangGraph", level=2)
doc.add_paragraph("普通函数链适合固定的一次性流程，但多轮客服存在恢复、打断、重试、分支和状态持久化。LangGraph 把这些行为显式建模为状态、节点和边，使流程可观察、可测试，也更容易限制最大动作次数。它不是为了增加技术名词，而是为复杂会话提供可恢复的控制流。")

doc.add_heading("三 最重要的能力一  Agent 编排与多轮 Workflow", level=1)
doc.add_heading("1 为什么这是项目的主线", level=2)
doc.add_paragraph("多数实习项目只展示单轮问答。本项目更有区分度的部分，是退货、查物流和修改地址等多轮业务在自然语言输入下仍保持确定性。面试中建议把这一部分分配约三分之一的讲解时间。")
doc.add_heading("2 关键机制", level=2)
add_table(doc, ["机制", "解决的问题", "实现思路"], [
    ["槽位收集", "业务参数不完整", "YAML 定义步骤、提示语、字段和校验规则"],
    ["当前槽位纠错", "用户立即修改刚输入的信息", "识别纠错动作并覆盖目标槽位"],
    ["历史槽位回退", "用户修改之前填写的信息", "定位字段、清除旧值、回到对应步骤"],
    ["意图漂移", "办理中突然发起新业务", "判断取消、打断、插入或继续填槽"],
    ["流程栈", "新流程结束后恢复旧流程", "保存 FlowFrame 并按栈恢复上下文"],
    ["动作上限", "循环或模型异常导致无限执行", "单轮限制最大动作数量"],
], [3.0, 5.0, 7.8])
doc.add_heading("3 为什么业务操作不交给 LLM 自由发挥", level=2)
add_bullets(doc, [
    "业务办理涉及状态变更，需要确定的顺序、校验和权限边界。",
    "完全依赖模型规划难以保证每次都填写必填字段，也难以回放和审计。",
    "LLM 适合意图理解和自然语言生成，Workflow 适合执行确定性规则。",
    "组合方案能在自然交互和业务可靠性之间取得平衡。",
])
doc.add_heading("4 应该能讲清的演示案例", level=2)
doc.add_paragraph("用户发起退货，先填写订单号和原因，然后说“刚才订单号写错了”，系统需要识别纠错目标，只修改订单号而保留其他槽位。若用户中途询问退货政策，系统应先回答轻量问题，再继续提示当前待填字段；若用户改为查询物流，则压栈当前流程并启动新流程。")

doc.add_heading("四 最重要的能力二  RAG 检索与答案可靠性", level=1)
doc.add_heading("1 完整链路", level=2)
add_numbered(doc, [
    "上传 PDF、Markdown 或文本，并保留文档、页码、分块序号和租户信息。",
    "按 chunk_size 与 chunk_overlap 切分文本，兼顾语义完整性和召回粒度。",
    "使用 BGE 中文模型生成向量，查询侧添加检索前缀。",
    "分别执行 BM25 关键词检索与 Chroma 向量检索。",
    "通过 RRF 按排名融合结果，必要时使用 reranker 重新排序。",
    "低于相关性阈值时拒答，否则将上下文交给 LLM 生成带引用的答案。",
])
doc.add_heading("2 BM25 和向量检索为什么要结合", level=2)
add_table(doc, ["方式", "优势", "局限"], [
    ["BM25", "订单号、政策名称、专有词等精确匹配强", "同义表达和语义改写能力弱"],
    ["向量检索", "能识别语义相近但措辞不同的问题", "可能忽略关键字，分数难直接解释"],
    ["RRF 融合", "只依赖排名，可合并不同评分尺度", "仍需离线数据校准 top_k 和后续排序"],
    ["Reranker", "对候选 query-document 对进行更精细判断", "增加延迟和模型资源消耗"],
], [2.6, 6.5, 6.7])
doc.add_heading("3 RRF 怎么解释", level=2)
doc.add_paragraph("对每个候选文档，将它在不同检索列表中的排名转成分数并相加。常见形式为 score(d) = Σ 1 / (k + rank)。一个文档若同时在 BM25 和向量结果中靠前，融合分数会更高。RRF 的优势是无需把 BM25 分数和余弦相似度强行归一到同一尺度。")
doc.add_heading("4 如何降低幻觉", level=2)
add_bullets(doc, [
    "只允许模型基于检索上下文回答，并返回文档来源。",
    "设置相关性阈值，证据不足时明确拒答。",
    "使用租户过滤，避免召回其他客户的知识。",
    "建立有答案、无答案、相似干扰和对抗提示测试集。",
    "监控无答案率、引用正确率和人工转接率，而不只观察回答是否流畅。",
])
doc.add_heading("5 当前实现需要诚实说明", level=2)
doc.add_paragraph("项目已经实现 BM25、向量检索和 RRF，也提供 reranker 能力，但 Agent 主链当前关闭 reranker。面试时应说明这是为降低本地演示资源和延迟所做的取舍，并提出用离线指标与延迟数据决定是否启用，而不是声称已经完成线上调优。")

doc.add_heading("五 GraphRAG 的亮点与边界", level=1)
doc.add_heading("1 查询链路", level=2)
doc.add_paragraph("用户问题 → 实体与节点类型识别 → 入口节点召回 → Text2Cypher → 只读与结构校验 → 错误反馈自纠错 → Neo4j 执行 → 基于查询结果生成回答。")
doc.add_heading("2 哪些问题适合 GraphRAG", level=2)
add_table(doc, ["问题类型", "优先方案", "原因"], [
    ["退换货政策是什么", "RAG", "答案主要存在于非结构化文档中"],
    ["某订单关联哪些商品和物流节点", "GraphRAG", "需要沿实体关系查询"],
    ["帮我修改收货地址", "Workflow", "属于有副作用的确定性业务操作"],
    ["你好或谢谢", "直接回答", "无需访问外部能力"],
], [5.3, 3.2, 7.3])
doc.add_heading("3 安全重点", level=2)
add_bullets(doc, [
    "只允许 MATCH 和 RETURN 等只读查询，禁止 CREATE、DELETE、SET 等写操作。",
    "所有用户输入通过参数传递，不直接拼接到 Cypher。",
    "强制加入用户或租户过滤条件，并限制返回数量。",
    "限制可访问的节点、关系和属性，避免模型探索整个数据库。",
    "记录生成语句、校验结果和失败原因，便于审计。",
])
doc.add_heading("4 当前边界", level=2)
doc.add_paragraph("GraphRAG 的工程链路已经搭建，但标签路由仍使用 Mock；未配置 LLM 时，Cypher 生成和回答也会使用 Mock。正确表述是“实现并测试了 GraphRAG 技术链路”，而不是“已在真实生产图谱中稳定运行”。")

doc.add_heading("六 可靠性  降级与可观测性", level=1)
doc.add_heading("1 为什么降级是 AI 应用的核心能力", level=2)
doc.add_paragraph("模型、向量库、图数据库和业务系统都可能失败。可靠的 AI 应用不能把异常包装成一个看似合理的答案，而应识别失败位置，尝试有限重试，切换到能力较弱但安全的路径，最终在证据不足时拒答或转人工。")
doc.add_heading("2 可讲的降级策略", level=2)
add_table(doc, ["故障", "降级动作", "最终原则"], [
    ["LLM 意图识别失败", "回退关键词路由", "宁可保守路由，不执行错误业务"],
    ["GraphRAG 查询失败", "校验、自纠错，再降级至 RAG", "限制重试次数并保留轨迹"],
    ["RAG 无可靠结果", "返回无答案提示", "不编造政策或业务状态"],
    ["业务供应商不可用", "有限重试和熔断", "避免持续放大故障"],
    ["用户明确要求人工", "创建人工转接任务", "保留最近对话上下文"],
], [4.0, 6.2, 5.6])
doc.add_heading("3 应关注的指标", level=2)
add_table(doc, ["类别", "指标"], [
    ["模型与路由", "意图准确率、工具选择准确率、越权操作率"],
    ["检索", "Recall@K、MRR、无答案识别率、引用正确率"],
    ["业务", "流程完成率、平均轮次、纠错成功率、人工转接率"],
    ["性能", "首字延迟 P50/P95、总延迟、吞吐量、错误率"],
    ["稳定性", "重试率、降级率、熔断次数、依赖可用性"],
], [4.0, 11.8])
doc.add_paragraph("当前项目有离线评测接口和 98 项通过的后端测试，这是工程质量证据。但单元测试通过不等于 RAG 效果好；检索效果仍需带标注的数据集和指标验证。")

doc.add_heading("七 项目真实完成度与风险认知", level=1)
doc.add_heading("1 已经完成并可重点展示", level=2)
add_bullets(doc, [
    "LangGraph 状态编排、checkpoint 和最大动作保护。",
    "声明式多轮流程、槽位校验、纠错、打断与恢复。",
    "文档解析、混合检索、RRF、拒答和来源引用。",
    "GraphRAG 的生成、校验、自纠错与执行骨架。",
    "JWT、RBAC、租户上下文、限流、审计和 Prometheus 指标。",
    "SSE 流式接口、人工转接、知识库 CRUD 和基础三端页面。",
    "98 项后端测试通过，前端类型检查和生产构建通过。",
])
doc.add_heading("2 不应夸大的内容", level=2)
add_bullets(doc, [
    "GraphRAG 部分路由仍为 Mock，尚未形成真实图谱数据闭环。",
    "前端身份、会话、流程配置和部分 Dashboard 数据仍含 Mock。",
    "真实嵌入模型的慢速集成测试默认跳过。",
    "没有真实生产流量和线上效果数据。",
    "当前是生产化前期原型，不是已经大规模上线的系统。",
])
doc.add_heading("3 主动指出会加分的工程问题", level=2)
add_table(doc, ["优先级", "问题", "改进方向"], [
    ["P0", "生产默认 JWT 密钥", "生产启动时禁止默认值并引入 Secret 管理"],
    ["P0", "Dashboard 后端缺少 RBAC", "增加管理员权限与租户级指标"],
    ["P0", "替换文档删除向量时未带 tenant_id", "使用 doc_id 与 tenant_id 联合过滤"],
    ["P1", "数据库与向量库写入非事务", "状态机、幂等、补偿和一致性巡检"],
    ["P1", "文件上传无大小和类型限制", "流式处理、白名单、大小与页数上限"],
    ["P1", "多 worker 下内存指标和限流分裂", "Redis 与独立 Prometheus 采集"],
    ["P2", "前端包体积较大", "Element Plus 和 ECharts 按需加载与拆包"],
], [1.7, 7.0, 7.1])

doc.add_heading("八 高频面试问答", level=1)
add_qa(doc, "为什么不用普通状态机或一串函数？", "普通状态机可以完成简单流程，但本项目同时需要多轮恢复、嵌套流程、条件路由、工具执行和持久化。LangGraph 让这些状态转换显式化，并提供 checkpoint 和事件流。业务内部仍使用确定性 Workflow，避免把全部控制权交给模型。")
add_qa(doc, "checkpoint 保存什么？", "保存会话中的消息、当前意图、活跃流程、已收集槽位、流程栈、工具轨迹和其他状态。thread_id 由 tenant_id 与 session_id 组成，避免不同租户使用相同会话号时互相污染。")
add_qa(doc, "为什么 SSE 而不是 WebSocket？", "当前主要需求是服务端向客户端单向流式输出 token，SSE 基于 HTTP，接入和代理配置更简单，并自带事件语义。若未来需要坐席协同、双向实时状态和多事件通道，再考虑 WebSocket。")
add_qa(doc, "chunk_size 怎么确定？", "不能凭经验固定。块太小会丢上下文，太大则增加噪声和 token 成本。应根据文档结构构建标注查询集，比较不同切分参数下的 Recall@K、MRR、回答正确率和延迟。")
add_qa(doc, "为什么需要拒答？", "客服系统涉及政策和业务状态，错误答案的成本高于暂时无法回答。相关证据不足时拒答或转人工，可以控制幻觉风险，也方便统计知识缺口。")
add_qa(doc, "怎样防止提示词注入？", "将系统指令、检索内容和用户输入分隔；不把文档内容当作系统命令；工具执行采用白名单和结构化参数；高风险操作使用确定性校验和权限检查；对异常指令建立评测用例。")
add_qa(doc, "怎样保证多租户隔离？", "JWT 提供 tenant_id，API 依赖执行 RBAC，数据库和向量检索都应强制带 tenant_id，checkpoint key 也包含 tenant_id。不能相信请求体里客户端自行填写的租户值。")
add_qa(doc, "LLM 或 Neo4j 不可用怎么办？", "执行有限重试，记录失败原因和降级路径；GraphRAG 可降级到 RAG，RAG 无证据则拒答，业务系统失败则熔断或转人工。不能在依赖失败后伪造成功结果。")
add_qa(doc, "怎么证明系统效果好？", "分别评估路由、检索、回答和业务完成度。使用意图准确率、Recall@K、MRR、无答案识别率、流程完成率、引用正确率和首字延迟等指标，并保留固定回归集。")
add_qa(doc, "项目中最难的部分是什么？", "最难的不是接入模型，而是协调不确定的自然语言与确定的业务状态。我通过 LangGraph 管理会话状态，用 Workflow 承载有副作用业务，并设计纠错、意图漂移、动作上限和降级路径来控制异常。")
add_qa(doc, "如果继续做，你先优化什么？", "先修复权限和租户边界，再解决数据库与向量库的一致性；之后建立真实检索评测集，校准阈值和 reranker；最后去除前端 Mock，完善流程发布和多实例监控。")

doc.add_heading("九 三种项目介绍模板", level=1)
doc.add_heading("1 三十秒版本", level=2)
doc.add_paragraph("我做了一个基于 FastAPI、LangGraph 和 Vue 3 的智能客服系统。与普通 RAG Demo 不同，它同时支持多轮业务 Workflow、混合检索和 GraphRAG，并重点处理槽位纠错、意图漂移、拒答与能力降级。项目目前有 98 项后端测试通过，适合作为企业级 AI 客服的原型。")
doc.add_heading("2 一分钟版本", level=2)
doc.add_paragraph("这个项目解决的是大模型客服如何可靠执行业务的问题。接入层使用 FastAPI 和 SSE；LangGraph 负责会话状态、路由和 checkpoint；退货、查物流和修改地址使用 YAML 定义的确定性 Workflow，支持槽位校验、纠错、打断与恢复。知识问答使用 BGE、BM25、Chroma 和 RRF 进行混合检索，并在证据不足时拒答。关系类问题走 GraphRAG，生成的 Cypher 必须通过只读校验和自纠错后才会执行。平台侧还实现了 JWT、RBAC、多租户、限流、监控、人工转接和离线评测。")
doc.add_heading("3 简历项目描述", level=2)
add_bullets(doc, [
    "基于 FastAPI、LangGraph 与 Vue 3 构建多租户智能客服系统，统一编排 Workflow、RAG 和 GraphRAG，并通过 Redis checkpoint 支持多轮状态恢复。",
    "设计声明式业务流程与流程栈，支持槽位收集、历史纠错、意图漂移、流程打断和恢复，通过动作上限避免 Agent 循环。",
    "实现 BGE 向量检索、BM25 与 RRF 融合、阈值拒答和来源引用，并搭建 Text2Cypher 校验、自纠错与降级链。",
    "实现 JWT、RBAC、租户隔离、限流、审计、指标和人工转接；建立自动化测试与离线评测，当前 98 项后端测试通过。",
])
doc.add_paragraph("注意：简历中只有在你能独立解释并现场展示时，才保留对应描述。不要写未经实际测量的准确率、并发量或性能提升比例。")

doc.add_heading("十 现场演示脚本", level=1)
doc.add_heading("场景一 多轮流程与纠错", level=2)
add_numbered(doc, [
    "输入退货请求，观察系统进入退货流程并询问订单信息。",
    "填写订单号和退货原因，再修改之前的订单号。",
    "说明系统如何定位目标槽位、保留其他槽位并继续执行。",
    "展示工具轨迹、最终业务结果和 checkpoint 恢复。",
])
doc.add_heading("场景二 RAG 引用与拒答", level=2)
add_numbered(doc, [
    "询问知识库中明确存在的退换货政策，展示回答和来源。",
    "解释 BM25 与向量召回如何融合。",
    "询问知识库不存在的问题，展示无答案策略。",
    "强调拒答是可靠性设计，不是系统能力不足的遮掩。",
])
doc.add_heading("场景三 GraphRAG 校验与降级", level=2)
add_numbered(doc, [
    "提出一个需要实体关系查询的问题。",
    "展示实体路由、生成的 Cypher 和只读校验。",
    "模拟查询或校验失败，展示错误反馈、自纠错和有限重试。",
    "说明重试耗尽后如何降级到 RAG 或安全拒答。",
])
doc.add_heading("演示前检查", level=2)
add_bullets(doc, [
    "后端、前端、Redis、Neo4j 和本地模型均能正常启动。",
    "准备固定测试账号和 JWT，但屏幕录制中不展示密钥。",
    "提前导入演示知识文档和图谱数据。",
    "关闭无关窗口，保留接口文档、日志和前端页面。",
    "准备离线或外部模型不可用时的备用演示路径。",
])

doc.add_heading("十一 七天准备计划", level=1)
add_table(doc, ["时间", "重点", "输出"], [
    ["第 1 天", "画架构图并走读一次请求", "能脱稿讲 1 分钟项目介绍"],
    ["第 2 天", "LangGraph 与 Workflow", "讲清 state、checkpoint、纠错和意图漂移"],
    ["第 3 天", "RAG 与检索", "手算 RRF，说明切分、阈值和评测"],
    ["第 4 天", "GraphRAG 与安全", "讲清 Text2Cypher、校验、自纠错和租户过滤"],
    ["第 5 天", "工程问题", "准备安全、一致性、多 worker 和部署追问"],
    ["第 6 天", "现场演示", "稳定跑通三个场景并录一次屏"],
    ["第 7 天", "模拟面试", "完成 30 分钟问答并修正表达"],
], [2.4, 6.0, 7.4])

doc.add_heading("十二 最终复习清单", level=1)
add_table(doc, ["检查项", "完成标准"], [
    ["项目定位", "能说明为什么不是普通聊天 Demo"],
    ["请求链路", "能从 Vue 讲到 API、Agent、能力层和数据层"],
    ["LangGraph", "能解释 state、node、edge、checkpoint 和动作上限"],
    ["Workflow", "能解释纠错、漂移、插入、打断和恢复"],
    ["RAG", "能解释切分、BGE、BM25、向量、RRF、rerank 和拒答"],
    ["GraphRAG", "能解释适用场景、Cypher 安全和当前 Mock 边界"],
    ["评测", "能区分单元测试、检索评测、回答评测和业务指标"],
    ["可靠性", "能说明重试、降级、熔断、拒答和转人工"],
    ["安全", "能说明 JWT、RBAC、租户隔离和提示词注入防护"],
    ["项目不足", "能主动提出至少三个真实问题及改进方案"],
    ["演示", "三个场景可稳定运行，有外部服务失败预案"],
], [5.2, 10.6])

doc.add_heading("结语", level=1)
doc.add_paragraph("对于 AI 应用开发实习，这个项目已经具备竞争力。真正决定面试表现的，不是组件数量，而是你能否解释每项设计解决了什么问题、为什么选择这一方案、如何验证效果，以及系统在哪些条件下会失败。把主线集中在 Agent 编排、多轮 Workflow、RAG 质量、可靠性和评测上，前端与平台能力作为工程完整性的支撑即可。")
doc.add_paragraph("最重要的原则是：只讲自己理解并能验证的实现；对尚未完成的部分明确说明现状，并给出合理的下一步方案。")

# Keep headings with their following content and set table widths
for p in doc.paragraphs:
    if p.style.name.startswith("Heading"):
        set_keep_with_next(p)
    if p.text.strip() == "十一 七天准备计划":
        p.paragraph_format.page_break_before = True

doc.core_properties.title = "栈语智能客服项目 AI 应用开发实习面试手册"
doc.core_properties.subject = "AI 应用开发实习项目准备"
doc.core_properties.author = "Codex"
doc.core_properties.keywords = "LangGraph, RAG, GraphRAG, FastAPI, AI 应用开发, 面试"
doc.save(OUT)
print(OUT)
