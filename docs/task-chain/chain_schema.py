"""task-chain schema — 中立纯模块(两侧共读)。

链系统有两个消费方:派生链视图的运行时与校验写入的工具链;本模块不属于
任何一侧,由两侧经文件路径加载。中立性=零依赖纯度,非地址。

判定分两层:
  机械可直接执法=格式事实(schema非法|枚举越界——闭世界错误,validate只报此类);
  复杂状态(closed/质量/一致性)=语义声明——机械面产 facets(规则匹配证据快照)
  随声明落账 + 事后 consistency ⚠ 标记呈示,不自动改写状态。

legacy profile(schema ≤ 2.2)为读取兼容启发:deprecated(deprecation_notice
非null)→retired;handoff.closed=="closed"→closed;executor_and_time非空→executing;
其余→planned。此为读取兼容,非新 schema 判定(文档化启发)。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

SCHEMA_VERSION = "3.3"

Status = Literal["planned", "executing", "delivered", "closed", "retired"]
STATUS_VALUES: tuple[str, ...] = ("planned", "executing", "delivered",
                                  "closed", "retired")
CLOSED_STATUSES: frozenset[str] = frozenset({"closed", "retired"})
SETTLED_STATUSES: frozenset[str] = frozenset({"delivered", "closed"})

ChangeTier = Literal["declared", "undeclared", "mechanism"]

Kind = Literal["terminal", "standing"]
KIND_VALUES: tuple[str, ...] = ("terminal", "standing")

CHAIN_EVENTS: tuple[str, ...] = ("birth", "reopen", "archive", "unarchive",
                                 "charter-rev")
CAUSE_REQUIRED_CHAIN_EVENTS: frozenset[str] = frozenset(
    {"reopen", "archive", "unarchive", "charter-rev"})

TERMINAL_TASK_EVENTS: frozenset[str] = frozenset({"close", "retire"})

# declare 软门关键 facet(缺失→警告;--force 越道留痕)——辅助依据非直接依据
CRITICAL_FACETS: Mapping[str, tuple[str, ...]] = {
    "close": ("handoff_written", "delivery_signed"),
    "deliver": ("changes_recorded",),
}


@dataclass(frozen=True)
class Violation:
    """格式事实违规(validate 只产此类——闭世界错误,非状态判定)。"""

    path: str
    code: str  # missing | type | enum
    detail: str


@dataclass(frozen=True)
class Facets:
    """规则匹配器产物——在场性匹配快照,非判定。"""

    handoff_written: bool      # handoff.detection 非空
    delivery_signed: bool      # handoff.delivery_details 非空
    changes_recorded: bool     # handoff.changes 非空
    unfinished_present: bool   # handoff.unfinished_reason 非 null
    evidence_linked: bool      # records 非空
    declared_files: bool       # execute.task_Det 非空

    def as_dict(self) -> dict[str, bool]:
        return {
            "handoff_written": self.handoff_written,
            "delivery_signed": self.delivery_signed,
            "changes_recorded": self.changes_recorded,
            "unfinished_present": self.unfinished_present,
            "evidence_linked": self.evidence_linked,
            "declared_files": self.declared_files,
        }


@dataclass(frozen=True)
class Flag:
    """一致性标记(事后呈示,advisory——不自动改写状态)。"""

    code: str
    detail: str


@dataclass(frozen=True)
class TaskView:
    """read_status 产物——derive_course/显示面消费。"""

    chain: str
    task: str
    index: int
    schema_version: str      # "3.0" | "legacy"
    status: str              # Status 值(legacy 经兼容启发映射)
    closed: bool
    task_type: str
    oneliner: str
    momentum: str
    unfinished: str
    flags: tuple[Flag, ...] = ()


@dataclass(frozen=True)
class ManifestView:
    """manifest 读取面(链级单一事实源)。"""

    chain_id: str
    oneliner: str
    momentum: str
    routing_paths: tuple[str, ...] = ()
    routing_tokens: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION


_ACTIVE_CHAIN_RE = re.compile(r"C\d+|C[A-Z]{2,7}")


def is_active_chain_dir(name: str) -> bool:
    """活跃链目录判定——显式规则(归档区 chain-history 等不进 course/发现面)。

    防 glob 巧合: Windows 大小写不敏感下 "chain-history" 会被 "C*" 误匹配。
    注1: 归档为 manifest 声明、目录不动——archived 链仍住原目录,
    由读取方经 chain_state() 排除,本函数只管目录形态。
    注2: 治理链(C+大写字母的语义id)为另一种命名格式,入规则。
    """
    return _ACTIVE_CHAIN_RE.fullmatch(name) is not None


# ---------------------------------------------------------------------------
# 序列化权威 + canonical 快照哈希(检测器基线)
# ---------------------------------------------------------------------------

def dump_task(obj: Mapping[str, Any]) -> str:
    """任务文件唯一序列化——快照哈希的稳定性前提(参数变更即全量快照失效,
    检测器按 advisory 对待)。"""
    return json.dumps(dict(obj), indent=2, ensure_ascii=False) + "\n"


def _snapshot_view(obj: Mapping[str, Any]) -> dict[str, Any]:
    """canonical 视图——剥最后一条终局声明(close/retire),挥发面归零:
    lifecycle.consistency_flags 清空;status 从剩余声明重推(与 declare 的
    状态映射同律——status 是声明的派生面,不重推则快照永不相等)。"""
    o = copy.deepcopy(dict(obj))
    life = o.get("lifecycle")
    if isinstance(life, dict):
        decls = life.get("declarations")
        if (isinstance(decls, list) and decls
                and isinstance(decls[-1], Mapping)
                and decls[-1].get("event") in TERMINAL_TASK_EVENTS):
            decls.pop()
        status: Status = "planned"
        if isinstance(decls, list):
            for d in decls:
                if isinstance(d, Mapping):
                    status = _EVENT_STATUS.get(str(d.get("event")), status)
        life["status"] = status
        life["consistency_flags"] = []
    return o


def snapshot_sha(obj: Mapping[str, Any]) -> str:
    """声明时刻的内容快照(close/retire 前状态)——写入 declaration.content_sha256。"""
    return hashlib.sha256(
        dump_task(_snapshot_view(obj)).encode("utf-8")).hexdigest()


def content_sha_of(obj: Mapping[str, Any]) -> str:
    """读时重算——与 snapshot_sha 同口径(剥终局声明+挥发面归零)。"""
    return snapshot_sha(obj)


def charter_sha(text: str) -> str:
    """charter 文件内容哈希(manifest.evolution.charter.sha256 的口径)。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_legacy(obj: Mapping[str, Any]) -> bool:
    """≤2.2 判定——schema_version 非 3.x。"""
    v = obj.get("schema_version")
    return not (isinstance(v, str) and v.startswith("3."))


