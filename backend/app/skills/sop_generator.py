"""技能：调试程序（SOP）/ 检查与试验程序（ITR）起草。"""
from typing import Any, Dict

from .base import Skill

_SYSTEM = (
    "你是一名资深海工船舶调试工程师，负责编写海洋工程/船舶项目的设备调试程序（Commissioning Procedure / SOP）"
    "与检查与试验程序（Inspection & Test Record, ITR）。"
    "输出要求：\n"
    "1. 使用专业的海工船舶调试书面语，语言为英文时符合国际项目文档习惯（句式精炼、被动语态、术语准确），中文时规范严谨；\n"
    "2. 结构清晰、步骤可执行、含具体验收标准（最好给出数值/判据）与安全注意事项；\n"
    "3. 涉及标准的条款不要编造，写标准号与适用章节主题即可，并注明'以最新官方版本为准'；\n"
    "4. 项目特定信息（船名/项目号/设备名牌参数）用户未提供时用【待填】占位并单独说明，不编造具体数值；\n"
    "5. 直接输出文档正文（Markdown），不要额外解释。"
)


class SopGeneratorSkill(Skill):
    name = "sop_generator"
    title = "调试程序 / SOP 生成"
    description = (
        "按海工行业规范模板生成设备调试程序（SOP）、检查与试验程序（ITR）、操作程序等工程文档草稿。"
        "适合用户说'帮我写一份XX的调试程序/SOP/ITR'的场景。"
    )
    parameters = [
        {"name": "topic", "type": "string", "description": "设备/系统名称，如 '低压电动机软起动器'、'中压断路器'", "required": True},
        {"name": "language", "type": "string", "description": "输出语言：zh（中文）或 en（英文），默认 zh", "required": False, "enum": ["zh", "en"]},
        {"name": "project", "type": "string", "description": "项目名/船名/FPSO名等，可选", "required": False},
        {"name": "extra", "type": "string", "description": "补充要求：关注点、设备规格、标准要求等，可选", "required": False},
    ]

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        topic = str(args.get("topic", "")).strip()
        if not topic:
            return {"type": "text", "content": "缺少主题（topic），例如：低压电动机软起动器。"}
        lang = str(args.get("language", "zh")).lower()
        project = str(args.get("project", "")).strip()
        extra = str(args.get("extra", "")).strip()

        template = _build_template(lang, topic, project, extra)
        try:
            doc = await ctx.llm_call(_SYSTEM, template, temperature=0.3)
        except Exception as e:  # noqa: BLE001
            return {"type": "text", "content": f"生成失败（模型未配置或调用出错）：{e}"}
        doc = doc.strip()
        return {"type": "text", "content": doc, "meta": {"kind": "SOP", "language": lang}}


def _build_template(lang: str, topic: str, project: str, extra: str) -> str:
    zh = lang == "zh"
    head = f"项目：{project or '【待填】'}；主题：{topic}"
    if extra:
        head += f"；补充要求：{extra}"
    if zh:
        return head + "\n请按以下章节结构起草调试程序：\n" + "\n".join([
            "1 目的（Purpose）",
            "2 适用范围（Scope）",
            "3 参考文件（References：厂家手册、IEC/IEEE/GB 相关标准号，注明以最新版本为准）",
            "4 术语与缩写（Terms & Abbreviations）",
            "5 安全注意事项（Safety Precautions：隔离、上锁挂牌LOTO、放电、验电、风险评估）",
            "6 前置条件（Preconditions：供电可用、图纸齐全、仪器校准有效、人员资质）",
            "7 工具与仪器（Tools & Instruments：含量程/精度要求）",
            "8 调试步骤（Commissioning Steps：逐条编号、可操作、含设定值与动作判据）",
            "9 验收标准（Acceptance Criteria：明确数值/状态判据）",
            "10 记录表格（Records：测试记录表样式）",
            "11 异常处理与故障排查（Troubleshooting）",
        ])
    return head + "\nPlease draft the commissioning procedure with the following structure:\n" + "\n".join([
        "1 Purpose", "2 Scope", "3 References (manufacturer manuals, IEC/IEEE/GB standard numbers; note 'latest official version prevails')",
        "4 Terms & Abbreviations", "5 Safety Precautions (isolation, LOTO, discharge, voltage verification, risk assessment)",
        "6 Preconditions (power available, drawings approved, calibrated instruments, qualified personnel)",
        "7 Tools & Instruments (with range/accuracy requirements)",
        "8 Commissioning Steps (numbered, actionable, with setpoints and judgment criteria)",
        "9 Acceptance Criteria (quantified where possible)",
        "10 Records (test record forms)",
        "11 Troubleshooting & Exception Handling",
    ])
