"""技能：确定性工程计算引擎（电压降/电缆选型/谐波/无功补偿/软起动/谐振）。

所有计算为确定性公式，输入参数由用户提供；结果附公式、计算过程与校核结论。
"""
import math
from typing import Any, Dict

from .base import Skill

_STD_SIZES = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]
_RHO = {"copper": 0.0185, "aluminium": 0.0310}  # Ω·mm²/m（约 75℃ 工作温度）


def _num(args, key, default=None) -> float | None:
    v = args.get(key, default)
    if v in (None, "", "null"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _md_table(headers, rows):
    s = "| " + " | ".join(headers) + " |\n|" + "---|" * len(headers) + "\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


class CalcEngineSkill(Skill):
    name = "calc_engine"
    title = "工程计算引擎"
    description = (
        "确定性工程计算，支持：voltage_drop 电压降校核、cable_area 电缆截面选型、harmonic_thd 谐波畸变率(THD)计算与限值校核、"
        "power_factor 功率因数与无功补偿、soft_starter 软起动器起动校核、resonance 电容器/变压器谐振频率评估。"
        "输入 calc_type 与 params，返回公式、计算过程、结果表与结论。"
    )
    parameters = [
        {"name": "calc_type", "type": "string", "required": True,
         "enum": ["voltage_drop", "cable_area", "harmonic_thd", "power_factor", "soft_starter", "resonance"],
         "description": "计算类型"},
        {"name": "params", "type": "object", "required": True, "description": "计算参数对象，见各类型说明"},
    ]

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        calc_type = str(args.get("calc_type", "")).strip()
        params = args.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        fn = {
            "voltage_drop": self._voltage_drop,
            "cable_area": self._cable_area,
            "harmonic_thd": self._harmonic_thd,
            "power_factor": self._power_factor,
            "soft_starter": self._soft_starter,
            "resonance": self._resonance,
        }.get(calc_type)
        if not fn:
            return {"type": "text",
                    "content": f"不支持的计算类型：{calc_type}。可选：{', '.join(['voltage_drop','cable_area','harmonic_thd','power_factor','soft_starter','resonance'])}"}
        return fn(params)

    # ------------------------------------------------ 电压降
    def _voltage_drop(self, p) -> Dict[str, Any]:
        I = _num(p, "current"); L = _num(p, "length"); U = _num(p, "voltage", 400)
        phase = str(p.get("phase", "3"))
        cosf = _num(p, "cos_phi", 0.85)
        area = _num(p, "cable_area_mm2")
        R = _num(p, "R_ohm_per_km")
        X = _num(p, "X_ohm_per_km", 0.08)
        cond = str(p.get("conductor", "copper"))
        missing = []
        if I is None: missing.append("current(负载电流A)")
        if L is None: missing.append("length(电缆长度m)")
        if area is None and R is None: missing.append("cable_area_mm2 或 R_ohm_per_km(二者必填其一)")
        if missing:
            return {"type": "text", "content": "参数缺失：" + "、".join(missing)}

        if R is None:
            R = _RHO.get(cond, _RHO["copper"]) * 1000 / area
        sinf = math.sqrt(max(0.0, 1 - cosf * cosf))
        k = math.sqrt(3) if phase == "3" else 2.0
        dV = k * I * L * (R * cosf + X * sinf) / 1000.0
        dVpct = dV / U * 100
        Rline = k * L * R / 1000.0
        Xline = k * L * X / 1000.0
        rows = [
            ["相制", "√3（三相）/ 2（单相）", k],
            ["负载电流 I", "A", I],
            ["线路长度 L", "m", L],
            ["单位电阻 R", "Ω/km", round(R, 5)],
            ["单位电抗 X", "Ω/km", X],
            ["cos φ", "—", cosf],
            ["线路压降 ΔV", "V", round(dV, 2)],
            ["压降百分比", "%", round(dVpct, 2)],
        ]
        content = (
            "### 电压降计算\n\n**公式**：三相 ΔV = √3·I·L·(R·cosφ + X·sinφ) / 1000；单相 ΔV = 2·I·L·(R·cosφ + X·sinφ) / 1000\n\n"
            + _md_table(["项目", "单位", "数值"], rows)
            + f"\n**结论**：线路压降 **{round(dV, 2)} V（{round(dVpct, 2)}%）**。"
        )
        if dVpct > 3:
            content += " 超过 3% 的常见配电要求，建议加大截面或缩短路径。"
        else:
            content += " 满足 3% 以内的常见配电要求。"
        content += "\n> 注：X 对低压小截面影响小，精确计算请使用电缆厂商数据。"
        return {"type": "text", "content": content}

    # ------------------------------------------------ 电缆截面
    def _cable_area(self, p) -> Dict[str, Any]:
        I = _num(p, "current"); L = _num(p, "length"); U = _num(p, "voltage", 400)
        phase = str(p.get("phase", "3"))
        cosf = _num(p, "cos_phi", 0.85)
        pct = _num(p, "vdrop_pct_allowed", 3)
        cond = str(p.get("conductor", "copper")).lower()
        missing = []
        if I is None: missing.append("current")
        if L is None: missing.append("length")
        if missing:
            return {"type": "text", "content": "参数缺失：" + "、".join(missing)}
        rho = _RHO.get(cond, _RHO["copper"])
        dV_allow = U * pct / 100.0
        k = math.sqrt(3) if phase == "3" else 2.0
        A = k * I * L * rho * cosf / dV_allow
        suggest = [s for s in _STD_SIZES if s >= A]
        suggest = suggest[0] if suggest else _STD_SIZES[-1]
        rows = [["计算最小截面 A", "mm²", round(A, 2)],
                ["建议标准截面", "mm²", suggest],
                ["允许压降 ΔV", "V", round(dV_allow, 2)]]
        content = (
            f"### 电缆截面选型（{cond}，按压降）\n\n"
            "**公式**：A = k·I·L·ρ·cosφ / ΔV，其中 k=√3（三相）/2（单相），ρ="
            f"{rho} Ω·mm²/m\n\n" + _md_table(["项目", "单位", "数值"], rows) +
            f"\n**结论**：按 {pct}% 允许压降，最小截面 {round(A, 2)} mm²，工程取标准截面 **{suggest} mm²**。\n"
            "> 校核提示：1) 载流量需按 IEC 60364-5-52 敷设方式（空气中/桥架/穿管、环境温度）查表校核；"
            "2) 短路热稳定按 IEC 60364-5-54 校核；3) 长电缆还需校核电机端子电压降满足起动要求。"
        )
        return {"type": "text", "content": content}

    # ------------------------------------------------ 谐波
    def _harmonic_thd(self, p) -> Dict[str, Any]:
        harmonics = p.get("harmonics")
        if not isinstance(harmonics, list) or not harmonics:
            return {"type": "text", "content": "参数缺失：harmonics=[{order, percent}, ...]，percent 为相对基波的百分比幅值。"}
        rows, s2 = [], 0.0
        for h in harmonics:
            order = int(h.get("order", 0)); percent = float(h.get("percent", 0))
            if order <= 0: continue
            rows.append([order, round(percent, 2), f"IHD{order}={percent:.2f}%"])
            s2 += percent * percent
        thd = math.sqrt(s2)
        worst = max(rows, key=lambda r: r[1]) if rows else None
        limit_v = 5.0
        content = (
            "### 谐波畸变率计算\n\n"
            "**公式**：THD = √(Σ hᵢ²) / h₁ × 100%，hᵢ 为各次谐波相对基波的幅值百分比\n\n"
            + _md_table(["谐波次数", "幅值 %", "单次畸变 IHD"], rows)
            + f"\n**THD = {round(thd, 2)}%**"
        )
        verdict = []
        if worst:
            verdict.append(f"最大单次谐波：{worst[2]}（{worst[0]} 次）")
        verdict.append(f"电压 THD 限值：IEEE 519（<69kV PCC）≤ 5%、单次 ≤ 3%；GB/T 14549（380V）电压 THD ≤ 5%、奇次 ≤ 4%、偶次 ≤ 2%")
        passed = thd <= limit_v and (worst is None or worst[1] <= 3.0)
        verdict.append("**结论：" + ("满足" if passed else "超出") + " IEEE 519 电压 THD 限值（5%）。若超限，建议评估谐波源治理（加装滤波/调谐电抗、调整变频器载波等）。**")
        content += "\n\n" + "\n".join(f"- {v}" for v in verdict)
        content += "\n> 注：电流 TDD 限值取决于短路比 ISC/IL（IEEE 519 表2），需按 PCC 短路容量另行评估。"
        return {"type": "text", "content": content}

    # ------------------------------------------------ 功率因数
    def _power_factor(self, p) -> Dict[str, Any]:
        U = _num(p, "voltage", 400); I = _num(p, "current")
        cos1 = _num(p, "cos_phi1", 0.75); cos2 = _num(p, "cos_phi2_target", 0.95)
        phase = str(p.get("phase", "3"))
        if I is None:
            return {"type": "text", "content": "参数缺失：current(线电流A)。"}
        k = math.sqrt(3) if phase == "3" else 1.0
        P = k * U * I * cos1 / 1000.0
        Q1 = P * math.tan(math.acos(cos1))
        Q2 = P * math.tan(math.acos(cos2))
        Qc = Q1 - Q2
        C = Qc * 1e6 / (2 * math.pi * 50 * U * U) if U else 0
        rows = [
            ["有功功率 P", "kW", round(P, 2)],
            ["补偿前无功 Q₁", "kvar", round(Q1, 2)],
            ["补偿后无功 Q₂", "kvar", round(Q2, 2)],
            ["所需补偿容量 Qc", "kvar", round(Qc, 2)],
            ["对应电容 C（50Hz, 线电压）", "μF", round(C, 1)],
        ]
        content = (
            "### 功率因数与无功补偿\n\n"
            f"**公式**：P = √3·U·I·cosφ₁（kW）；Qc = P·(tanφ₁ − tanφ₂)；C = Qc×10⁶ / (2πf·U²)（μF）\n\n"
            + _md_table(["项目", "单位", "数值"], rows) +
            f"\n**结论**：需补偿 **{round(Qc, 2)} kvar** 可将功率因数由 {cos1} 提升至 {cos2}。\n"
            "> 提示：电容投切需核算谐振风险（用 resonance 计算）与涌流；实际选型取标准容量并留裕度。"
        )
        return {"type": "text", "content": content}

    # ------------------------------------------------ 软起动
    def _soft_starter(self, p) -> Dict[str, Any]:
        kw = _num(p, "motor_kw")
        Ifl = _num(p, "motor_full_load_A")
        Ilr_ratio = _num(p, "locked_rotor_ratio", 6.5)
        k_lim = _num(p, "current_limit_k", 0.5)
        Tlr_ratio = _num(p, "locked_torque_ratio", 1.5)
        load_torque = _num(p, "load_torque_ratio", 0.8)
        missing = []
        if kw is None: missing.append("motor_kw")
        if Ifl is None: missing.append("motor_full_load_A")
        if missing:
            return {"type": "text", "content": "参数缺失：" + "、".join(missing)}
        Ilr = Ilr_ratio * Ifl
        Istart = k_lim * Ilr
        Tstart = k_lim * k_lim * Tlr_ratio
        margin = Tstart - load_torque
        rows = [
            ["堵转电流 I_LR", "A", round(Ilr, 1)],
            ["限流起动电流 I_start", "A", round(Istart, 1)],
            ["起动转矩系数 T_start/T_N", "p.u.", round(Tstart, 2)],
            ["负载转矩系数 T_load/T_N", "p.u.", load_torque],
            ["转矩裕度 T_start − T_load", "p.u.", round(margin, 2)],
        ]
        content = (
            "### 软起动器起动校核（限流模式）\n\n"
            "**公式**：I_LR = k_LR·I_FL；I_start ≈ k·I_LR；T_start/T_N ≈ k²·(T_LR/T_N)（近似，电流限流控制）\n\n"
            + _md_table(["项目", "单位", "数值"], rows)
        )
        if margin > 0:
            content += f"\n**结论**：转矩裕度 {round(margin, 2)} p.u. > 0，**可正常起动**（假设恒阻性负载）。"
        else:
            content += f"\n**结论**：转矩裕度 ≤ 0，**起动可能失败**，建议：1) 提高电流限值 k（不超电机/电网承受）；2) 采用电压斜坡+限流组合；3) 换更大起动转矩方案。"
        content += ("\n> 校核提示：1) 检查软起动器额定电流 ≥ 电机满载电流且留裕度；2) 核算 I²t 热负荷与起动频次（每小时起动次数）；"
                    "3) 大惯量负载（如泵/风机）还需校核加速时间与散热；4) 电网压降校核可用 voltage_drop/cable_area 计算。")
        return {"type": "text", "content": content}

    # ------------------------------------------------ 谐振
    def _resonance(self, p) -> Dict[str, Any]:
        St = _num(p, "transformer_kva")
        Zpct = _num(p, "impedance_pct", 6)
        Qc = _num(p, "capacitor_kvar")
        if St is None or Qc is None:
            return {"type": "text", "content": "参数缺失：transformer_kva 与 capacitor_kvar。"}
        Scc = St * 100.0 / Zpct
        h = math.sqrt(Scc / Qc)
        fres = 50 * h
        danger = any(abs(h - n) < 0.3 for n in (5, 7, 11, 13))
        rows = [["变压器短路容量 S_cc", "kVA", round(Scc, 1)],
                ["谐振次数 h", "p.u.", round(h, 2)],
                ["谐振频率 f_res", "Hz", round(fres, 1)]]
        content = (
            "### 电容/变压器并联谐振评估\n\n"
            "**公式**：S_cc = S_T×100/Z%；h = √(S_cc / Q_c)；f_res = f₁·h\n\n"
            + _md_table(["项目", "单位", "数值"], rows)
        )
        if danger:
            content += f"\n**警告**：谐振点 h={round(h, 2)} 接近 {_near(h)} 次特征谐波，存在谐波放大风险！建议：1) 电容支路串联调谐电抗（如 7% → 调谐频率约 189 Hz，避开 5/7 次）；2) 核算实际谐波源电流；3) 投切策略优化。"
        else:
            content += f"\n**结论**：谐振点 h={round(h, 2)} 未落在常见特征谐波（5/7/11/13 次）附近，风险较低。仍建议核算实际谐波水平。"
        return {"type": "text", "content": content}


def _near(h: float) -> str:
    for n in (5, 7, 11, 13):
        if abs(h - n) < 0.3:
            return f"{n}"
    return f"{h:.1f}"
