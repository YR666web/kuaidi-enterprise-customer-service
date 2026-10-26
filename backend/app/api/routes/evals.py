"""Agent 回归评测接口。"""

import fastapi
from fastapi import APIRouter

from app.evals.agent_runner import run_agent_harness_evaluation
from app.evals.prompt_runner import run_prompt_evaluation
from app.evals.runner import list_badcases, run_offline_evaluation
from app.platform.rbac import Permission, require_permission

router = APIRouter(prefix="/evals", tags=["evals"])
_eval_run = fastapi.Depends(require_permission(Permission.EVAL_RUN))


@router.get("/report")
def get_report(_tenant=_eval_run) -> dict:
    """获取当前代码版本的离线路由/安全评测报告。"""
    return run_offline_evaluation()


@router.post("/run")
def run_report(_tenant=_eval_run) -> dict:
    """重新执行离线评测；无需模型额度。"""
    return run_offline_evaluation()


@router.get("/agent")
def get_agent_report(_tenant=_eval_run) -> dict:
    """获取工具选择、参数、任务成功率与不安全动作指标。"""
    return run_agent_harness_evaluation()


@router.get("/prompt")
def get_prompt_report(_tenant=_eval_run) -> dict:
    """获取 Prompt 结构、注入边界与上下文预算回归报告。"""
    return run_prompt_evaluation()


@router.get("/badcases")
def get_badcases(_tenant=_eval_run) -> dict:
    """查看已沉淀的脱敏失败案例及其回归目标。"""
    return {"total": len(list_badcases()), "cases": list_badcases()}
