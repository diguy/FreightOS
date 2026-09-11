from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


OUT = Path(r"E:\PythonProject5\backend-lab\deliverables")
OUT.mkdir(exist_ok=True)
FONT_CN = r"C:\Windows\Fonts\msyh.ttc"
FONT_EN = r"C:\Windows\Fonts\arial.ttf"


def set_font(run, size=10.5, bold=False, color=None):
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text, bold=False, color=None, size=9.5):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(text)
    set_font(r, size=size, bold=bold, color=color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def table_borders(table, color="B7C4D0"):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        elem = OxmlElement(f"w:{edge}")
        elem.set(qn("w:val"), "single")
        elem.set(qn("w:sz"), "6")
        elem.set(qn("w:color"), color)
        borders.append(elem)
    tbl_pr.append(borders)


def add_title(doc, title, subtitle=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(title)
    set_font(r, size=20, bold=True, color=(31, 78, 121))
    if subtitle:
        p2 = doc.add_paragraph()
        p2.paragraph_format.space_after = Pt(12)
        r2 = p2.add_run(subtitle)
        set_font(r2, size=10.5, color=(89, 89, 89))


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(11 if level == 1 else 7)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_font(r, size=14 if level == 1 else 11.5, bold=True,
             color=(31, 78, 121) if level == 1 else (55, 55, 55))
    return p


def add_body(doc, text, indent=0, bold_lead=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.22
    p.paragraph_format.left_indent = Cm(indent)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        set_font(r, bold=True)
        r = p.add_run(text[len(bold_lead):])
        set_font(r)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(item)
        set_font(r)


def setup_doc(doc):
    sec = doc.sections[0]
    sec.top_margin = Cm(1.7)
    sec.bottom_margin = Cm(1.7)
    sec.left_margin = Cm(1.8)
    sec.right_margin = Cm(1.8)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)


def build_spec():
    doc = Document()
    setup_doc(doc)
    add_title(doc, "AIA Agent Chatbot 工作流程说明书",
              "根据原始“友邦”流程材料整理；保留原有业务规则、术语与示例，并按实际执行顺序重组。")

    add_heading(doc, "1. 文档目的与范围")
    add_body(doc, "本文件描述 AIA Agent Chatbot 的端到端工作流，包括用户咨询、意图路由、子机器人问答、知识库检索、Fallback、人工转接、CRM Case 创建与关闭。")
    add_body(doc, "说明：原始材料中的“Plain Text”“---”“...”多为白板/界面标记或分隔符，已改为清晰的正文结构；业务含义、条件、示例与字段均予保留。")

    add_heading(doc, "2. 整体架构")
    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table_borders(table)
    headers = ["组件", "职责", "主要覆盖内容 / 数据来源"]
    for i, text in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], text, bold=True, color=(255, 255, 255))
        shade(table.rows[0].cells[i], "1F4E79")
    rows = [
        ("User (Agent)", "打开 Chat Widget、提问、评分、选择人工服务主题、补充资料。", "7×24 小时可访问 Chat Widget。"),
        ("Main Bot", "接收问题、发送欢迎语、识别意图、路由 Sub Bot、回复用户、控制转人工、创建 CRM Case。", "Intent Routing；Fallback；Live Chat / Open Case 分流。"),
        ("Orchestrator", "执行用户意图编排与领域判断。", "判断问题属于 Operations/Servicing 或 Agency。"),
        ("Sub Bot 1 - Operations/Servicing", "处理保单服务问题并返回答案。", "Claim、Payment、Policy、POS、Autopay；FAQ、KB、API。"),
        ("Sub Bot 2 - Agency AI", "处理代理人业务问题并返回答案。", "AIA ONE、iRecruit、MDRT、Product、Competition、Secretary Topics。"),
        ("KMS / Knowledge Base", "提供问答检索基础。", "FAQ、KB Document、API；ADP KB、DS KB、AGM KB、MKT KB、Health KB 等。"),
        ("Omnichannel / CRM", "承接人工队列、人工聊天，以及 Open/Closed Case 记录。", "Chat History、User Information、Context、Case 字段与邮件通知。"),
    ]
    for component, role, scope in rows:
        cells = table.add_row().cells
        set_cell_text(cells[0], component, bold=True)
        set_cell_text(cells[1], role)
        set_cell_text(cells[2], scope)

    add_heading(doc, "3. 端到端流程概览")
    add_body(doc, "用户打开 Chat Widget后，Main Bot 发送欢迎语并接收问题。Orchestrator 根据意图将问题路由至 Operations/Servicing 或 Agency AI 子机器人；子机器人从相应知识来源检索并返回答案。")
    add_body(doc, "若无法回答，则返回 Fallback/default answer；当满足连续 Fallback、用户主动联系人工、点踩或负面情绪等条件时，进入人工服务分流。人工服务根据主题、Live Chat 范围、工作时间及是否允许 Open Case，分别进入 Omnichannel、提供联系信息、创建 Open Case 或返回固定文案。")

    phases = [
        ("4. 第一阶段：用户进入聊天", [
            "Step 1：用户打开 Chat Widget（Open chat widget，7×24 小时可访问）。",
            "入口动作：Open Widget → Welcome。"
        ]),
        ("5. 第二阶段：欢迎语与意图识别", [
            "Step 2：Main Bot 发送 Welcome Message，例如 “How can I help?”。",
            "Step 3：用户输入问题，例如 “What is claim status?”；进入 “Ask a Question”。",
            "Step 4：Main Bot / Orchestrator 执行 “Orchestrate user intent”，这是全流程最关键的判断步骤。",
            "领域判断示例：How do I submit claim? → Servicing Agent；What is MDRT? → Agency AI；Hello → Agency AI（原材料说明 Secretary Topics 属于 Agency）。"
        ]),
        ("6. 第三阶段：调用 Sub Bot 与知识检索", [
            "Step 5：Main Bot 执行 Route Question，将问题发送至对应 Sub Bot。",
            "情况 A - Sub Bot 1（Operations/Servicing）：understand question and provide answer；使用 FAQ、KB、API。示例：Claim Status 可调用 API。",
            "情况 B - Sub Bot 2（Agency AI）：understand question and provide answer；使用 ADP KB、DS KB、AGM KB、MKT KB、Health KB、BQM KB、Persist. KB、XX KB、YY KB 等知识库。",
            "KMS 知识来源包括 FAQ、KB Document、API；上述知识库是实际问答检索基础。"
        ]),
        ("7. 第四阶段：答案返回", [
            "Step 6：Sub Bot 返回结果（Get Info From Sub Bot）。示例：How to use AIA ONE 从 KB 检索答案。",
            "Step 7：Main Bot 回复用户（Answer）。返回内容包含 Answer Content、Citation、Flag；界面可展示答案、来源和链接。",
            "用户得到答案后可继续提问、确认答案，或关闭聊天。原白板中 “Confirm answer is acceptable” 与 “Confirm ask again” 标记为待确认项，未作为强制步骤。"
        ]),
        ("8. 第五阶段：Fallback 流程", [
            "当无法回答时，进入 Return with fallback / default answer。",
            "Fallback 触发原因：No knowledge to provide answer（知识库无内容）；Bot cannot understand user intent（意图无法识别）；confidence score low（相似度/置信度过低）。",
            "返回内容：Default Answer。"
        ]),
        ("9. 第六阶段：触发转人工", [
            "任一触发条件满足时，提供/开放 “contact staff” 选项：连续 3 次 Fallback/default answer；用户点踩（Thumb Down）；用户明确说 Contact staff / Speak to human / Contact urgently；LLM 识别到 Anger、Anxiety、Strong dissatisfaction、Urgent help 等负面或紧急情绪。",
            "转人工入口：Select “contact staff”。"
        ]),
        ("10. 第七阶段：人工服务 Topic 选择", [
            "Bot 提问：Which topic do you need to contact staff?",
            "用户可选择：Premium Payment、Claims、New Business、Policy Data Change、Other Operations、Others。"
        ]),
        ("11. 第八阶段：Live Chat 范围判断", [
            "判断：Is in Scope Live Chat?",
            "允许进入 Live Chat：Premium Payment、Claims、New Business、Policy Data Change、Other Operations。",
            "不允许进入 Live Chat：Others，例如 MDRT、Competition、Recruitment。此时 Provide Contact Info，直接提供电话/各主题联系信息，不进入人工队列。"
        ]),
        ("12. 第九至十阶段：工作时间内的人工服务", [
            "若属于 Live Chat Scope，判断 Is it in working hour? 原材料给出的工作时间为 Mon-Fri，08:30-17:00。",
            "工作时间内：Request CSAT → 用户 Rate CSAT score → Transfer to Omnichannel → In Queue → CSR 接单 → Chat with Staff。",
            "CRM 在人工接手时应可查看 Chat History、User Information、Context。",
            "队列按所选主题分流：Premium Payment / Claims / Policy Service → Agency queue（CSM team）；New Business / Policy Data Change → BackendTeam queue（Customer+Service）。"
        ]),
        ("13. 第十一阶段：Visitor Drop Out", [
            "若用户在队列中关闭窗口、离开 Queue，或 300 秒无响应，则按 Visitor Drop Out 处理。",
            "原白板的 use case category 映射：Premium Payment、Claims、New Business、Policy Data Change、Policy Service。",
            "Closed Case Sub Category：Visitor Drop Out。"
        ]),
        ("14. 第十二至十三阶段：非工作时间与 Open Case", [
            "非工作时间（Out of Service Hour）：对 Premium Payment、Claims、Other Operations 等主题返回固定文案，例如 “Currently out of service hours”；随后结束本次服务。",
            "进入 “Is topic to create open case?” 判断。仅 New Business 与 Policy Data Change 允许创建 Open Case。",
            "YES：Bot 收集 Policy No. 与 Leave Message，创建 Open Case；CRM 记录 Policy No.、Leave Message，并向 Back Office 发送邮件。邮件同时携带 Agent Name、Agent Email、Policy No.、Message。",
            "NO：Premium Payment、Claims、Other Operations 等主题返回固定消息（Fixed Message），并提供该主题联系信息。"
        ]),
        ("15. 第十四至十五阶段：Auto Create Closed Case", [
            "无论是否已转人工，当用户 Close Chat 或出现 300 秒 Idle，都会触发 Auto Create Closed Case。",
            "CRM 记录：Case Type = Chatbot；Status = Closed；Subcategory = Answer by Chat Bot。",
            "如属于 Visitor Drop Out，Closed Case 的 Sub Category 为 Visitor Drop Out。"
        ]),
    ]
    for heading, bullets in phases:
        add_heading(doc, heading)
        add_bullets(doc, bullets)

    add_heading(doc, "16. 关键规则速查")
    quick = doc.add_table(rows=1, cols=2)
    quick.style = "Table Grid"
    table_borders(quick)
    for cell, text in zip(quick.rows[0].cells, ["规则", "处理结果"]):
        set_cell_text(cell, text, bold=True, color=(255, 255, 255))
        shade(cell, "1F4E79")
    for left, right in [
        ("可回答", "Sub Bot 返回结果，Main Bot 回复 Answer（含 Answer Content / Citation / Flag）。"),
        ("无法回答", "Fallback/default answer；原因包括知识库无内容、意图无法识别、置信度低。"),
        ("转人工触发", "连续 3 次 Fallback、点踩、明确要求人工、负面/紧急情绪。"),
        ("不属于 Live Chat", "Provide Contact Info；不进入人工队列。"),
        ("工作时间内", "CSAT → Omnichannel → Queue → CSR → Chat with Staff。"),
        ("非工作时间", "固定 out-of-service 文案；按主题判断是否创建 Open Case。"),
        ("允许创建 Open Case", "仅 New Business、Policy Data Change；收集 Policy No. / Leave Message，建单并邮件通知。"),
        ("关闭聊天或 300 秒 idle", "Auto Create Closed Case；默认 Subcategory = Answer by Chat Bot。"),
    ]:
        cells = quick.add_row().cells
        set_cell_text(cells[0], left, bold=True)
        set_cell_text(cells[1], right)

    path = OUT / "友邦_AIA_Chatbot流程说明书_整理版.docx"
    doc.save(path)
    return path