# ---------------------------------------------------------------------------
# validate —— 只报格式事实
# ---------------------------------------------------------------------------

def _violation(path: str, code: str, detail: str) -> Violation:
    return Violation(path, code, detail)


def validate_task(obj: Mapping[str, Any]) -> tuple[Violation, ...]:
    """v3 任务骨架格式核验——缺键/类型/枚举越界;legacy 文件不适用(返回注明)。"""
    if is_legacy(obj):
        return (_violation("schema_version", "enum",
                           "legacy file (≤2.2) — validate applies to v3 only"),)
    out: list[Violation] = []
    ident = obj.get("identity")
    if not isinstance(ident, Mapping):
        return (_violation("identity", "missing", "identity section required"),)
    tid = ident.get("task_id")
    if not isinstance(tid, str) or not tid:
        out.append(_violation("identity.task_id", "missing", "non-empty str"))
    idx = ident.get("task_index")
    if not isinstance(idx, int) or isinstance(idx, bool) or idx < 1:
        out.append(_violation("identity.task_index", "type", "int >= 1"))
    life = obj.get("lifecycle")
    if not isinstance(life, Mapping):
        out.append(_violation("lifecycle", "missing", "lifecycle section required"))
    else:
        st = life.get("status")
        if st not in STATUS_VALUES:
            out.append(_violation("lifecycle.status", "enum",
                                  f"one of {STATUS_VALUES}"))
        decls = life.get("declarations")
        if not isinstance(decls, list):
            out.append(_violation("lifecycle.declarations", "type", "list"))
        else:
            for i, d in enumerate(decls):
                if not isinstance(d, Mapping) or not isinstance(d.get("event"), str):
                    out.append(_violation(f"lifecycle.declarations[{i}]",
                                          "type", "event str required"))
                if not isinstance(d.get("by"), str) or not d.get("by"):
                    out.append(_violation(f"lifecycle.declarations[{i}].by",
                                          "missing", "non-empty str"))
                if not isinstance(d.get("at"), (int, float)):
                    out.append(_violation(f"lifecycle.declarations[{i}].at",
                                          "type", "number"))
    lineage = obj.get("lineage")
    if not isinstance(lineage, Mapping) or not isinstance(lineage.get("depends_on"), list):
        out.append(_violation("lineage.depends_on", "type", "list required"))
    for sec in ("execute", "handoff"):
        if not isinstance(obj.get(sec), Mapping):
            out.append(_violation(sec, "missing", f"{sec} section required"))
    # 格式事实收紧:changes 恒为 list(防手写成串);executor 为 null|str
    hand = obj.get("handoff") if isinstance(obj.get("handoff"), Mapping) else {}
    if not isinstance(hand.get("changes"), list):
        out.append(_violation("handoff.changes", "type",
                              "list required (schema 3.3)"))
    exe = obj.get("execute") if isinstance(obj.get("execute"), Mapping) else {}
    if exe.get("executor") is not None and not isinstance(exe.get("executor"), str):
        out.append(_violation("execute.executor", "type",
                              "null | str (schema 3.3)"))
    rec = obj.get("records")
    if not isinstance(rec, list):
        out.append(_violation("records", "type", "list"))
    return tuple(out)


