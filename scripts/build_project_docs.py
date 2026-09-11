from __future__ import annotations

from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUTPUT_DIR = Path(r"F:\agent学习路径\物流知识库")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_border(cell, color: str = "D9D9D9", size: str = "6") -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_run_font(run, name="Microsoft YaHei", size=10.5, bold=False, color="000000") -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def set_doc_defaults(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for style_name, size, color in (
        ("Title", 22, "000000"),
        ("Heading 1", 15, "000000"),
        ("Heading 2", 12.5, "000000"),
        ("Heading 3", 11, "000000"),
    ):
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(12 if style_name == "Heading 1" else 8)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("电商物流智能客服项目")
    set_run_font(run, size=9, color="666666")


def add_title(doc: Document, title: str, subtitle: str) -> None:
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.add_run(title)
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(14)
    run = p2.add_run(subtitle)
    set_run_font(run, size=11, color="666666")


def add_meta_table(doc: Document, rows: Iterable[tuple[str, str]]) -> None:
    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = True
    for key, value in rows:
        cells = table.add_row().cells
        cells[0].text = key
        cells[1].text = value
        set_cell_shading(cells[0], "EAF2F8")
        for idx, cell in enumerate(cells):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            set_cell_border(cell)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    set_run_font(run, size=9.5, bold=(idx == 0))
    doc.add_paragraph()


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        set_cell_shading(cell, "2F5597")
        set_cell_border(cell)
        set_cell_margins(cell, top=120, bottom=120)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            set_run_font(run, size=9.5, bold=True, color="FFFFFF")
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if widths:
            cell.width = Cm(widths[i])
    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
            if row_idx % 2 == 1:
                set_cell_shading(cells[i], "F5F7FA")
            set_cell_border(cells[i])
            set_cell_margins(cells[i], top=110, bottom=110)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cells[i].paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    set_run_font(run, size=9.2)
    doc.add_paragraph()


def add_bullet(doc: Document, text: str, level: int = 0) -> None:
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(3)
    p.add_run(text)


def add_number(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(3)
    p.add_run(text)


def add_code(doc: Document, code: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.right_indent = Cm(0.5)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.05
    for line_idx, line in enumerate(code.splitlines()):
        run = p.add_run(line)
        set_run_font(run, name="Consolas", size=9, color="333333")
        if line_idx < len(code.splitlines()) - 1:
            run.add_break()


def create_intent_doc() -> Path:
    doc = Document()
    set_doc_defaults(doc)
    add_title(
        doc,
        "电商物流智能客服意图识别实现说明",
        "用于项目介绍、面试说明和技术方案复盘 | 更新时间 2026年9月6日",
    )
    add_meta_table(
        doc,
        [
            ("项目定位", "面向电商物流场景的 MVP 智能客服系统"),
            ("本文目的", "说明意图识别模块为什么这样设计、如何实现、如何验证"),
            ("当前结论", "人工测评准确率约 90%，已达到 MVP 继续推进的门槛"),
            ("当前边界", "本模块识别当前消息，不负责长期记忆、复杂多轮状态或 MCP"),
        ],
    )

    doc.add_heading("一 项目背景与问题定义", level=1)
    doc.add_paragraph(
        "物流客服消息通常不是结构化输入。用户可能直接提供订单号，也可能先表达情绪、补充联系方式，"
        "或者在一句话中同时提出多个诉求。因此，系统不能只依赖关键词命中，而需要先判断当前消息的主意图，"
        "再提取后续流程所需的实体，并根据置信度和字段完整性决定是否允许调用业务工具。"
    )
    doc.add_paragraph(
        "本项目采用“Dify 负责自然语言理解和流程编排，Python 后端负责契约校验、业务事实和安全兜底”的分工。"
        "这样可以把模型的不确定性限制在意图识别层，避免模型直接修改订单、提交投诉或编造物流状态。"
    )

    doc.add_heading("二 意图范围", level=1)
    add_table(
        doc,
        ["意图", "标识", "典型用户表达", "后续方向"],
        [
            ["物流查询", "tracking_query", "查 ORD1001 到哪里了", "订单查询工具"],
            ["物流知识问答", "knowledge_query", "电池可以寄吗", "知识库检索"],
            ["地址修改", "address_change", "把 ORD1001 改到新地址", "信息收集和确认"],
            ["投诉", "complaint", "我要投诉快递员", "补齐投诉信息后提交"],
            ["人工客服", "human_transfer", "请转人工", "转人工或创建人工请求"],
            ["工单查询", "ticket_status", "查询工单 TABC123 的进度", "工单查询工具"],
            ["未知", "unknown", "你好、帮我处理一下", "澄清，不调用工具"],
        ],
        widths=[2.6, 3.0, 5.0, 3.8],
    )

    doc.add_heading("三 总体处理流程", level=1)
    add_number(doc, "用户消息进入 Dify Chatflow。")
    add_number(doc, "Dify 根据提示词判断一个主意图，并输出统一 JSON。")
    add_number(doc, "规则提取器对订单号、工单号、手机号和确认词做高确定性提取。")
    add_number(doc, "Python 解析器校验 JSON 结构、枚举值、置信度和实体字段。")
    add_number(doc, "系统计算缺失字段，并执行工具调用门槛。信息不足或风险较高时进入澄清流程。")
    add_number(doc, "只有通过门槛的结果才进入订单、知识库、投诉或工单等后续业务模块。")
    add_code(
        doc,
        '{"intent":"tracking_query","confidence":0.95,'
        '"entities":{"order_id":"ORD1001","ticket_no":null,'
        '"new_address":null,"complaint_content":null,"contact":null},'
        '"missing_slots":[],"action":"query","should_call_tool":true}',
    )

    doc.add_heading("四 输出契约设计", level=1)
    doc.add_paragraph(
        "输出契约写入 docs/intent-contract.md，并同时约束 Dify、Python 数据模型和评测集。统一契约的价值是让每个模块"
        "都围绕相同字段协作，避免 Dify 输出一套格式、后端又猜另一套格式。"
    )
    add_table(
        doc,
        ["字段", "类型", "规则"],
        [
            ["intent", "固定枚举", "只能是 7 类意图之一"],
            ["confidence", "0 到 1 的数字", "低于 0.70 时禁止调用工具"],
            ["entities", "对象", "包含 5 个固定实体字段，未提取使用 null"],
            ["missing_slots", "字符串数组", "列出当前意图所需但缺失的字段"],
            ["action", "固定枚举", "query、collect_info、clarify、transfer、confirm、cancel"],
            ["should_call_tool", "布尔值", "由置信度、意图和字段完整性共同决定"],
        ],
        widths=[3.0, 3.5, 9.0],
    )

    doc.add_heading("五 Dify 中完成的工作", level=1)
    add_bullet(doc, "建立独立的物流意图识别 Chatflow，避免与原有物流查询应用混用。")
    add_bullet(doc, "在提示词中固定 7 类意图、主意图优先级、实体字段和工具调用门槛。")
    add_bullet(doc, "针对订单号、工单号、联系方式、地址和投诉内容给出正例及边界规则。")
    add_bullet(doc, "把复杂实体作为 result_json 字符串传递，规避 Dify Code 节点 outputs.children.type 的导入兼容问题。")
    add_bullet(doc, "当前可导入 DSL：物流意图识别-v2-纯字符串输出.yml。")
    doc.add_paragraph(
        "这里的设计取舍是先确保 DSL 可导入、可执行、可被后端稳定解析，再逐步扩展复杂结构。"
        "实体信息没有丢失，而是位于 result_json 中，由 Python 侧负责最终结构化校验。"
    )

    doc.add_heading("六 Python 代码实现", level=1)
    add_table(
        doc,
        ["模块", "职责", "关键实现"],
        [
            ["app/agent/intent_schema.py", "定义对外数据模型", "Pydantic 模型、固定枚举、工具门禁"],
            ["app/agent/intent_rules.py", "确定性实体提取", "正则提取订单号、工单号、手机号和确认词"],
            ["app/agent/intent_extractor.py", "组合规则提取器", "输出统一 RuleExtractionResult"],
            ["docs/intent-contract.md", "跨模块契约", "字段、规则、验收标准和边界"],
            ["scripts/evaluation/cases/*.jsonl", "离线评测集", "基础样例和对抗样例"],
        ],
        widths=[5.2, 5.0, 5.3],
    )
    doc.add_paragraph(
        "代码采用模块化拆分，避免把所有逻辑集中在一个 Agent 文件中。规则提取和模型语义判断相互独立，"
        "便于单独测试、替换和复用。Pydantic 模型使用 extra=forbid，能够尽早发现字段拼写和结构漂移。"
    )
    add_code(
        doc,
        "if result.intent == 'unknown' or result.confidence < 0.70 or result.missing_slots:\n"
        "    result.should_call_tool = False",
    )

    doc.add_heading("七 主意图判断策略", level=1)
    add_bullet(doc, "每条消息只输出一个主意图，避免一次自动触发多个业务工具。")
    add_bullet(doc, "明确投诉优先于普通物流查询，因为投诉是更强的用户动作。")
    add_bullet(doc, "明确转人工优先于普通咨询，但人工请求内容不足时先澄清。")
    add_bullet(doc, "只出现订单号不等于查询订单，必须同时出现查询、进度、到哪里等动作语义。")
    add_bullet(doc, "混合意图无法安全选择时输出 unknown，交给后续澄清，而不是猜测。")
    add_bullet(doc, "当前阶段只读取当前消息，不自动把历史消息中的订单号合并进结果。")

    doc.add_heading("八 测试与测评方法", level=1)
    doc.add_paragraph(
        "测试分为三层。第一层是数据模型测试，检查字段、枚举、范围和工具门禁；第二层是规则提取测试，"
        "检查各种大小写、连字符、脱敏手机号和确认表达；第三层是意图样例和对抗样例，用于评估真实流程风险。"
    )
    add_table(
        doc,
        ["测试资产", "规模或状态", "验证目标"],
        [
            ["tests/test_intent_schema.py", "已通过", "结构化输出和工具门禁"],
            ["tests/test_intent_rules.py", "已通过", "订单号、工单号、手机号、确认词"],
            ["tests/test_intent_extractor.py", "已通过", "规则提取组合结果"],
            ["intent_cases.jsonl", "35 条", "7 类意图基础覆盖"],
            ["intent_adversarial_cases.jsonl", "15 条", "混合意图、模糊动作、历史实体"],
            ["人工测评", "约 90%", "Dify 当前识别效果是否达到 MVP 门槛"],
        ],
        widths=[5.0, 4.0, 6.5],
    )
    doc.add_paragraph(
        "当前阶段的验收目标是：基础意图准确率不低于 90%，对抗样例不低于 85%，订单号提取准确率不低于 95%，"
        "低置信度和缺字段场景的工具误调用率为 0。人工测评达到 90% 后，可以进入输出解析和业务闭环阶段。"
    )

    doc.add_heading("九 面试介绍参考", level=1)
    doc.add_paragraph(
        "我在物流客服项目中把意图识别设计成一个独立模块。Dify 负责理解用户自然语言，输出固定的意图、置信度、"
        "实体和缺失字段；Python 后端使用 Pydantic 做结构校验，并用规则提取器处理订单号、工单号和联系方式等"
        "高确定性字段。系统不会因为模型给出了一个意图就直接调用工具，而是增加了置信度、必要字段和确认状态三道门槛。"
        "对于无法判断的消息、混合意图和历史实体引用，系统会降级为澄清。这样在 MVP 规模下既保留了大模型的语义能力，"
        "又把误调用业务接口的风险控制在可测范围内。当前人工测评准确率约为 90%，下一步将把 Dify 输出接入通用解析器，"
        "再进入会话状态、Redis 和端到端流程。"
    )

    doc.add_heading("十 当前局限", level=1)
    add_bullet(doc, "还没有完成 Dify 输出到 Python 后端的正式解析器和批量回归命令。")
    add_bullet(doc, "当前不支持把历史消息中的实体自动合并到当前轮次。")
    add_bullet(doc, "投诉、地址修改等业务还需要后续会话状态和确认流程才能形成完整闭环。")
    add_bullet(doc, "Redis、MySQL 和 MCP 尚未接入本阶段，不应在面试中表述为已经完成。")

    path = OUTPUT_DIR / "电商物流智能客服_意图识别实现说明.docx"
    doc.save(path)
    return path


def create_handoff_doc() -> Path:
    doc = Document()
    set_doc_defaults(doc)
    add_title(
        doc,
        "电商物流智能客服项目进度与后续交付计划",
        "新窗口交接文档 | 更新时间 2026年9月6日",
    )
    add_meta_table(
        doc,
        [
            ("工作方式", "每完成一个模块，先做模块内循环测评，再由用户确认进入下一模块"),
            ("当前阶段", "第一阶段：意图识别与实体提取"),
            ("当前状态", "意图识别人工测评约 90%，可以进入输出校验阶段"),
            ("项目目标", "完成一个可靠、可测评、非企业级但能展示完整闭环的物流客服 MVP"),
        ],
    )

    doc.add_heading("一 新窗口首先要知道什么", level=1)
    doc.add_paragraph(
        "这是一个已经进行到中途的电商物流智能客服项目。不要从零设计，也不要一次性展开所有模块。"
        "当前优先级是把每个模块做成可重复测试的循环工程：定义契约，完成最小实现，准备测试集，运行测评，"
        "修复问题，记录结果，得到用户确认后再进入下一模块。"
    )
    doc.add_paragraph(
        "用户特别要求：避免上帝文件；功能要模块化；重复逻辑封装成通用函数和组件；如果要修改 Dify，直接修改 DSL YAML，"
        "用户会手动导入；每做完一步都要先汇报做了什么、增加了什么，并等待用户确认。"
    )

    doc.add_heading("二 项目目录与关键文件", level=1)
    add_table(
        doc,
        ["路径", "用途", "当前说明"],
        [
            ["E:/PythonProject5/backend-lab/app/agent/", "智能客服 Agent 相关模块", "已包含意图模型和规则提取"],
            ["app/agent/intent_schema.py", "意图输出数据模型", "已完成"],
            ["app/agent/intent_rules.py", "规则实体提取", "已完成"],
            ["app/agent/intent_extractor.py", "规则提取组合器", "已完成"],
            ["docs/intent-contract.md", "意图识别契约", "已完成"],
            ["scripts/evaluation/cases/", "离线测试集", "已包含基础和对抗样例"],
            ["tests/", "Python 自动化测试", "已有较多后端与意图测试"],
            ["F:/agent学习路径/物流知识库/物流意图识别-v2-纯字符串输出.yml", "Dify 意图识别 DSL", "可作为当前导入版本"],
            ["F:/agent学习路径/物流知识库/物流查询测试.yml", "原有物流查询 DSL", "不要误当成最新意图 DSL"],
        ],
        widths=[6.0, 5.0, 5.0],
    )

    doc.add_heading("三 已完成内容", level=1)
    add_table(
        doc,
        ["模块", "完成内容", "证据或文件"],
        [
            ["意图契约", "固定 7 类意图、5 类实体、JSON 格式和工具门槛", "docs/intent-contract.md"],
            ["数据模型", "Pydantic 校验、枚举限制、低置信度安全降级", "app/agent/intent_schema.py"],
            ["规则提取", "订单号、工单号、手机号、确认和取消表达", "app/agent/intent_rules.py"],
            ["模块组合", "统一输出 RuleExtractionResult", "app/agent/intent_extractor.py"],
            ["基础用例", "7 类意图各 5 条，共 35 条", "scripts/evaluation/cases/intent_cases.jsonl"],
            ["对抗用例", "混合意图、模糊动作、历史实体等 15 条", "scripts/evaluation/cases/intent_adversarial_cases.jsonl"],
            ["Dify DSL", "修复 Code 节点结构化 outputs 兼容错误", "v2 纯字符串输出 DSL"],
            ["人工测评", "用户测试准确率达到约 90%", "用户当前反馈"],
        ],
        widths=[3.5, 8.0, 4.5],
    )
    doc.add_paragraph(
        "历史基线测试为 poetry run pytest tests -q，曾通过 81 项测试。新窗口开始工作时，应重新运行一次，"
        "以当前工作区结果为准，不要假设历史结果仍然有效。"
    )

    doc.add_heading("四 当前已确认的技术边界", level=1)
    add_bullet(doc, "Dify：意图识别、参数提取和流程编排。")
    add_bullet(doc, "FastAPI：业务事实、权限、状态、订单、知识库和工单接口。")
    add_bullet(doc, "当前阶段：先完成意图识别模块，不提前接入长期记忆和复杂多轮状态。")
    add_bullet(doc, "Redis：放在会话状态和短期记忆阶段，用于多轮上下文、TTL 和流程状态。")
    add_bullet(doc, "MySQL：放在业务数据持久化阶段，替换或扩展当前 SQLite 数据访问层。")
    add_bullet(doc, "MCP：在业务工具接口稳定后再做适配层，不让 MCP 反过来主导业务模型。")

    doc.add_heading("五 下一步执行顺序", level=1)
    add_table(
        doc,
        ["阶段", "模块目标", "完成标准"],
        [
            ["1", "Dify 输出校验与 Python 解析器", "异常格式可兜底，统一转换为 IntentResult"],
            ["2", "批量意图评测脚本", "一条命令输出准确率、实体准确率、工具误调用率"],
            ["3", "第一阶段验收", "基础、对抗和安全门槛均达标，并记录基线"],
            ["4", "会话状态与多轮记忆", "短期状态可保存、读取、过期和清理"],
            ["5", "Redis 接入", "把会话状态从内存迁移到 Redis，补充 TTL 测试"],
            ["6", "MySQL 数据层", "订单、工单等业务数据持久化，保留 repository/service 分层"],
            ["7", "业务工具闭环", "物流查询、知识问答、地址修改、投诉、工单状态"],
            ["8", "MCP 适配", "把稳定业务能力封装为可控工具，增加参数和权限校验"],
            ["9", "端到端测评", "从用户输入到最终回复覆盖成功、澄清、拒绝和异常链路"],
        ],
        widths=[2.0, 7.0, 7.0],
    )

    doc.add_heading("六 当前下一步的详细操作", level=1)
    doc.add_heading("步骤 1 Dify 输出校验", level=2)
    add_bullet(doc, "在 Dify 中使用物流意图识别-v2-纯字符串输出.yml，确认输入 ORD1001 查询可以正常运行。")
    add_bullet(doc, "确认最终输出包含 action、confidence、intent、result_json、should_call_tool。")
    add_bullet(doc, "如果仍然出现 outputs.entities 或 outputs.missing_slots 的 CodeNodeData 错误，导出 Dify 当前应用 DSL，先检查实际加载的版本。")
    add_bullet(doc, "不要继续修改已经正确的 v2 文件来猜测旧应用状态。")

    doc.add_heading("步骤 2 Python 通用解析器", level=2)
    add_bullet(doc, "新增独立模块，例如 app/agent/dify_output_parser.py，不要把解析逻辑塞进 main.py 或单个 Agent 文件。")
    add_bullet(doc, "解析字符串 result_json，并转换为 IntentResult。")
    add_bullet(doc, "处理 Markdown 代码块、前后空白、JSON 解析失败、缺字段、非法枚举、confidence 越界等情况。")
    add_bullet(doc, "解析失败统一返回 unknown_intent_result，禁止调用工具。")
    add_bullet(doc, "新增针对正常、空值、脏 JSON 和安全降级的单元测试。")

    doc.add_heading("步骤 3 批量测评", level=2)
    add_bullet(doc, "读取 scripts/evaluation/cases/ 下的 JSONL 文件。")
    add_bullet(doc, "统计 intent accuracy、entity accuracy、missing_slots accuracy、tool_gate accuracy。")
    add_bullet(doc, "将基础样例和对抗样例分开统计，不只报告一个平均分。")
    add_bullet(doc, "每次 Dify Prompt 或规则修改后，保留测评结果，形成可比较的回归记录。")

    doc.add_heading("七 每个模块都要执行的循环工程", level=1)
    add_number(doc, "先写模块契约：输入、输出、错误、边界和禁止行为。")
    add_number(doc, "再拆分代码：路由、服务、仓储、解析器、状态管理各自负责单一职责。")
    add_number(doc, "准备正常样例、缺字段样例、异常样例和对抗样例。")
    add_number(doc, "先运行自动化测试，再用 Dify 或 API 做真实链路测试。")
    add_number(doc, "记录通过率、错误类型和是否存在危险误调用。")
    add_number(doc, "只修复当前模块的问题，修复后重新跑完整回归。")
    add_number(doc, "向用户汇报本步变更和结果，等待用户确认后再进入下一模块。")

    doc.add_heading("八 新窗口的协作规则", level=1)
    add_bullet(doc, "先读取本交付文档、docs/intent-contract.md 和当前 git status。")
    add_bullet(doc, "不要回滚用户或历史已有修改，尤其要注意当前工作区是 dirty 的。")
    add_bullet(doc, "修改前先说明准备修改哪些文件和原因。")
    add_bullet(doc, "Dify 修改直接产出新的 YAML 文件，保留旧 DSL，不覆盖用户原文件。")
    add_bullet(doc, "完成一步后只汇报这一步，不自动跨越用户确认进入下一步。")
    add_bullet(doc, "如果发现历史说明与当前代码冲突，以当前代码、测试和用户最新反馈为准，并记录差异。")

    doc.add_heading("九 当前验收门槛", level=1)
    add_table(
        doc,
        ["指标", "目标", "当前状态"],
        [
            ["基础意图准确率", "不低于 90%", "用户反馈约 90%，可进入下一阶段"],
            ["对抗样例准确率", "不低于 85%", "需通过批量脚本正式统计"],
            ["订单号提取准确率", "不低于 95%", "已有规则测试，需纳入统一测评"],
            ["低置信度工具误调用率", "0", "由 schema 门禁保障，需做集成测试"],
            ["未知意图工具误调用率", "0", "由 schema 门禁保障，需做集成测试"],
            ["缺必要字段工具误调用率", "0", "地址、投诉、工单场景需继续验证"],
        ],
        widths=[5.0, 4.0, 8.0],
    )

    doc.add_heading("十 交接时可直接使用的开场指令", level=1)
    doc.add_paragraph(
        "请读取 F:\\agent学习路径\\物流知识库\\电商物流智能客服项目进度与后续交付计划.docx，"
        "并结合 E:\\PythonProject5\\backend-lab 当前代码继续工作。当前意图识别人工测评约 90%，"
        "现在只做下一模块：Dify 输出校验与 Python 通用解析器。请先检查现有代码和测试，"
        "再说明本步准备修改的文件；完成后运行测试并汇报，等待我确认后才能进入批量评测。"
    )

    path = OUTPUT_DIR / "电商物流智能客服_项目进度与后续交付计划.docx"
    doc.save(path)
    return path


if __name__ == "__main__":
    first = create_intent_doc()
    second = create_handoff_doc()
    print(first)
    print(second)
