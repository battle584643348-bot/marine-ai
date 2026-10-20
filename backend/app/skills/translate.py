"""技能：海工技术文档中英互译。"""
from typing import Any, Dict

from .base import Skill

_GLOSSARY = [
    "soft starter 软起动器", "variable frequency drive (VFD) 变频器", "commissioning 调试",
    "inspection & test record (ITR) 检查与试验记录", "punch list 缺陷清单", "loop check 回路检查",
    "megger / insulation resistance test 绝缘电阻测试（摇表）", "earth fault 接地故障",
    "short-circuit 短路", "overcurrent 过电流", "differential protection 差动保护",
    "smart electronic device (IED) 智能电子装置", "protection relay 继电保护装置",
    "motor control centre (MCC) 电动机控制中心", "switchgear 开关柜", "breaker 断路器",
    "busbar 母线", "earthing 接地", "cable tray 电缆桥架", "junction box 接线箱",
    "thermocouple 热电偶", "RTD 铂电阻温度传感器", "transducer 变送器", "solenoid valve 电磁阀",
    "limit switch 限位开关", "pressure safety valve (PSV) 安全阀", "esd (emergency shutdown) 紧急关断",
    "fire & gas (F&G) system 火气系统", "hazardous area 危险区域", "Ex d / Ex e 隔爆/增安",
    "offshore platform 海上平台", "FPSO 浮式生产储卸油装置", "jacket 导管架",
    "topside 上部组块", "mooring 系泊", "riser 立管", "blue/yellow/red tag 蓝/黄/红标签",
]

_SYSTEM_ZH = (
    "你是海工船舶领域的专业中英翻译。要求：\n"
    "1. 术语准确，优先使用海工/船舶/电气调试行业惯用表达；\n"
    "2. 保持原文技术含义不变，不增删内容；\n"
    "3. 文档类内容保持分条结构；\n"
    "4. 仅输出译文，不解释、不添加前言。"
)
_SYSTEM_EN = (
    "You are a professional EN-ZH translator specialized in offshore/marine engineering and commissioning. "
    "Requirements: accurate terminology, preserve technical meaning, keep list/document structure, output only the translation."
)


class TranslateSkill(Skill):
    name = "translate"
    title = "中英技术翻译"
    description = (
        "海工/船舶/电气调试领域的技术文档中英互译（含术语表）。"
        "适合用户要求'翻译/中英对照'的场景。"
    )
    parameters = [
        {"name": "text", "type": "string", "description": "待翻译文本", "required": True},
        {"name": "target", "type": "string", "description": "目标语言：en（译成英文）或 zh（译成中文），默认自动判断", "required": False, "enum": ["en", "zh"]},
    ]

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        text = str(args.get("text", "")).strip()
        if not text:
            return {"type": "text", "content": "缺少待翻译文本（text）。"}
        target = str(args.get("target", "")).strip().lower()
        has_cjk = any("\u4e00" <= c <= "\u9fff" for c in text)
        if target not in ("en", "zh"):
            target = "en" if has_cjk else "zh"
        system = _SYSTEM_ZH if target == "zh" else _SYSTEM_EN
        user = f"翻译方向：{'英文→中文' if target == 'zh' else '中文→英文'}\n术语表（优先采用）：\n" + \
               "\n".join(_GLOSSARY) + "\n\n待翻译文本：\n" + text
        try:
            out = await ctx.llm_call(system, user, temperature=0.2)
        except Exception as e:  # noqa: BLE001
            return {"type": "text", "content": f"翻译失败（模型未配置或调用出错）：{e}"}
        return {"type": "text", "content": out.strip(), "meta": {"target": target}}
