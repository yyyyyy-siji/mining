"""Verification script to test Minimax API connection and the mining pipeline."""

import asyncio
from rich.console import Console
from signal_miner.settings import AppSettings
from signal_miner.llm.minimax_adapter import MinimaxAdapter
from signal_miner.pipeline.runner import run_mining_pipeline, ingest_feedback
from signal_miner.db import init_db, close_db
from signal_miner.models import new_id

console = Console()

async def main():
    console.print("\n[bold cyan]1. 初始化配置...[/bold cyan]")
    settings = AppSettings()
    
    if not settings.minimax_api_key:
        console.print("[bold red]错误：没有在 .env 中找到 MINIMAX_API_KEY[/bold red]")
        return
        
    llm = MinimaxAdapter(
        api_key=settings.minimax_api_key,
        group_id=settings.minimax_group_id,
        model=settings.minimax_model,
        base_url="https://api.minimaxi.com/v1"
    )
    console.print(f"[green]已配置 Minimax 适配器 (模型: {settings.minimax_model})[/green]")

    console.print("\n[bold cyan]2. 测试大模型连通性 (文本生成)...[/bold cyan]")
    try:
        reply = await llm.call_text("请回复'API连接正常'。")
        console.print(f"[green]成功收到回复:[/green] {reply.strip()}")
    except Exception as e:
        console.print(f"[bold red]API连通性测试失败:[/bold red] {e}")
        return

    console.print("\n[bold cyan]3. 测试大模型向量化 (Embedding)...[/bold cyan]")
    try:
        vec = await llm.embed("这是一个测试用的信号句子。")
        console.print(f"[green]成功生成向量! (维度: {len(vec)})[/green]")
    except Exception as e:
        console.print(f"[bold red]向量化测试失败:[/bold red] {e}")
        return
        
    console.print("\n[bold cyan]4. 测试完整挖矿管线打通...[/bold cyan]")
    await init_db(settings.database_url)
    try:
        # 注入两条测试反馈以触发聚类
        fb1_id = await ingest_feedback({
            "source_type": "test",
            "source_id": "t1",
            "dedupe_key": "test_dedupe_1",
            "content": {"subject": "无法导出PDF", "text": "报告界面的导出按钮点击没反应，急需使用！"}
        })
        fb2_id = await ingest_feedback({
            "source_type": "test",
            "source_id": "t2",
            "dedupe_key": "test_dedupe_2",
            "content": {"subject": "导出功能报错", "text": "我想把数据导出成PDF格式分享给老板，结果一直提示失败。"}
        })
        console.print(f"[dim]已虚拟注入 2 条反馈数据...[/dim]")
        
        run_id = new_id("run")
        console.print("[dim]开始执行核心管线 (提取 -> 向量 -> 聚类 -> 提炼资产)...[/dim]")
        
        # 运行管线
        await run_mining_pipeline(
            run_id=run_id,
            feedback_ids=[fb1_id, fb2_id],
            llm=llm,
            max_signals=3,
            confidence_threshold=0.5
        )
        console.print("[bold green]✅ 管线工作流执行完毕！打通成功！[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]管线执行发生异常:[/bold red] {e}")
    finally:
        await close_db()
        console.print("\n[bold cyan]验证结束。如果上方全部是绿色，说明系统一切正常，请去启动 Web 界面吧！[/bold cyan]")

if __name__ == "__main__":
    asyncio.run(main())