def validate_manifest(obj: Mapping[str, Any]) -> tuple[Violation, ...]:
    """v3 manifest 格式核验(格式事实)——v3.1 增 kind 枚举/charter 形状/lifecycle。"""
    if is_legacy(obj):
        return (_violation("schema_version", "enum", "legacy manifest"),)
    out: list[Violation] = []
    cid = obj.get("chain_id")
    if not isinstance(cid, str) or not cid:
        out.append(_violation("chain_id", "missing", "non-empty str"))
    kind = obj.get("kind")
    if kind is not None and kind not in KIND_VALUES:
        out.append(_violation("kind", "enum", f"one of {KIND_VALUES}"))
    evo = obj.get("evolution")
    if not isinstance(evo, Mapping):
        out.append(_violation("evolution", "missing", "evolution section required"))
    else:
        mom = evo.get("momentum")
        if not isinstance(mom, str) or not mom:
            out.append(_violation("evolution.momentum", "missing",
                                  "non-empty str (立链登记,分支truth-maker)"))
        ep = evo.get("epoch")
        if ep is not None and (not isinstance(ep, int) or isinstance(ep, bool)
                               or ep < 1):
            out.append(_violation("evolution.epoch", "type",
                                  "int >= 1 (机械维护,reopen 自增)"))
        ch = evo.get("charter")
        if ch is not None:
            if not isinstance(ch, Mapping) or not isinstance(ch.get("sha256"), str):
                out.append(_violation("evolution.charter", "type",
                                      "charter{path,sha256,revisions} required"))
    life = obj.get("lifecycle")
    if life is not None and not isinstance(life, Mapping):
        out.append(_violation("lifecycle", "type", "Mapping required"))
    return tuple(out)


