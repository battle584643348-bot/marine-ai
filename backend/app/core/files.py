"""生成文件（generated/ 目录）的安全路径解析与下载 URL 生成。

【为什么单独建这个模块，而不是写在 api/settings.py 里】
    需要用到它的有两层：
      · api 层  settings.py —— 把 URL 里的相对路径变成磁盘上的真实文件
      · agent 层 loop.py     —— 把技能产物的绝对路径变成浏览器能点的下载 URL
    如果函数写在 api 层，agent 层就得 `from ..api.settings import ...`，
    变成「业务层反向依赖接口层」——依赖方向反了，以后想换 Web 框架（比如换 Flask）
    就得连 agent 层一起改。放在 core（最底层，不 import 任何上层模块）就没有这个问题。

【安全边界：这个文件是全项目唯一允许把「外部字符串」翻译成「磁盘路径」的地方】
    Web 应用最经典的漏洞之一是路径穿越（Path Traversal）：
        用户请求 /api/files/../../config.yaml
    如果直接拼路径并读文件，configuration.yaml 里的 API Key 就泄露了。
    所以下面每个函数只做两件事：拼出路径、然后用 is_relative_to 确认它没跑出根目录。
"""
from pathlib import Path
from typing import Optional
from urllib.parse import quote


def generated_root(cfg) -> Path:
    """返回 generated 目录的绝对规范路径。

    · cfg.paths()["generated"] 来自 core/config.py:70，是配置里算出来的目录
    · Path(...)                把字符串包装成路径对象，才能用 / 拼接、.resolve() 等方法
    · .resolve()               关键：把 `..`、`.`、符号链接、以及 Windows 的短文件名
                               全部展开成唯一的绝对路径。不做这一步，所有比较都不可靠
    """
    return Path(cfg.paths()["generated"]).resolve()


def resolve_generated_rel(cfg, rel: str) -> Optional[Path]:
    """把 URL 中的相对路径（如 `diagram_mark/xxx.pdf`）解析成磁盘上的真实文件。

    返回值：合法且存在的文件 → Path；越界 / 不存在 / 非法 → None（由调用方回 404）。

    【为什么这里用 Optional[Path] 而不是抛异常】
        这个函数会被两处调用，其中 agent 层只是"尽力附带下载链接"，失败了不该
        中断整轮对话。返回 None 让调用方自己决定是抛 404 还是静默跳过。
    """
    # 空字符串直接拒掉：base / "" 会得到 base 本身，等于把整个目录当成文件
    if not rel:
        return None

    base = generated_root(cfg)

    # try 里只放"可能因为用户输入而崩溃"的操作，异常类型要写具体，不要裸 except
    #   OSError   —— 路径太长（Windows 260 限制）、非法字符、磁盘错误
    #   ValueError —— 路径里含 \x00（空字节），Python 会直接拒绝
    try:
        # `base / rel` 是 pathlib 的运算符重载，等价于 os.path.join
        # 但它有个特性：如果 rel 是绝对路径（如 "C:/Windows/x" 或 "/etc/passwd"），
        # 结果会变成 rel 本身，base 被整个丢弃 —— 所以必须靠下面的 is_relative_to 兜底
        candidate = (base / rel).resolve()
    except (OSError, ValueError):
        return None

    # ★ 核心防线：is_relative_to 判断 candidate 是否在 base 这棵子树里。
    #   为什么不用 str(candidate).startswith(str(base))？
    #   因为字符串前缀比较会被同名前缀骗过：
    #       base     = E:\AI LCP\marine-ai\generated
    #       candidate= E:\AI LCP\marine-ai\generated_evil\x.txt
    #   后者 startswith 前者为 True，但它根本不在 generated 目录里。
    #   is_relative_to 是按「路径层级」比较的，不会出现这种误判。
    #   （需要 Python 3.9+，本项目要求 3.10+）
    if not candidate.is_relative_to(base):
        return None

    # is_file() 而非 exists()：目录、设备文件（如 Windows 的 CON）都不能当下载内容
    if not candidate.is_file():
        return None

    return candidate


def generated_url(cfg, abs_path: str) -> Optional[str]:
    """把 generated 下的绝对路径，翻译成前端可以直接放进 <a href> 的 URL。

    例：E:\\AI LCP\\marine-ai\\generated\\diagram_mark\\a b&c.pdf
        → /api/files/diagram_mark/a%20b%26c.pdf

    【为什么要把"绝对路径 → URL"放在后端做，而不是原样发给前端让它自己拼】
        1. 不泄露服务器目录结构。把 `E:\\AI LCP\\...` 发到浏览器，等于告诉别人
           你的用户名、项目代号、磁盘布局——这类信息在渗透测试里叫"信息泄露"。
        2. 只发相对路径 + 编码，前端就没机会拼错，也不需要知道 generated 在哪。
    """
    try:
        p = Path(abs_path).resolve()
        base = generated_root(cfg)
        # 同样的越界检查：技能理论上只会往 generated 里写，但防御性编程不嫌多
        if not p.is_relative_to(base):
            return None
        # relative_to 去掉 base 前缀 → Path("diagram_mark/a b.pdf")
        # .as_posix() 把 Windows 的反斜杠 `\\` 统一成正斜杠 `/`，否则拼进 URL 会变成转义符
        rel = p.relative_to(base).as_posix()
    except (OSError, ValueError):
        return None

    # quote() 做 URL 百分号编码：空格→%20、&→%26、中文→UTF-8 十六进制
    # safe="/" 表示「斜杠不要编码」，因为斜杠是 URL 里的路径分隔符，不是数据
    #   · 不编码空格：浏览器会把 URL 在空格处截断，下载链接直接失效
    #   · 不编码 &  ：`&` 在 URL 里是参数分隔符，文件名里的 & 会被当成新参数
    return "/api/files/" + quote(rel, safe="/")