class Flowchart:
    def __init__(self):
        self.im = Image.new("RGB", (6600, 3900), "white")
        self.d = ImageDraw.Draw(self.im)
        self.fonts = {
            "title": ImageFont.truetype(FONT_CN, 54),
            "lane": ImageFont.truetype(FONT_CN, 34),
            "box": ImageFont.truetype(FONT_CN, 26),
            "small": ImageFont.truetype(FONT_CN, 21),
            "note": ImageFont.truetype(FONT_CN, 20),
        }
        self.colors = {
            "user": "#D9B47A", "main": "#5BA6D5", "ops": "#68A978",
            "agency": "#C7868A", "kms": "#AF78B1", "human": "#E4C469",
            "note": "#D67C72", "line": "#4A4A4A", "bg": "#F7FAFC",
        }

    def text_box(self, xy, text, fill, font="box", radius=8, outline="#5A5A5A", align="center"):
        x1, y1, x2, y2 = xy
        self.d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=4)
        f = self.fonts[font]
        lines = []
        for line in text.split("\n"):
            lines.extend(line.split("|"))
        heights = [self.d.textbbox((0, 0), line, font=f)[3] for line in lines]
        total = sum(heights) + max(0, len(lines) - 1) * 5
        y = (y1 + y2 - total) / 2
        for line, h in zip(lines, heights):
            bbox = self.d.textbbox((0, 0), line, font=f)
            if align == "left":
                x = x1 + 12
            else:
                x = (x1 + x2 - (bbox[2] - bbox[0])) / 2
            self.d.text((x, y), line, fill="#111111", font=f)
            y += h + 5

    def diamond(self, cx, cy, w, h, text):
        pts = [(cx, cy - h // 2), (cx + w // 2, cy), (cx, cy + h // 2), (cx - w // 2, cy)]
        self.d.polygon(pts, fill=self.colors["main"], outline=self.colors["line"])
        self.d.line(pts + [pts[0]], fill=self.colors["line"], width=4)
        f = self.fonts["small"]
        lines = text.split("\n")
        total = sum(self.d.textbbox((0, 0), l, font=f)[3] for l in lines) + (len(lines) - 1) * 3
        y = cy - total / 2
        for line in lines:
            bb = self.d.textbbox((0, 0), line, font=f)
            self.d.text((cx - (bb[2] - bb[0]) / 2, y), line, font=f, fill="#111111")
            y += bb[3] + 3

    def arrow(self, start, end, label=None, color="#4A4A4A", width=5):
        self.d.line([start, end], fill=color, width=width)
        x1, y1 = start
        x2, y2 = end
        if abs(x2 - x1) >= abs(y2 - y1):
            pts = [(x2, y2), (x2 - 20 if x2 > x1 else x2 + 20, y2 - 11), (x2 - 20 if x2 > x1 else x2 + 20, y2 + 11)]
        else:
            pts = [(x2, y2), (x2 - 11, y2 - 20 if y2 > y1 else y2 + 20), (x2 + 11, y2 - 20 if y2 > y1 else y2 + 20)]
        self.d.polygon(pts, fill=color)
        if label:
            f = self.fonts["small"]
            bb = self.d.textbbox((0, 0), label, font=f)
            self.d.rectangle(((x1 + x2) / 2 - 5, (y1 + y2) / 2 - 4,
                              (x1 + x2) / 2 + bb[2] - bb[0] + 5, (y1 + y2) / 2 + bb[3] + 4), fill="white")
            self.d.text(((x1 + x2) / 2, (y1 + y2) / 2), label, font=f, fill="#222222")

    def elbow(self, points, label=None, color="#4A4A4A"):
        for a, b in zip(points, points[1:]):
            self.d.line([a, b], fill=color, width=5)
        self.arrow(points[-2], points[-1], label=label, color=color)

    def note(self, xy, text):
        self.text_box(xy, text, self.colors["note"], font="note", radius=2)

    def draw(self):
        d = self.d
        d.rectangle((0, 0, 6600, 3900), fill=self.colors["bg"])
        d.rectangle((0, 0, 6600, 100), fill="#8B1E2D")
        d.text((110, 25), "AIA Agent Chatbot - End-to-End Workflow", font=self.fonts["title"], fill="white")
        d.text((4400, 36), "Rebuilt from Whiteboard screenshots + source workflow", font=self.fonts["small"], fill="white")

        # Swimlane labels and dividers, mirroring the source whiteboard.
        lane_y = [500, 920, 1340, 1760, 2180, 2680]
        labels = [
            ("User\n(Agent)", "user"), ("Main Bot", "main"), ("Sub Bot 1\nOperations", "ops"),
            ("Sub Bot 2\nAgency", "agency"), ("KMS\n(QA + Document)", "kms"), ("Omnichannel / CRM", "human")
        ]
        for y, (label, color) in zip(lane_y, labels):
            self.text_box((80, y - 65, 410, y + 65), label, self.colors[color], font="lane")
            d.line((450, y, 6500, y), fill="#C7D1DA", width=3)
        d.line((450, 350, 450, 3650), fill="#778899", width=5)

        # Core question/answer flow.
        self.text_box((620, 430, 920, 570), "Open chat widget\n(24/7)", self.colors["user"])
        self.text_box((620, 850, 920, 990), "Welcome\nmessage", self.colors["main"])
        self.text_box((1050, 430, 1380, 570), "Ask a question", self.colors["user"])
        self.text_box((1050, 850, 1380, 1000), "Orchestrate\nuser intent", self.colors["main"])
        self.diamond(1570, 925, 260, 180, "Can get info\nfrom Sub Bot?")
        self.text_box((1760, 850, 2070, 1000), "Answer", self.colors["main"])
        self.text_box((2160, 850, 2550, 1000), "Return with fallback\n/ default answer", self.colors["main"])
        self.arrow((770, 570), (770, 850))
        self.arrow((920, 920), (1050, 920))
        self.arrow((1215, 570), (1215, 850))
        self.arrow((1380, 925), (1440, 925))
        self.arrow((1700, 925), (1760, 925), "Yes")
        self.arrow((2070, 925), (2160, 925))
        self.arrow((2300, 850), (2300, 570), "continue / ask again")

        # Sub bots and knowledge bases.
        self.text_box((1050, 1270, 1410, 1440), "understand question\nand provide answer", self.colors["ops"])
        self.text_box((820, 1690, 1180, 1860), "understand question\nand provide answer", self.colors["agency"])
        self.elbow([(1500, 1015), (1500, 1355), (1410, 1355)], "Operations")
        self.elbow([(1130, 1015), (1130, 1775), (1180, 1775)], "Agency")
        ops_kms = ["FAQ", "KB", "API"]
        for i, item in enumerate(ops_kms):
            self.text_box((1010 + i * 145, 2080, 1135 + i * 145, 2175), item, self.colors["kms"], font="small")
            self.arrow((1130 + i * 145, 1440), (1070 + i * 145, 2080), color="#66806F", width=3)
        kb_names = ["ADP\nKB", "DS\nKB", "AGM\nKB", "MKT\nKB", "Health\nKB", "BQM\nKB", "Persist.\nKB", "XX\nKB", "YY\nKB", "Operations\nKB"]
        xs = [780, 970, 1160, 1350, 1540, 780, 970, 1160, 1350, 1540]
        ys = [2420] * 5 + [2580] * 5
        for name, x, y in zip(kb_names, xs, ys):
            self.text_box((x, y, x + 145, y + 110), name, self.colors["kms"], font="small")
        self.elbow([(1000, 1860), (1000, 2330), (860, 2330), (860, 2420)], color="#9B637D")
        self.elbow([(1000, 1860), (1000, 2330), (1600, 2330), (1600, 2420)], color="#9B637D")
        self.note((1860, 1170, 2510, 1410),
                  "Fallback reasons:\n- No knowledge to provide answer\n- Bot cannot understand user intent\n- confidence score = low")

        # Closed-case trigger at top.
        self.text_box((2750, 430, 3100, 570), "Auto create\nclosed case on CRM", self.colors["main"])
        self.note((3160, 355, 3840, 665),
                  "Trigger point of auto-create closed case on CRM:\nAfter bot response, when user exits without handover to human\nor idle timeout = 300 sec.\n\nCRM: Case Type = Chatbot; Status = Closed;\nSubcategory = Answer by Chat Bot")
        self.arrow((2550, 500), (2750, 500))

        # Handover flow.
        self.text_box((2760, 430, 3100, 570), "Auto create\nclosed case on CRM", self.colors["main"])
        self.text_box((2750, 850, 3110, 1000), "Select\n\"contact staff\"", self.colors["user"])
        self.note((3180, 790, 3860, 1060),
                  "Trigger point of handover to human agent:\n(1) Fallback/default answer for 3 times;\n(2) user taps thumb down;\n(3) Contact staff / Speak to human / urgent need;\n(4) negative emotion or dissatisfaction.")
        self.text_box((4040, 850, 4450, 1020), "Ask \"Which topic\ndo you need to\ncontact staff?\"", self.colors["main"])
        self.diamond(4660, 935, 280, 190, "Is in scope\nLive Chat?")
        self.diamond(5060, 935, 300, 190, "Is it in working hour\nof Omnichannel?")
        self.text_box((5460, 850, 5750, 1020), "Request\nCSAT score", self.colors["main"])
        self.text_box((5840, 850, 6130, 1020), "Transfer to\nOmnichannel", self.colors["main"])
        self.text_box((5840, 1110, 6130, 1250), "In queue", self.colors["human"])
        self.text_box((5840, 1340, 6170, 1480), "Chat with staff\nas usual", self.colors["user"], radius=70)
        self.arrow((3110, 925), (4040, 925))
        self.arrow((4450, 935), (4520, 935))
        self.arrow((4800, 935), (4910, 935), "Yes")
        self.arrow((5210, 935), (5460, 935), "Yes")
        self.arrow((5750, 935), (5840, 935))
        self.arrow((5985, 1020), (5985, 1110))
        self.arrow((5985, 1250), (5985, 1340))
        self.elbow([(4660, 1030), (4660, 1590), (4140, 1590)], "No")
        self.text_box((3880, 1520, 4410, 1660), "Provide contact info.\nfor each topic", self.colors["main"])
        self.text_box((4550, 1520, 5020, 1660), "Out of service hours:\nfixed message", self.colors["main"])
        self.elbow([(5060, 1030), (5060, 1590), (4790, 1590)], "No")

        # Topics and scope note.
        self.note((4030, 1120, 5050, 1420),
                  "Select Topic:\n1. Premium Payment\n2. Claims\n3. New Business\n4. Policy Data Change\n5. Other Operations\n6. Others\n\nLive Chat Scope: 1-5 only.\nOthers (e.g. MDRT / Competition / Recruitment)\n→ provide contact info, no human queue.")

        # Open case flow.
        self.diamond(4680, 1850, 290, 200, "Is topic set\nto create\nopen case?")
        self.text_box((5050, 1780, 5390, 1930), "Response with\nfixed message", self.colors["main"])
        self.text_box((5510, 1780, 5900, 1930), "Bot request info.\nfor callback", self.colors["main"])
        self.text_box((6020, 1780, 6320, 1930), "Provide info.\nPolicy No. + message", self.colors["user"])
        self.text_box((5510, 2070, 6260, 2230),
                      "1. Response user\n2. Auto-create open case on CRM\n3. Send email to agent / Back Office",
                      self.colors["main"], font="small")
        self.arrow((4680, 1950), (5050, 1850), "No")
        self.arrow((4825, 1850), (5510, 1850), "Yes")
        self.arrow((5900, 1850), (6020, 1850))
        self.arrow((6170, 1930), (6170, 2070))
        self.note((4400, 2170, 5310, 2370),
                  "Topic to create Open Case:\n- New Business\n- Policy Data Change\n\nOther topics → fixed message + topic contact info.")

        # Queues and visitor drop out.
        self.text_box((620, 3050, 1000, 3180), "Queue depends on\nselected topic", self.colors["human"])
        self.diamond(2140, 3115, 320, 190, "Topic = PMC /\nClaim / POS?")
        self.text_box((2500, 3020, 2900, 3180), "Agency queue\n(CSM team)", self.colors["human"], radius=65)
        self.text_box((2500, 3310, 2950, 3470), "BackendTeam queue\n(Customer + Service)", self.colors["human"], radius=65)
        self.arrow((1000, 3115), (1980, 3115))
        self.elbow([(2300, 3050), (2500, 3100)], "Premium Payment / Claims / Policy Service")
        self.elbow([(2140, 3210), (2140, 3390), (2500, 3390)], "New Business / Policy Data Change")
        self.note((3000, 3020, 3770, 3290),
                  "Visitor Drop Out:\nIn queue, user closes window / leaves queue\nor idle for 300 sec.\nClosed Case Sub Category = Visitor Drop Out.\n\nCRM handover context: Chat History,\nUser Information, Context.")

        # Connector annotations.
        self.elbow([(2550, 925), (2750, 925)], color="#4A4A4A")
        self.elbow([(4410, 1660), (4410, 1850), (4535, 1850)], color="#4A4A4A")
        d.text((480, 3650), "Legend: User / Main Bot / Operations Sub Bot / Agency Sub Bot / KMS / Omnichannel-CRM", font=self.fonts["small"], fill="#555555")
        d.text((4300, 3650), "Core rules preserved from source document; whiteboard screenshot styling recreated as a unified map.", font=self.fonts["small"], fill="#555555")
        return self.im


def build_flowchart_doc():
    chart = Flowchart()
    image_path = OUT / "AIA_Chatbot完整流程图.png"
    chart.draw().save(image_path, quality=96)

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width = Cm(42.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(0.8)
    sec.bottom_margin = Cm(0.8)
    sec.left_margin = Cm(1.0)
    sec.right_margin = Cm(1.0)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("AIA Agent Chatbot 完整流程图")
    set_font(r, size=16, bold=True, color=(31, 78, 121))
    p.paragraph_format.space_after = Pt(4)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run("按白板照片的泳道、颜色和横向节点布局重绘，并用“友邦”流程规则补齐断开部分。")
    set_font(r2, size=9.5, color=(89, 89, 89))
    p2.paragraph_format.space_after = Pt(3)
    doc.add_picture(str(image_path), width=Cm(39.5))
    path = OUT / "友邦_AIA_Chatbot完整流程图_重绘版.docx"
    doc.save(path)
    return path, image_path


if __name__ == "__main__":
    spec = build_spec()
    flow, png = build_flowchart_doc()
    print(spec)
    print(flow)
    print(png)