# ---------------------------------------------------------------------------
# facets / consistency —— 规则匹配器
# ---------------------------------------------------------------------------

def facets_of(obj: Mapping[str, Any]) -> Facets:
    """在场性匹配(v3 形状;legacy 返回启发面同名 facets)。"""
    hand = obj.get("handoff") if isinstance(obj.get("handoff"), Mapping) else {}
    exe = obj.get("execute") if isinstance(obj.get("execute"), Mapping) else {}
    rec = obj.get("records") if isinstance(obj.get("records"), list) else []
    det = exe.get("task_Det") if isinstance(exe.get("task_Det"), list) else []
    return Facets(
        handoff_written=bool(str(hand.get("detection") or "").strip()),
        delivery_signed=bool(str(hand.get("delivery_details") or "").strip()),
        changes_recorded=bool(hand.get("changes")),
        unfinished_present=hand.get("unfinished_reason") is not None,
        evidence_linked=bool(rec),
        declared_files=bool(det),
    )


def consistency_of(obj: Mapping[str, Any]) -> tuple[Flag, ...]:
    """事后一致性标记(呈示不执法)——声明与 facets 的矛盾检出。

    含读时检测 closed-then-modified:终局声明携带 content_sha256
    时,与同口径读时重算比对——闭后无痕改动即 mismach。纯数据(不需文件字节:
    加载对象本身即内容)。
    """
    if is_legacy(obj):
        return ()  # 启发面不产 flag(文档化)
    flags: list[Flag] = []
    life = obj.get("lifecycle") if isinstance(obj.get("lifecycle"), Mapping) else {}
    status = life.get("status")
    f = facets_of(obj)
    if status == "closed":
        if not f.delivery_signed:
            flags.append(Flag("closed-unsigned", "closed 而 delivery_details 空"))
        if not f.handoff_written:
            flags.append(Flag("closed-no-handoff", "closed 而 handoff.detection 空"))
    if status in SETTLED_STATUSES and not f.changes_recorded:
        flags.append(Flag("settled-no-changes", "delivered/closed 而无 changes 记录"))
    if status in CLOSED_STATUSES:
        decls = life.get("declarations")
        if isinstance(decls, list) and decls:
            last = decls[-1]
            if (isinstance(last, Mapping)
                    and last.get("event") in TERMINAL_TASK_EVENTS
                    and isinstance(last.get("content_sha256"), str)
                    and last["content_sha256"]
                    and content_sha_of(obj) != last["content_sha256"]):
                flags.append(Flag(
                    "closed-then-modified",
                    "闭后内容与闭时快照不符——须经 reopen 声明后修改"))
    return tuple(flags)


# ---------------------------------------------------------------------------
# read_status —— derive_course/显示面唯一消费 API
# ---------------------------------------------------------------------------

def read_status(obj: Mapping[str, Any], *, chain: str = "",
                manifest: Mapping[str, Any] | None = None) -> TaskView | None:
    """任务对象 → TaskView(v3/legacy 自动分派;无 task 标识→None)。"""
    if is_legacy(obj):
        return _legacy_view(obj, chain)
    ident = obj.get("identity") if isinstance(obj.get("identity"), Mapping) else {}
    tid = ident.get("task_id")
    if not isinstance(tid, str) or not tid:
        return None
    life = obj.get("lifecycle") if isinstance(obj.get("lifecycle"), Mapping) else {}
    status = life.get("status") if life.get("status") in STATUS_VALUES else "planned"
    exe = obj.get("execute") if isinstance(obj.get("execute"), Mapping) else {}
    hand = obj.get("handoff") if isinstance(obj.get("handoff"), Mapping) else {}
    mv = manifest_view(manifest) if manifest is not None else None
    return TaskView(
        chain=(mv.chain_id if mv and mv.chain_id else chain),
        task=tid,
        index=int(ident.get("task_index") or 0),
        schema_version=SCHEMA_VERSION,
        status=status,
        closed=status in CLOSED_STATUSES,
        task_type=str(exe.get("task_type") or ""),
        oneliner=(mv.oneliner if mv else ""),
        momentum=(mv.momentum if mv else ""),
        unfinished=str(hand.get("unfinished_reason") or "").strip(),
        flags=consistency_of(obj),
    )


