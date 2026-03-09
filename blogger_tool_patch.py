"""
blogger_tool_patch.py
Monkey-patch que adiciona a tool blogger.publish_post ao ToolExecutor existente.
Importe este arquivo no main.py APÓS importar o tool_executor.
"""

import logging
from blogger_module import publish_post

logger = logging.getLogger(__name__)


def _patch_tool_executor(executor):
    """
    Adiciona suporte à tool blogger.publish_post no ToolExecutor.
    Chame esta função passando a instância do tool_executor após criá-la.
    """
    original_execute_plan = executor.execute_plan

    def patched_execute_plan(plan, cycle_number=None):
        # Separar steps do Blogger dos demais
        blogger_steps = [s for s in plan if s.get("tool") == "blogger.publish_post"]
        other_steps = [s for s in plan if s.get("tool") != "blogger.publish_post"]

        # Executar tools normais primeiro
        result = original_execute_plan(other_steps, cycle_number) if other_steps else {
            "tools_executed": [], "insights": [], "errors": []
        }

        # Executar steps do Blogger
        for step in blogger_steps:
            args = step.get("args", {})
            title = args.get("title", "Artigo sem título")
            content = args.get("content", "")
            labels = args.get("labels", ["saúde", "emagrecimento"])
            affiliate_link = args.get("affiliate_link")
            affiliate_product = args.get("affiliate_product")

            if not content or len(content) < 100:
                tool_result = {
                    "tool": "blogger.publish_post",
                    "step_id": step.get("id", "blogger_step"),
                    "success": False,
                    "error": "Conteúdo muito curto para publicar (mínimo 100 caracteres).",
                    "used_fallback": False,
                }
            else:
                try:
                    pub_result = publish_post(
                        title=title,
                        content=content,
                        labels=labels,
                        affiliate_link=affiliate_link,
                        affiliate_product=affiliate_product,
                    )
                    tool_result = {
                        "tool": "blogger.publish_post",
                        "step_id": step.get("id", "blogger_step"),
                        "success": pub_result.get("success", False),
                        "url": pub_result.get("url", ""),
                        "post_id": pub_result.get("post_id", ""),
                        "title": pub_result.get("title", title),
                        "published_at": pub_result.get("published_at", ""),
                        "error": pub_result.get("error", ""),
                        "used_fallback": False,
                    }
                    if tool_result["success"]:
                        result["insights"].append(
                            f"Artigo publicado no Blogger: {tool_result['url']}"
                        )
                except Exception as e:
                    logger.error(f"Erro ao publicar no Blogger: {e}")
                    tool_result = {
                        "tool": "blogger.publish_post",
                        "step_id": step.get("id", "blogger_step"),
                        "success": False,
                        "error": str(e),
                        "used_fallback": False,
                    }

            result["tools_executed"].append(tool_result)

        return result

    executor.execute_plan = patched_execute_plan
    logger.info("ToolExecutor patcheado com suporte a blogger.publish_post")
    return executor