def _legacy_view(obj: Mapping[str, Any], chain_hint: str) -> TaskView | None:
    """legacy profile——兼容启发(≤2.2,非新 schema 判定)。"""
    mech = obj.get("mechanical") if isinstance(obj.get("mechanical"), Mapping) else {}
    exe = obj.get("execute") if isinstance(obj.get("execute"), Mapping) else {}
    hand = obj.get("handoff") if isinstance(obj.get("handoff"), Mapping) else {}
    chain = str(mech.get("chain_id") or chain_hint or "")
    task = str(mech.get("task_id") or "")
    if not chain or not task:
        return None
    if hand.get("deprecation_notice") is not None:
        status: Status = "retired"
    elif str(hand.get("closed") or "").strip() == "closed":
        status = "closed"
    elif bool(str(hand.get("executor_and_time")
                  or exe.get("executor_and_time") or "").strip()):
        status = "executing"
    else:
        status = "planned"
    return TaskView(
        chain=chain,
        task=task,
        index=int(mech.get("task_index") or 0),
        schema_version="legacy",
        status=status,
        closed=status in CLOSED_STATUSES,
        task_type=str(exe.get("task_type") or ""),
        oneliner=str(exe.get("oneliner") or "").strip(),
        momentum=str(exe.get("momentum") or "").strip(),
        unfinished=str(hand.get("unfinished_reason") or "").strip(),
    )


def manifest_view(obj: Mapping[str, Any] | None) -> ManifestView | None:
    """manifest 对象 → ManifestView(非 manifest 形状→None)。"""
    if not isinstance(obj, Mapping) or is_legacy(obj):
        return None
    evo = obj.get("evolution") if isinstance(obj.get("evolution"), Mapping) else {}
    anchors = (evo.get("routing_anchors")
               if isinstance(evo.get("routing_anchors"), Mapping) else {})
    return ManifestView(
        chain_id=str(obj.get("chain_id") or ""),
        oneliner=str(evo.get("oneliner") or "").strip(),
        momentum=str(evo.get("momentum") or "").strip(),
        routing_paths=tuple(anchors.get("paths") or ()),
        routing_tokens=tuple(anchors.get("tokens") or ()),
    )


# ---------------------------------------------------------------------------
# declare —— 声明转移(语义判断登记;机械面=证据快照+软门)
# ---------------------------------------------------------------------------

_EVENT_STATUS: Mapping[str, Status] = {
    "start": "executing",
    "deliver": "delivered",
    "close": "closed",
    "retire": "retired",
    "reopen": "executing",
}


def declare(obj: Mapping[str, Any], event: str, *, by: str, at: float,
            at_iso: str, force: bool = False,
            critical: Mapping[str, tuple[str, ...]] = CRITICAL_FACETS,
            content_sha256: str | None = None,
            superseded_by: str | None = None,
            ) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """声明事件登记——返回 (新对象, 警告元组);软门拒绝时新对象为 None。

    纯函数: 不修改入参;状态=声明的机械登记(judgment 在调用侧语义层)。
    软门: event 的关键 facet 缺失→警告;非 force→拒绝(None),
    force→越道留痕(overrides 记录缺失 facet 名)。
    content_sha256: 终局事件(close/retire)的内容快照——调用侧以
    snapshot_sha(原对象) 预计算传入;未传则跳过(检测面缺席)。
    superseded_by: retire 时记录取代者指针(supersede 模式)。
    """
    if event not in _EVENT_STATUS:
        return None, (f"unknown event: {event}",)
    fac = facets_of(obj)
    keys = critical.get(event, ())
    missing = tuple(k for k in keys if not fac.as_dict().get(k))
    warnings: list[str] = []
    overrides: list[str] = []
    if missing:
        w = (f"critical facets missing for '{event}': {', '.join(missing)} "
             f"— 声明被软门拒绝(机械=辅助依据);补齐后重试或 --force 越道留痕")
        if not force:
            return None, (w,)
        warnings.append(w + " [forced]")
        overrides.extend(missing)
    new = copy.deepcopy(dict(obj))
    life = new.setdefault("lifecycle", {})
    decls = life.setdefault("declarations", [])
    record: dict[str, Any] = {
        "event": event, "by": by, "at": at, "at_iso": at_iso,
        "facets": fac.as_dict(), "overrides": overrides,
    }
    if content_sha256:
        record["content_sha256"] = content_sha256
    if superseded_by:
        record["superseded_by"] = superseded_by
    decls.append(record)
    life["status"] = _EVENT_STATUS[event]
    life["consistency_flags"] = [
        {"code": f.code, "detail": f.detail} for f in consistency_of(new)
    ]
    return new, tuple(warnings)


# ---------------------------------------------------------------------------
# 链级声明与状态派生
# ---------------------------------------------------------------------------

def declare_chain(manifest: Mapping[str, Any], event: str, *, by: str,
                  at: float, at_iso: str, cause: str = "",
                  force: bool = False,
                  content_sha256: str | None = None,
                  ) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """链级声明(birth/reopen/archive/unarchive/charter-rev)。

    cause 必填面软门: 缺 cause→拒绝;force→越道留痕。
    archive/unarchive 配对即原位归档——目录不动,状态经 chain_state 派生。
    """
    if event not in CHAIN_EVENTS:
        return None, (f"unknown chain event: {event}",)
    warnings: list[str] = []
    overrides: list[str] = []
    if event in CAUSE_REQUIRED_CHAIN_EVENTS and not cause.strip():
        w = (f"chain event '{event}' requires --cause "
             f"(演进事实的 truth-maker);--force 越道留痕")
        if not force:
            return None, (w,)
        warnings.append(w + " [forced]")
        overrides.append("cause")
    new = copy.deepcopy(dict(manifest))
    life = new.setdefault("lifecycle", {})
    decls = life.setdefault("declarations", [])
    decls.append({
        "event": event, "by": by, "at": at, "at_iso": at_iso,
        "cause": cause, "overrides": overrides,
        **({"content_sha256": content_sha256} if content_sha256 else {}),
    })
    if event == "reopen":
        # 纪元计数为机械维护字段:reopen 声明时 epoch=声明链内 reopen 事件数+1
        # (birth=1),不经语义字段手写;检测器以 epoch-mismatch 对账。
        evo = new.setdefault("evolution", {})
        reopens = sum(
            1 for d in decls
            if isinstance(d, Mapping) and d.get("event") == "reopen"
        )
        evo["epoch"] = reopens + 1
    return new, tuple(warnings)


def chain_state(manifest: Mapping[str, Any] | None,
                task_statuses: list[str]) -> str:
    """链级状态派生——archived(声明) > dormant(standing∧全闭) > active。

    task_statuses: 该链全部任务的 status(含 retired);manifest 为
    v3.0/legacy(无 lifecycle)时按声明面缺席处理(terminal 语义)。
    """
    archived = False
    if isinstance(manifest, Mapping):
        life = manifest.get("lifecycle")
        if isinstance(life, Mapping):
            for d in life.get("declarations") or []:
                if isinstance(d, Mapping):
                    if d.get("event") == "archive":
                        archived = True
                    elif d.get("event") == "unarchive":
                        archived = False
    if archived:
        return "archived"
    kind = ""
    if isinstance(manifest, Mapping):
        kind = str(manifest.get("kind") or "")
    if (kind == "standing" and task_statuses
            and all(s in CLOSED_STATUSES for s in task_statuses)):
        return "dormant"
    return "active"


def manifest_consistency(manifest: Mapping[str, Any],
                         charter_sha_now: str | None = None,
                         ) -> tuple[Flag, ...]:
    if is_legacy(manifest):
        return ()
    flags: list[Flag] = []
    evo = manifest.get("evolution")
    ch = (evo.get("charter") if isinstance(evo, Mapping)
          and isinstance(evo.get("charter"), Mapping) else None)
    if ch is not None and charter_sha_now is not None:
        if str(ch.get("sha256") or "") != charter_sha_now:
            flags.append(Flag("charter-uncommitted",
                              "charter 文件与最近登记的修订不符——须经 "
                              "charter --rev --cause 声明"))
    life = manifest.get("lifecycle")
    if isinstance(life, Mapping):
        for i, d in enumerate(life.get("declarations") or []):
            if (isinstance(d, Mapping)
                    and d.get("event") in CAUSE_REQUIRED_CHAIN_EVENTS
                    and not str(d.get("cause") or "").strip()):
                flags.append(Flag(
                    "declaration-no-cause",
                    f"declarations[{i}] ({d.get('event')}) 缺 cause"))
    # epoch-mismatch——存储纪元数 vs 声明链派生值对账
    if isinstance(evo, Mapping):
        ep = evo.get("epoch")
        if isinstance(ep, int) and not isinstance(ep, bool) and isinstance(life, Mapping):
            reopens = sum(
                1 for d in life.get("declarations") or []
                if isinstance(d, Mapping) and d.get("event") == "reopen"
            )
            if ep != reopens + 1:
                flags.append(Flag(
                    "epoch-mismatch",
                    f"evolution.epoch={ep} 与声明链派生值={reopens + 1} 不符"
                    f"——手写漂移,reopen 声明时机械重写"))
    return tuple(flags)


# ---------------------------------------------------------------------------
# constructors —— 外壳生成 v3 文件用(纯)
# ---------------------------------------------------------------------------

def new_manifest_obj(*, chain_id: str, oneliner: str, momentum: str,
                     kind: str = "terminal",
                     charter_text: str | None = None,
                     by: str, at: float, at_iso: str) -> dict[str, Any]:
    """立链 manifest——kind 二分+charter 指针+birth 声明
    +epoch 纪元计数(birth=1,reopen 机械自增)。"""
    evolution: dict[str, Any] = {
        "momentum": momentum,
        "oneliner": oneliner,
        "epoch": 1,
    }
    if charter_text is not None:
        evolution["charter"] = {
            "path": "_charter.md",
            "sha256": charter_sha(charter_text),
            "revisions": 0,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "chain_id": chain_id,
        "kind": kind,
        "evolution": evolution,
        "lifecycle": {"declarations": [
            {"event": "birth", "by": by, "at": at, "at_iso": at_iso,
             "cause": "", "overrides": []},
        ]},
        "created": {"by": by, "at": at, "at_iso": at_iso},
    }


def new_task_obj(*, task_id: str, task_index: int,
                 depends_on: tuple[str, ...] = (),
                 task_type: str = "", supersedes: str = "",
                 by: str, at: float,
                 at_iso: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "task_id": task_id,
            "task_index": task_index,
            "parent_task": None,
            **({"supersedes_task": supersedes} if supersedes else {}),
            "created": {"by": by, "at": at, "at_iso": at_iso},
        },
        "lifecycle": {
            "status": "planned",
            "declarations": [],
            "consistency_flags": [],
        },
        "lineage": {"depends_on": list(depends_on)},
        "inspect": {"checks": None, "summary": None},
        "execute": {
            "executor": None,
            "task_type": task_type or None,
            "task_Det": [],
            "expected": None,
        },
        "handoff": {
            "changes": [],
            "detection": None,
            "delivery_details": None,
            "unfinished_reason": None,
            "deprecation_notice": None,
        },
        "records": [],
    }
